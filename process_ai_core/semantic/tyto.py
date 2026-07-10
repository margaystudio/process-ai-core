"""TytoQueryService: recuperación gobernada para el asistente Tyto (RAG).

Contrato de gobernanza (ADR-002, brief §7) — Tyto SOLO puede usar:
- document_versions APPROVED vigentes (is_current=True) de documentos del
  workspace consultado;
- document_relations con status='confirmed' para expandir la red;
- document_chunks pertenecientes a esas versiones aprobadas vigentes.

Nunca usa relaciones 'candidate' ni documentos sin aprobar como fuente oficial.

Retrieval: si hay embeddings (pgvector / provider configurado) rankea por
similitud coseno; si no, degrada a scoring léxico simple. En ambos casos el
universo de búsqueda ya está filtrado por gobernanza ANTES de rankear.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..db.models import Document, DocumentVersion
from ..db.models_semantic import DocumentChunk, DocumentRelation, KnowledgeObject
from .chunking import literal_to_embedding

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 6


@dataclass
class TytoCitation:
    document_id: str
    document_name: str
    document_version_id: str
    chunk_id: str
    section_title: str | None
    content: str
    score: float


@dataclass
class TytoContext:
    """Contexto recuperado y gobernado, listo para ensamblar la respuesta."""
    citations: list[TytoCitation] = field(default_factory=list)
    related_entities: list[dict] = field(default_factory=list)
    related_documents: list[dict] = field(default_factory=list)


class TytoQueryService:
    """Recuperación de contexto para Tyto con filtro de gobernanza."""

    def __init__(self, embedding_provider=None) -> None:
        self._embedding_provider = embedding_provider
        self._embedding_unavailable = False

    # ------------------------------------------------------------------
    # Universo gobernado
    # ------------------------------------------------------------------
    def approved_current_versions(
        self, session: Session, workspace_id: str
    ) -> list[DocumentVersion]:
        """Versiones APPROVED vigentes de documentos del workspace (única fuente oficial)."""
        return (
            session.query(DocumentVersion)
            .join(Document, Document.id == DocumentVersion.document_id)
            .filter(
                Document.workspace_id == workspace_id,
                DocumentVersion.version_status == "APPROVED",
                DocumentVersion.is_current.is_(True),
            )
            .all()
        )

    def confirmed_relations(
        self, session: Session, workspace_id: str, document_ids: list[str]
    ) -> list[DocumentRelation]:
        """Relaciones CONFIRMADAS de los documentos dados (jamás candidate/rejected/obsolete)."""
        if not document_ids:
            return []
        return (
            session.query(DocumentRelation)
            .filter(
                DocumentRelation.workspace_id == workspace_id,
                DocumentRelation.status == "confirmed",
                DocumentRelation.document_id.in_(document_ids),
            )
            .all()
        )

    # ------------------------------------------------------------------
    # Query principal
    # ------------------------------------------------------------------
    def retrieve(
        self,
        session: Session,
        *,
        workspace_id: str,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> TytoContext:
        """Recupera chunks relevantes + expansión por la red confirmada."""
        versions = self.approved_current_versions(session, workspace_id)
        if not versions:
            return TytoContext()
        version_by_id = {v.id: v for v in versions}

        chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_version_id.in_(list(version_by_id)))
            .all()
        )
        if not chunks:
            return TytoContext()

        scored = self._rank(query, chunks)[:top_k]

        doc_by_version: dict[str, Document] = {}
        for v in versions:
            doc = session.query(Document).filter_by(id=v.document_id).first()
            if doc:
                doc_by_version[v.id] = doc

        citations: list[TytoCitation] = []
        cited_doc_ids: set[str] = set()
        for chunk, score in scored:
            doc = doc_by_version.get(chunk.document_version_id)
            if not doc:
                continue
            cited_doc_ids.add(doc.id)
            citations.append(
                TytoCitation(
                    document_id=doc.id,
                    document_name=doc.name,
                    document_version_id=chunk.document_version_id,
                    chunk_id=chunk.id,
                    section_title=chunk.section_title,
                    content=chunk.content,
                    score=round(score, 4),
                )
            )

        # Expansión por relaciones confirmadas (red documental gobernada)
        relations = self.confirmed_relations(session, workspace_id, sorted(cited_doc_ids))
        entity_ids = {r.target_id for r in relations if r.target_type != "document"}
        related_doc_ids = {r.target_id for r in relations if r.target_type == "document"}

        entities = (
            session.query(KnowledgeObject).filter(KnowledgeObject.id.in_(entity_ids)).all()
            if entity_ids
            else []
        )
        # Documentos relacionados: solo si están APROBADOS (gobernanza también en la expansión)
        related_docs = (
            session.query(Document)
            .filter(
                Document.id.in_(related_doc_ids),
                Document.workspace_id == workspace_id,
                Document.status == "approved",
            )
            .all()
            if related_doc_ids
            else []
        )

        return TytoContext(
            citations=citations,
            related_entities=[
                {"id": e.id, "type": e.type, "name": e.canonical_name} for e in entities
            ],
            related_documents=[
                {"id": d.id, "name": d.name, "document_type": d.document_type}
                for d in related_docs
            ],
        )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------
    def _rank(self, query: str, chunks: list[DocumentChunk]) -> list[tuple[DocumentChunk, float]]:
        query_vector = self._embed_query(query)
        with_embeddings = [
            (c, literal_to_embedding(c.embedding)) for c in chunks
        ]
        if query_vector is not None and any(vec for _, vec in with_embeddings):
            scored = [
                (c, _cosine(query_vector, vec) if vec else 0.0)
                for c, vec in with_embeddings
            ]
        else:
            scored = [(c, _lexical_score(query, c.content)) for c in chunks]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [pair for pair in scored if pair[1] > 0]

    def _embed_query(self, query: str) -> list[float] | None:
        if self._embedding_unavailable:
            return None
        if self._embedding_provider is None:
            try:
                from ..ai.factory import get_embedding_provider

                self._embedding_provider = get_embedding_provider()
            except Exception:
                self._embedding_unavailable = True
                return None
        try:
            return self._embedding_provider.embed([query])[0]
        except Exception as exc:
            logger.warning("Tyto: embeddings no disponibles (%s)", type(exc).__name__)
            self._embedding_unavailable = True
            return None


def _lexical_score(query: str, content: str) -> float:
    """Scoring léxico simple (fallback sin embeddings): overlap de tokens."""
    q_tokens = {t for t in re.findall(r"\w+", query.lower()) if len(t) > 2}
    if not q_tokens:
        return 0.0
    c_tokens = set(re.findall(r"\w+", content.lower()))
    return len(q_tokens & c_tokens) / len(q_tokens)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
