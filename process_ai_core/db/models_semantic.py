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
    confirmed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunk_index"),
    )


class EvidenceItem(Base):
    """
    Evidencia asociada a un documento (video, audio, pdf, entrevista, foto, ...).

    Las evidencias persisten y se siguen sumando a lo largo de la vida del
    documento (ADR-013/017); no se borran al versionar.
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
