"""
Modelos de la capa semántica (red documental gobernada).

Implementa el brief "Capa de relaciones y conocimiento":
- KnowledgeObject   → entidades semánticas (sistema, rol, área, formulario, ...).
- DocumentRelation  → relaciones candidatas/confirmadas entre documentos y entidades.
- DocumentChunk     → chunks indexables por versión aprobada (RAG de Tyto).
- EvidenceItem      → evidencias asociadas a un documento (ADR-013/017).

Reglas de gobernanza (Decision Log):
- ADR-006: la IA propone (status=candidate), el humano valida (status=confirmed).
- ADR-003: las relaciones son metadatos derivados y editables.
- ADR-002: Tyto consulta solo documentos aprobados y relaciones confirmadas.
- ADR-017: la entidad central sigue siendo document/document_version; el
  conocimiento emerge de la red, no hay entidad "Conocimiento" contenedora.

Nota sobre `DocumentChunk.embedding`: en PostgreSQL la columna es `vector(1536)`
(pgvector, creada por la migración 0005). En el ORM se mapea como Text con el
literal pgvector ("[0.1,0.2,...]") para mantener compatibilidad con SQLite en
tests. La serialización vive en process_ai_core.semantic.chunking.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .pgvector_type import VectorLiteral

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Tipos de entidad semántica soportados (brief §3)
KNOWLEDGE_OBJECT_TYPES = {
    "sistema",
    "rol",
    "area",
    "equipo",
    "formulario",
    "proceso",
    "ubicacion",
    "normativa",
    "documento",
}

# Tipos de relación soportados (brief §3 / Product Blueprint §8)
RELATION_TYPES = {
    "usa",
    "requiere",
    "genera",
    "relacionado_con",
    "describe",
    "aplica_a",
    "depende_de",
    "reemplaza_a",
    "ejecutado_por",
    "aprobado_por",
    "ubicado_en",
}

# Ciclo de vida de una relación (brief §6)
RELATION_STATUSES = {"candidate", "confirmed", "rejected", "obsolete"}


class KnowledgeObject(Base):
    """
    Entidad semántica del workspace (sistema, rol, área, equipo, formulario,
    proceso, ubicación, normativa).

    NO es un contenedor de conocimiento (ADR-017): es un nodo de la red al que
    los documentos se relacionan vía DocumentRelation.
    """
    __tablename__ = "knowledge_objects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)

    # sistema | rol | area | equipo | formulario | proceso | ubicacion | normativa | documento
    type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Nombre canónico ("SAP ERP") y normalizado para matching ("sap erp")
    canonical_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    # Embedding persistido del normalized_name (paso 3 de la cascada de matching).
    # vector(1536) en PostgreSQL, TEXT en SQLite (VectorLiteral), igual que
    # DocumentChunk.embedding. Guarda el literal pgvector ("[...]").
    name_embedding: Mapped[str | None] = mapped_column(VectorLiteral(1536), nullable=True)
    # Versionado del embedding (lección ADR-008): modelo con el que se generó el
    # vector. Si cambia el modelo, los vectores viejos NO se comparan a ciegas
    # (se recomputan) y hace falta backfill explícito.
    name_embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "type", "normalized_name", name="uq_knowledge_object_identity"),
    )


class DocumentRelation(Base):
    """
    Relación entre un documento y un knowledge_object (o entre documentos).

    Ciclo de vida: candidate → confirmed | rejected; confirmed → obsolete.
    Solo las relaciones `confirmed` forman la red documental que consulta Tyto.
    """
    __tablename__ = "document_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)

    # 'document' | knowledge_object.type
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # usa | requiere | genera | relacionado_con | describe | aplica_a | depende_de
    # | reemplaza_a | ejecutado_por | aprobado_por | ubicado_en
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)

    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Confianza 0..1 estimada por el pipeline (solo informativa; ADR-006)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Fragmento del documento que justifica la relación
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Versión aprobada de la que se extrajo la relación
    source_document_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_versions.id"), nullable=True, index=True
    )

    # candidate | confirmed | rejected | obsolete
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate", index=True)

    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=True)

    #: Quién DECIDIÓ sobre la relación. Se escribe al confirmar **y** al
    #: rechazar: no es "quién la confirmó". Se llamaba `confirmed_by` y mentía en
    #: las relaciones rechazadas (migración 0023).
    #:
    #: NULL con `status='confirmed'` es un dato, no un faltante: significa que la
    #: confirmó el sistema por autoconfianza, sin intervención humana (ver
    #: `relation_autoconfirm_threshold` en config.py).
    decided_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])  # noqa: F821

    __table_args__ = (
        Index("ix_document_relations_doc_status", "document_id", "status"),
        Index("ix_document_relations_target", "target_type", "target_id"),
        Index("ix_document_relations_source", "source_type", "source_id"),
    )


class DocumentChunk(Base):
    """
    Chunk indexable de una versión aprobada de documento (RAG de Tyto).

    `embedding` guarda el literal pgvector; en PostgreSQL la columna real es
    vector(1536) (ver migración 0005_semantic_layer).
    """
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # vector(1536) en PostgreSQL, TEXT en SQLite (VectorLiteral). Guarda el literal.
    embedding: Mapped[str | None] = mapped_column(VectorLiteral(1536), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunk_index"),
    )


class EvidenceItem(Base):
    """
    Evidencia asociada a un documento (video, audio, pdf, entrevista, foto, ...).

    Las evidencias persisten y se siguen sumando a lo largo de la vida del
    documento (ADR-013/017); no se borran al versionar.

    ⚠️ **SIN IMPLEMENTAR: esta tabla no tiene un solo escritor** (relevado
    2026-07-31). No hay un `EvidenceItem(...)` en todo el repo, y está en 0 filas
    en test y en prod. `POST /api/v1/evidence/process` procesa un archivo y
    devuelve el texto extraído **sin persistir nada**.

    Se deja porque el modelo es correcto y el flujo está especificado
    (ADR-013/017): es una feature pendiente, no código muerto — la diferencia con
    `workspace_invitations`, que sí se borró en la 0020, es que aquella tenía
    helpers completos y ninguna especificación detrás.

    Consecuencia para quien la implemente: `added_by` es una **referencia**
    (§5 del estándar de directorio), así que se guarda el uuid y el nombre se
    resuelve al leer contra `users_directory`. No agregar una columna `*_by_name`.
    """
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)

    # video | audio | pdf | manual | entrevista | imagen | foto | captura | mail | normativa
    type: Mapped[str] = mapped_column(String(30), nullable=False)

    storage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    added_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Estados de una corrida del pipeline semántico (observabilidad).
PIPELINE_STATUSES = {"running", "ok", "error"}


class SemanticPipelineRun(Base):
    """Rastro de una corrida del pipeline semántico (observabilidad — hardening).

    Una fila por corrida (por documento + versión). El pipeline corre best-effort
    al aprobar una versión (o vía POST /relations/suggest); un fallo NUNCA voltea
    la aprobación, pero queda registrado acá con el `stage` donde falló y el
    `error`, para diagnóstico. Tabla de auditoría desacoplada (sin FKs duras: el
    rastro sobrevive aunque se borre el documento).
    """

    __tablename__ = "semantic_pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)

    # running | ok | error
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # extraction | candidates | chunking | done | <stage que falló>
    stage: Mapped[str] = mapped_column(String(30), default="start")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidates_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_indexed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # approval (hook post-aprobación) | manual (POST /relations/suggest)
    trigger: Mapped[str] = mapped_column(String(20), default="approval")

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_semantic_pipeline_runs_doc_started", "document_id", "started_at"),
    )


class TytoQueryLog(Base):
    """Registro de cada consulta a Tyto (spec Tyto §1 "Segura" — logging, ADR-011).

    Una fila por pregunta: qué se preguntó, si se respondió o se rechazó, y qué
    fuentes se usaron. Alimenta el futuro dashboard de "preguntas sin respuesta"
    y la detección de brechas documentales. Tabla de auditoría desacoplada (sin
    FKs duras: el rastro sobrevive aunque se borren documentos o usuarios).
    """

    __tablename__ = "tyto_query_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    #: Conversación a la que pertenece esta pregunta.
    #:
    #: COLUMNA PLANA, SIN FOREIGN KEY — Y NO ES UN DESCUIDO.
    #:
    #: Con una FK a `tyto_session`, borrar una conversación del historial
    #: personal arrastraría (CASCADE) o bloquearía (RESTRICT) las filas de
    #: auditoría. Las dos cosas están mal: este log alimenta la detección de
    #: brechas documentales (ADR-011), que tiene que seguir funcionando aunque
    #: la persona haya limpiado su historial. Que alguien borre su conversación
    #: es una acción sobre SU vista, no sobre el rastro del sistema.
    #:
    #: Es la misma razón por la que `document_id` y `user_id` tampoco tienen FK
    #: acá. Si en algún momento aparece un `session_id` huérfano, eso es correcto
    #: y esperado: la pregunta ocurrió igual.
    #:
    #: Si venís a "arreglar esto" agregando la FK: el arreglo es el bug.
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: Texto de la respuesta, para poder reconstruir el hilo al recargar. Vacío
    #: en los rechazos, donde lo que se muestra es `refusal_reason`.
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    refusal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON: [{source_id, document_id, document_version_id, tier, cited}] — las
    # fuentes recuperadas y cuáles citó efectivamente la respuesta.
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tyto_query_log_ws_created", "workspace_id", "created_at"),
    )


class TytoSession(Base):
    """
    Agrupador de conversación de Tyto: el "hilo" que el usuario ve.

    Existe para que una conversación sobreviva a un F5. Cada pregunta seguía
    siendo un evento suelto en `tyto_query_log`; esto les da un padre.

    HISTORIAL PERSONAL, NO REGISTRO DE ACTIVIDAD
    --------------------------------------------
    Se lee SIEMPRE filtrando por `user_id` además de `workspace_id`, sin
    excepción de rol ni de admin. No es privacidad genérica: un registro de qué
    preguntó cada persona revela lo que esa persona NO SABE. Si un supervisor
    puede ver "Juan preguntó doce veces cómo cerrar caja", el producto se
    convierte en una herramienta de vigilancia que nadie pidió y la gente deja
    de preguntar — que es exactamente lo contrario de lo que Tyto necesita que
    hagan. Para detectar brechas documentales se usa `tyto_query_log` agregado y
    anónimo, que para eso está desacoplado.

    El título sale de la primera pregunta, truncado, y es editable. No se le
    pide a un LLM que lo resuma: cuesta plata y agrega latencia para algo que el
    usuario arregla en un clic si no le gusta.
    """

    __tablename__ = "tyto_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    #: Se toca con cada pregunta: es el orden en que se listan los "recientes".
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        # El índice del listado: mis sesiones de este workspace, más recientes
        # primero. Lleva user_id porque NO existe un listado sin él.
        Index(
            "ix_tyto_session_ws_user_updated",
            "workspace_id",
            "user_id",
            updated_at.desc(),
        ),
    )
