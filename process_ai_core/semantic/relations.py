"""RelationService: matching en cascada, relaciones candidatas, merge e impacto.

Matching (brief §4, callout): el LLM NO es el mecanismo de matching. Cascada:
  1. exacto     → normalized_name igual (mismo workspace + tipo)
  2. fuzzy      → similitud de secuencia sobre normalized_name (portable
                  SQLite/Postgres; en Postgres además existe el índice pg_trgm
                  para búsquedas server-side vía search_knowledge_objects)
  3. embedding  → similitud coseno con el EmbeddingProvider, solo para casos
                  ambiguos; si no hay provider configurado se saltea.

Gobernanza:
- Toda relación generada por el pipeline nace status='candidate' (ADR-006).
- Una relación 'rejected' no se vuelve a proponer para el mismo documento.
- confirm/reject valida segregación: quien creó la versión fuente no puede
  confirmar sus propias relaciones.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, UTC
from difflib import SequenceMatcher

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db.models import Document, DocumentVersion
from ..db.models_semantic import (
    DocumentRelation,
    KnowledgeObject,
    RELATION_STATUSES,
    RELATION_TYPES,
    KNOWLEDGE_OBJECT_TYPES,
)
from . import _pg
from .chunking import embedding_to_literal, literal_to_embedding
from .extraction import ExtractionResult
from .normalize import normalize_name

logger = logging.getLogger(__name__)

# Umbrales de la cascada de matching
FUZZY_MATCH_THRESHOLD = 0.88        # se considera la misma entidad
EMBEDDING_MATCH_THRESHOLD = 0.90    # similitud coseno para casos ambiguos
DUPLICATE_HINT_THRESHOLD = 0.72     # sugerir "posible duplicado" en la UI

# Shortlist fuzzy server-side (pg_trgm). El floor del operador `%` (0.3, el default
# de pg_trgm) mantiene el índice selectivo: un match real (SequenceMatcher >= 0.88,
# o el hint de duplicado >= 0.72) tiene alta similitud de trigramas, así que entra;
# un floor más bajo hincharía el shortlist con ruido y forzaría un scan casi total.
# La autoridad de la decisión de identidad sigue siendo SequenceMatcher (umbrales
# de arriba) sobre este shortlist.
FUZZY_SHORTLIST_LIMIT = 50
FUZZY_TRGM_FLOOR = 0.3


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _is_token_subset(a: str, b: str) -> bool:
    """True si todos los tokens de un nombre están contenidos en el otro ("sap" ⊂ "sap erp")."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


@dataclass
class MatchResult:
    knowledge_object: KnowledgeObject | None
    match_kind: str      # exact | fuzzy | embedding | none
    score: float


_USE_SETTINGS = object()  # sentinela: resolver el umbral desde get_settings()


class RelationService:
    """Genera, gobierna y consulta la red de relaciones documentales."""

    def __init__(self, embedding_provider=None, *, autoconfirm_threshold=_USE_SETTINGS) -> None:
        # Provider opcional; si es None se resuelve lazy y puede no estar configurado.
        self._embedding_provider = embedding_provider
        self._embedding_unavailable = False
        # Cache de embeddings de nombres POR CORRIDA: evita re-embeber el mismo
        # nombre (query o candidato) más de una vez dentro de la vida del service.
        self._name_embedding_cache: dict[str, list[float]] = {}
        # Umbral de autoconfirmación (Tarea 3). Por defecto se lee de settings
        # (RELATION_AUTOCONFIRM_THRESHOLD, off por defecto); inyectable en tests.
        self._autoconfirm_threshold_arg = autoconfirm_threshold

    def _autoconfirm_threshold(self) -> float | None:
        """Umbral efectivo de autoconfirmación, o None (off) => todo a revisión humana."""
        if self._autoconfirm_threshold_arg is not _USE_SETTINGS:
            return self._autoconfirm_threshold_arg
        try:
            from ..config import get_settings

            return get_settings().relation_autoconfirm_threshold
        except Exception:  # pragma: no cover - defensivo
            return None

    # ------------------------------------------------------------------
    # Matching en cascada
    # ------------------------------------------------------------------
    def match_entity(
        self,
        session: Session,
        workspace_id: str,
        entity_type: str,
        normalized_name: str,
    ) -> MatchResult:
        """Cascada exacto → fuzzy → embedding contra knowledge_objects del workspace."""
        # 1) Exacto
        exact = (
            session.query(KnowledgeObject)
            .filter_by(workspace_id=workspace_id, type=entity_type, normalized_name=normalized_name)
            .first()
        )
        if exact:
            return MatchResult(exact, "exact", 1.0)

        # Shortlist de candidatos: en Postgres lo hace pg_trgm server-side (índice
        # GIN); en SQLite u otro dialecto trae todos y filtra en Python.
        candidates = self._fuzzy_candidates(
            session, workspace_id, entity_type, normalized_name
        )
        if not candidates:
            return MatchResult(None, "none", 0.0)

        # 2) Fuzzy — SequenceMatcher sigue siendo la autoridad (umbrales sin cambios).
        best, best_score = None, 0.0
        for ko in candidates:
            score = _similarity(normalized_name, ko.normalized_name)
            if score > best_score:
                best, best_score = ko, score
        if best is not None and best_score >= FUZZY_MATCH_THRESHOLD:
            return MatchResult(best, "fuzzy", best_score)

        # 3) Embedding (solo casos ambiguos: hubo candidato fuzzy pero no alcanzó)
        if best is not None and best_score >= DUPLICATE_HINT_THRESHOLD:
            emb_match = self._embedding_match(normalized_name, candidates)
            if emb_match is not None:
                return emb_match

        return MatchResult(None, "none", best_score)

    def _fuzzy_candidates(
        self,
        session: Session,
        workspace_id: str,
        entity_type: str,
        normalized_name: str,
    ) -> list[KnowledgeObject]:
        """Candidatos para los pasos fuzzy/embedding.

        En PostgreSQL con pg_trgm hace el shortlist server-side entrando por el
        índice GIN (ix_knowledge_objects_name_trgm); si no hay pg_trgm (SQLite,
        degradado) o el SQL falla, trae todos los del workspace+tipo (comportamiento
        actual, portable).
        """
        if _pg.trgm_ready(session):
            try:
                return self._fuzzy_candidates_sql(
                    session, workspace_id, entity_type, normalized_name
                )
            except Exception as exc:  # pragma: no cover - defensivo (degradación)
                logger.warning(
                    "matching: shortlist pg_trgm falló, fallback Python (%s)",
                    type(exc).__name__,
                )
        return (
            session.query(KnowledgeObject)
            .filter_by(workspace_id=workspace_id, type=entity_type)
            .all()
        )

    def _fuzzy_candidates_sql(
        self,
        session: Session,
        workspace_id: str,
        entity_type: str,
        normalized_name: str,
    ) -> list[KnowledgeObject]:
        """Shortlist por pg_trgm: `%` en el WHERE (usa el índice GIN), similarity()
        solo en el ORDER BY. El umbral del operador `%` se baja con set_limit()
        acotado por save/restore para no filtrarse a otras consultas de la txn."""
        sch = _pg.schema()
        # Save/restore del umbral de `%` (garantía dura de no-leak; verificable con
        # show_limit() antes/después). SET LOCAL afectaría al resto de la txn.
        # set_limit espera 'real' (float4); psycopg manda float como double → cast.
        old_limit = session.execute(text("SELECT show_limit()")).scalar()
        try:
            session.execute(
                text("SELECT set_limit(CAST(:f AS real))"), {"f": FUZZY_TRGM_FLOOR}
            )
            rows = session.execute(
                text(
                    f"""
                    SELECT id
                    FROM "{sch}".knowledge_objects
                    WHERE workspace_id = :ws AND type = :type
                      AND normalized_name % :name
                    ORDER BY similarity(normalized_name, :name) DESC
                    LIMIT :k
                    """
                ),
                {
                    "ws": workspace_id,
                    "type": entity_type,
                    "name": normalized_name,
                    "k": FUZZY_SHORTLIST_LIMIT,
                },
            ).all()
        finally:
            try:
                session.execute(
                    text("SELECT set_limit(CAST(:f AS real))"), {"f": old_limit}
                )
            except Exception:  # pragma: no cover - defensivo
                pass

        ids = [r.id for r in rows]
        if not ids:
            return []
        # Hidratar ORM preservando el orden por similitud del shortlist.
        objs = {
            o.id: o
            for o in session.query(KnowledgeObject)
            .filter(KnowledgeObject.id.in_(ids))
            .all()
        }
        return [objs[i] for i in ids if i in objs]

    def _embedding_match(
        self, normalized_name: str, candidates: list[KnowledgeObject]
    ) -> MatchResult | None:
        """Paso 3 de la cascada. Devuelve None si no hay provider o no hay match.

        Ya no re-embebe los candidatos en cada llamada: usa el `name_embedding`
        persistido de cada knowledge_object (si su modelo coincide con el activo),
        y solo embebe el nombre de la query una vez (con cache por corrida). Si a un
        candidato le falta el vector o fue generado con otro modelo, lo recomputa y
        lo persiste write-through (nunca compara vectores de modelos distintos)."""
        provider = self._get_embedding_provider()
        if provider is None:
            return None
        model = self._active_embedding_model()
        try:
            query_vec = self._embed_name(normalized_name, provider)
        except Exception as exc:
            logger.warning("Embedding matching no disponible: %s", type(exc).__name__)
            self._embedding_unavailable = True
            return None

        pool = candidates[:50]
        best, best_score = None, 0.0
        for ko in pool:
            try:
                vec = self._candidate_embedding(ko, provider, model)
            except Exception as exc:
                logger.warning("Embedding matching no disponible: %s", type(exc).__name__)
                self._embedding_unavailable = True
                break
            if vec is None:
                continue
            score = _cosine(query_vec, vec)
            if score > best_score:
                best, best_score = ko, score
        if best is not None and best_score >= EMBEDDING_MATCH_THRESHOLD:
            return MatchResult(best, "embedding", best_score)
        return None

    def _active_embedding_model(self) -> str | None:
        """Modelo de embeddings activo (para versionar `name_embedding`)."""
        try:
            from ..config import get_settings

            return get_settings().openai_model_embedding
        except Exception:  # pragma: no cover - defensivo
            return None

    def _embed_name(self, name: str, provider) -> list[float]:
        """Embebe un nombre con cache por corrida (evita recomputar el mismo nombre)."""
        cached = self._name_embedding_cache.get(name)
        if cached is not None:
            return cached
        vec = provider.embed([name])[0]
        self._name_embedding_cache[name] = vec
        return vec

    def _candidate_embedding(
        self, ko: KnowledgeObject, provider, model: str | None
    ) -> list[float] | None:
        """Vector del nombre del candidato: usa el persistido si el modelo coincide;
        si falta o difiere el modelo, lo recomputa y lo persiste write-through."""
        if ko.name_embedding and ko.name_embedding_model == model:
            vec = literal_to_embedding(ko.name_embedding)
            if vec:
                return vec
        vec = self._embed_name(ko.normalized_name, provider)
        ko.name_embedding = embedding_to_literal(vec)
        ko.name_embedding_model = model
        return vec

    def _get_embedding_provider(self):
        if self._embedding_unavailable:
            return None
        if self._embedding_provider is None:
            try:
                from ..ai.factory import get_embedding_provider

                self._embedding_provider = get_embedding_provider()
            except Exception:
                self._embedding_unavailable = True
                return None
        return self._embedding_provider

    # ------------------------------------------------------------------
    # Generación de relaciones candidatas (pipeline)
    # ------------------------------------------------------------------
    def generate_candidates(
        self,
        session: Session,
        *,
        document: Document,
        version: DocumentVersion,
        extraction: ExtractionResult,
    ) -> list[DocumentRelation]:
        """Convierte una extracción en filas status='candidate'.

        - Matchea cada entidad contra la base (cascada); si no hay match crea el
          KnowledgeObject (marcado como creado por IA en metadata_json).
        - No duplica relaciones ya existentes (candidate/confirmed) ni vuelve a
          proponer relaciones 'rejected' para el mismo documento+destino.
        - Marca 'obsolete' las candidatas de versiones anteriores del documento.
        """
        workspace_id = document.workspace_id
        created: list[DocumentRelation] = []
        autoconfirm = self._autoconfirm_threshold()
        autoconfirmed = 0

        # Candidatas de versiones anteriores quedan obsoletas: la sugerencia
        # vigente es siempre la de la última versión aprobada. Las confirmadas
        # NO se tocan (siguen siendo la red oficial hasta que un humano decida).
        (
            session.query(DocumentRelation)
            .filter(
                DocumentRelation.document_id == document.id,
                DocumentRelation.status == "candidate",
                DocumentRelation.source_document_version_id != version.id,
            )
            .update({"status": "obsolete"}, synchronize_session=False)
        )

        for rel in extraction.relations:
            match = self.match_entity(
                session, workspace_id, rel.entity.type, rel.entity.normalized_name
            )
            ko = match.knowledge_object
            if ko is None:
                ko = KnowledgeObject(
                    workspace_id=workspace_id,
                    type=rel.entity.type,
                    canonical_name=rel.entity.canonical_name,
                    normalized_name=rel.entity.normalized_name,
                    description=rel.entity.description or None,
                    metadata_json=json.dumps({"created_by_ai": True}),
                )
                # name_embedding queda NULL al crear: se completa lazy (write-through)
                # la primera vez que el KO entra al paso embedding del matching. Así
                # generate_candidates NO dispara llamadas de embedding por cada entidad
                # (que además romperían la portabilidad/costo de los tests); la
                # persistencia ocurre donde el vector realmente se usa. El backfill
                # masivo de filas viejas corre aparte (script manual contra Supabase).
                session.add(ko)
                session.flush()

            existing = (
                session.query(DocumentRelation)
                .filter_by(
                    document_id=document.id,
                    relation_type=rel.relation_type,
                    target_type=ko.type,
                    target_id=ko.id,
                )
                .filter(DocumentRelation.status.in_(["candidate", "confirmed", "rejected"]))
                .first()
            )
            if existing:
                # Si sigue vigente como candidata, re-anclarla a la versión nueva
                if existing.status == "candidate":
                    existing.source_document_version_id = version.id
                    existing.confidence = rel.confidence
                    existing.evidence_text = rel.evidence_text or existing.evidence_text
                continue

            relation = DocumentRelation(
                workspace_id=workspace_id,
                document_id=document.id,
                source_type="document",
                source_id=document.id,
                relation_type=rel.relation_type,
                target_type=ko.type,
                target_id=ko.id,
                confidence=rel.confidence,
                evidence_text=rel.evidence_text or None,
                source_document_version_id=version.id,
                status="candidate",
                created_by_ai=True,
            )
            # Autoconfirmación opcional (ADR-006 sigue siendo el default: off).
            # confirmed_by queda NULL => rastro de "confirmada por el sistema".
            if (
                autoconfirm is not None
                and rel.confidence is not None
                and rel.confidence >= autoconfirm
            ):
                relation.status = "confirmed"
                relation.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
                autoconfirmed += 1
            session.add(relation)
            created.append(relation)

        session.flush()
        if autoconfirm is not None:
            logger.info(
                "relaciones: autoconfirm umbral=%.2f doc=%s: %d/%d autoconfirmadas",
                autoconfirm, document.id, autoconfirmed, len(created),
            )
        return created

    # ------------------------------------------------------------------
    # Revisión humana (ADR-006)
    # ------------------------------------------------------------------
    def confirm(
        self,
        session: Session,
        relation: DocumentRelation,
        user_id: str,
        *,
        enforce_segregation: bool = True,
    ) -> DocumentRelation:
        """candidate → confirmed. Valida segregación de funciones."""
        if relation.status != "candidate":
            raise ValueError(f"Solo se puede confirmar una relación 'candidate' (actual: {relation.status})")
        self._check_segregation(session, relation, user_id, enforce_segregation)
        relation.status = "confirmed"
        relation.confirmed_by = user_id
        relation.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return relation

    def reject(
        self,
        session: Session,
        relation: DocumentRelation,
        user_id: str,
        *,
        enforce_segregation: bool = True,
    ) -> DocumentRelation:
        """candidate → rejected. Se conserva para no re-proponerla."""
        if relation.status != "candidate":
            raise ValueError(f"Solo se puede rechazar una relación 'candidate' (actual: {relation.status})")
        self._check_segregation(session, relation, user_id, enforce_segregation)
        relation.status = "rejected"
        relation.confirmed_by = user_id
        relation.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        session.flush()
        return relation

    def _check_segregation(
        self,
        session: Session,
        relation: DocumentRelation,
        user_id: str,
        enforce: bool,
    ) -> None:
        """El creador de la versión fuente no valida sus propias relaciones."""
        if not enforce or not relation.source_document_version_id:
            return
        version = (
            session.query(DocumentVersion)
            .filter_by(id=relation.source_document_version_id)
            .first()
        )
        if version and version.created_by and version.created_by == user_id:
            raise PermissionError(
                "No puedes validar relaciones extraídas de una versión que creaste. "
                "Debe validarlas otro usuario."
            )

    def edit(
        self,
        session: Session,
        relation: DocumentRelation,
        *,
        relation_type: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> DocumentRelation:
        """Edita una relación incorrecta (ADR-003: metadatos editables).

        La relación editada deja de ser 'creada por IA'; sigue el ciclo normal
        (si era candidate, un humano igual debe confirmarla).
        """
        if relation.status in ("rejected", "obsolete"):
            raise ValueError(f"No se puede editar una relación '{relation.status}'")
        if relation_type is not None:
            if relation_type not in RELATION_TYPES:
                raise ValueError(f"relation_type inválido: {relation_type}")
            relation.relation_type = relation_type
        if (target_type is None) != (target_id is None):
            raise ValueError("target_type y target_id deben actualizarse juntos")
        if target_type is not None and target_id is not None:
            if target_type == "document":
                target = session.query(Document).filter_by(id=target_id).first()
                if not target or target.workspace_id != relation.workspace_id:
                    raise ValueError(f"Documento destino {target_id} no encontrado en el workspace")
            else:
                if target_type not in KNOWLEDGE_OBJECT_TYPES:
                    raise ValueError(f"target_type inválido: {target_type}")
                target = session.query(KnowledgeObject).filter_by(id=target_id).first()
                if not target or target.workspace_id != relation.workspace_id:
                    raise ValueError(f"Knowledge object {target_id} no encontrado en el workspace")
            relation.target_type = target_type
            relation.target_id = target_id
        relation.created_by_ai = False
        session.flush()
        return relation

    # ------------------------------------------------------------------
    # Knowledge objects: duplicados y merge
    # ------------------------------------------------------------------
    def find_possible_duplicate(
        self, session: Session, ko: KnowledgeObject
    ) -> KnowledgeObject | None:
        """Sugiere un posible duplicado para la UI ("SAP" vs "SAP ERP")."""
        siblings = (
            session.query(KnowledgeObject)
            .filter(
                KnowledgeObject.workspace_id == ko.workspace_id,
                KnowledgeObject.type == ko.type,
                KnowledgeObject.id != ko.id,
            )
            .all()
        )
        best, best_score = None, 0.0
        for other in siblings:
            score = _similarity(ko.normalized_name, other.normalized_name)
            if _is_token_subset(ko.normalized_name, other.normalized_name):
                score = max(score, DUPLICATE_HINT_THRESHOLD)
            if score > best_score:
                best, best_score = other, score
        if best is not None and best_score >= DUPLICATE_HINT_THRESHOLD:
            return best
        return None

    def merge_knowledge_objects(
        self,
        session: Session,
        *,
        source: KnowledgeObject,
        into: KnowledgeObject,
    ) -> KnowledgeObject:
        """Une un duplicado: reapunta TODAS las document_relations y elimina el origen.

        El nombre del origen queda registrado como alias en metadata_json del
        destino, para que el matching futuro lo resuelva por merge previo.
        """
        if source.id == into.id:
            raise ValueError("No se puede unir un knowledge object consigo mismo")
        if source.workspace_id != into.workspace_id:
            raise ValueError("Los knowledge objects pertenecen a workspaces distintos")
        if source.type != into.type:
            raise ValueError(f"Tipos distintos: {source.type} vs {into.type}")

        # Reapuntar relaciones donde el origen es target
        target_rels = (
            session.query(DocumentRelation)
            .filter_by(target_type=source.type, target_id=source.id)
            .all()
        )
        for rel in target_rels:
            duplicate = (
                session.query(DocumentRelation)
                .filter(
                    DocumentRelation.document_id == rel.document_id,
                    DocumentRelation.relation_type == rel.relation_type,
                    DocumentRelation.target_type == into.type,
                    DocumentRelation.target_id == into.id,
                    DocumentRelation.id != rel.id,
                    DocumentRelation.status.in_(["candidate", "confirmed"]),
                )
                .first()
            )
            if duplicate is not None and rel.status in ("candidate", "confirmed"):
                # Ya existe la misma relación hacia el destino: conservar la más
                # "oficial" (confirmed gana sobre candidate) y descartar la otra.
                keep_existing = (
                    duplicate.status == "confirmed" or rel.status == "candidate"
                )
                if keep_existing:
                    session.delete(rel)
                    continue
                session.delete(duplicate)
            rel.target_type = into.type
            rel.target_id = into.id

        # Reapuntar relaciones donde el origen es source (relaciones entidad → x)
        source_rels = (
            session.query(DocumentRelation)
            .filter_by(source_type=source.type, source_id=source.id)
            .all()
        )
        for rel in source_rels:
            rel.source_type = into.type
            rel.source_id = into.id

        # Alias en el destino
        try:
            meta = json.loads(into.metadata_json or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        aliases = set(meta.get("aliases", []))
        aliases.add(source.canonical_name)
        meta["aliases"] = sorted(aliases)
        into.metadata_json = json.dumps(meta, ensure_ascii=False)

        session.delete(source)
        session.flush()
        return into

    def search_knowledge_objects(
        self,
        session: Session,
        workspace_id: str,
        *,
        type: str | None = None,
        q: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeObject]:
        """Búsqueda para autocompletar / detectar duplicados (GET /knowledge-objects)."""
        query = session.query(KnowledgeObject).filter_by(workspace_id=workspace_id)
        if type:
            query = query.filter(KnowledgeObject.type == type)
        if q:
            normalized = normalize_name(q)
            query = query.filter(KnowledgeObject.normalized_name.like(f"%{normalized}%"))
        return query.order_by(KnowledgeObject.canonical_name).limit(limit).all()

    # ------------------------------------------------------------------
    # Impacto (GET /documents/{id}/impact)
    # ------------------------------------------------------------------
    def impact(self, session: Session, document: Document) -> dict:
        """Documentos y entidades afectadas si cambia este documento.

        Recorre exclusivamente relaciones CONFIRMADAS (ADR-002/006).
        """
        confirmed = (
            session.query(DocumentRelation)
            .filter_by(document_id=document.id, status="confirmed")
            .all()
        )
        entity_ids = {
            r.target_id for r in confirmed if r.target_type != "document"
        }
        related_doc_ids = {
            r.target_id for r in confirmed if r.target_type == "document"
        }

        # Otros documentos que (vía relaciones confirmadas) apuntan a las mismas
        # entidades o directamente a este documento.
        affected_q = (
            session.query(DocumentRelation)
            .filter(
                DocumentRelation.workspace_id == document.workspace_id,
                DocumentRelation.status == "confirmed",
                DocumentRelation.document_id != document.id,
            )
        )
        affected_doc_ids: set[str] = set()
        for rel in affected_q.all():
            if rel.target_type == "document" and rel.target_id == document.id:
                affected_doc_ids.add(rel.document_id)
            elif rel.target_type != "document" and rel.target_id in entity_ids:
                affected_doc_ids.add(rel.document_id)
        affected_doc_ids |= related_doc_ids
        affected_doc_ids.discard(document.id)

        docs = (
            session.query(Document)
            .filter(Document.id.in_(affected_doc_ids))
            .all()
            if affected_doc_ids
            else []
        )
        entities = (
            session.query(KnowledgeObject)
            .filter(KnowledgeObject.id.in_(entity_ids))
            .all()
            if entity_ids
            else []
        )
        return {
            "document_id": document.id,
            "affected_documents": [
                {"id": d.id, "name": d.name, "status": d.status, "document_type": d.document_type}
                for d in docs
            ],
            "affected_entities": [
                {"id": e.id, "type": e.type, "name": e.canonical_name}
                for e in entities
            ],
        }


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
