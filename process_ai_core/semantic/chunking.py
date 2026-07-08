"""Chunking e indexado de versiones aprobadas (RAG de Tyto).

Los chunks pertenecen SIEMPRE a una document_version APPROVED (ADR-002): al
aprobar una versión nueva se reemplazan los chunks de la versión anterior del
documento en el índice activo (la versión vieja queda OBSOLETE y sus chunks se
eliminan; el PDF congelado sigue siendo el artefacto de auditoría).

Los embeddings son opcionales: si el EmbeddingProvider no está configurado los
chunks quedan indexados sin vector y Tyto degrada a scoring léxico.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..db.models import DocumentVersion
from ..db.models_semantic import DocumentChunk

logger = logging.getLogger(__name__)

# Tamaño objetivo de chunk (caracteres) y solapamiento entre chunks contiguos
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    index: int
    content: str
    section_title: str | None = None


def split_markdown_into_chunks(
    markdown: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Divide markdown en chunks de ~chunk_size caracteres respetando secciones.

    Cada heading markdown arranca una sección; dentro de una sección larga se
    corta por párrafos con un pequeño solapamiento para no perder contexto.
    """
    if not markdown or not markdown.strip():
        return []

    # Agrupar líneas por sección (heading actual)
    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m:
            if current_lines and any(l.strip() for l in current_lines):
                sections.append((current_title, current_lines))
            current_title = m.group(2).strip() or None
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines and any(l.strip() for l in current_lines):
        sections.append((current_title, current_lines))

    chunks: list[Chunk] = []
    for title, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        if len(text) <= chunk_size:
            chunks.append(Chunk(index=len(chunks), content=text, section_title=title))
            continue
        # Sección larga: cortar por párrafos acumulando hasta chunk_size
        paragraphs = re.split(r"\n\s*\n", text)
        buffer = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if buffer and len(buffer) + len(para) + 2 > chunk_size:
                chunks.append(Chunk(index=len(chunks), content=buffer, section_title=title))
                buffer = buffer[-overlap:] if overlap else ""
            buffer = f"{buffer}\n\n{para}".strip() if buffer else para
            # Párrafo individual gigante: cortar duro
            while len(buffer) > chunk_size:
                chunks.append(Chunk(index=len(chunks), content=buffer[:chunk_size], section_title=title))
                buffer = buffer[chunk_size - overlap:]
        if buffer.strip():
            chunks.append(Chunk(index=len(chunks), content=buffer, section_title=title))
    return chunks


def embedding_to_literal(vector: list[float]) -> str:
    """Serializa un vector al literal pgvector: "[0.1,0.2,...]" (sin espacios)."""
    return "[" + ",".join(f"{x:.8f}".rstrip("0").rstrip(".") for x in vector) + "]"


def literal_to_embedding(literal: str | None) -> list[float] | None:
    if not literal:
        return None
    stripped = literal.strip().lstrip("[").rstrip("]")
    if not stripped:
        return None
    try:
        return [float(x) for x in stripped.split(",")]
    except ValueError:
        return None


class ChunkIndexService:
    """Indexa document_chunks (+embeddings) para versiones aprobadas."""

    def __init__(self, embedding_provider=None) -> None:
        self._embedding_provider = embedding_provider
        self._embedding_unavailable = False

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

    def index_version(self, session: Session, version: DocumentVersion) -> list[DocumentChunk]:
        """(Re)indexa los chunks de una versión APPROVED.

        Elimina chunks previos de la misma versión y de versiones anteriores del
        mismo documento (solo la versión aprobada vigente forma el índice).
        """
        if version.version_status != "APPROVED":
            raise ValueError(
                f"Solo se indexan versiones APPROVED (versión {version.id}: {version.version_status})"
            )

        # Limpiar índice del documento (versión actual y anteriores)
        old_version_ids = [
            row[0]
            for row in session.query(DocumentVersion.id)
            .filter(DocumentVersion.document_id == version.document_id)
            .all()
        ]
        if old_version_ids:
            (
                session.query(DocumentChunk)
                .filter(DocumentChunk.document_version_id.in_(old_version_ids))
                .delete(synchronize_session=False)
            )

        chunks = split_markdown_into_chunks(version.content_markdown or "")
        if not chunks:
            return []

        embeddings: list[list[float]] | None = None
        provider = self._get_embedding_provider()
        if provider is not None:
            try:
                embeddings = provider.embed([c.content for c in chunks])
            except Exception as exc:
                logger.warning(
                    "Indexado sin embeddings (provider falló: %s)", type(exc).__name__
                )
                embeddings = None

        rows: list[DocumentChunk] = []
        for i, chunk in enumerate(chunks):
            rows.append(
                DocumentChunk(
                    document_version_id=version.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    section_title=chunk.section_title,
                    embedding=(
                        embedding_to_literal(embeddings[i]) if embeddings else None
                    ),
                )
            )
        session.add_all(rows)
        session.flush()
        return rows
