"""Orquestación del pipeline semántico.

Se dispara al aprobar una versión de documento (hook en las rutas de
validación) o bajo demanda vía POST /documents/{id}/relations/suggest.

    Documento aprobado
      → extracción de entidades (SemanticExtractionService, modelo barato)
      → matching en cascada + relaciones candidatas (RelationService)
      → indexado de chunks + embeddings (ChunkIndexService)

El hook post-aprobación es best-effort: un fallo del pipeline NUNCA voltea la
aprobación (el documento ya quedó aprobado; las sugerencias pueden regenerarse
con /relations/suggest).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db.database import get_db_session
from ..db.models import Document, DocumentVersion
from .chunking import ChunkIndexService
from .extraction import SemanticExtractionService
from .relations import RelationService

logger = logging.getLogger(__name__)


def run_semantic_pipeline(
    session: Session,
    *,
    document: Document,
    version: DocumentVersion,
    extraction_service: SemanticExtractionService | None = None,
    relation_service: RelationService | None = None,
    chunk_service: ChunkIndexService | None = None,
    index_chunks: bool = True,
) -> dict:
    """Corre extracción → candidatas (→ indexado) para una versión aprobada.

    Devuelve un resumen {"candidates_created": int, "chunks_indexed": int}.
    """
    extraction_service = extraction_service or SemanticExtractionService()
    relation_service = relation_service or RelationService()

    content = version.content_markdown or ""
    extraction = extraction_service.extract(title=document.name, content=content)
    created = relation_service.generate_candidates(
        session, document=document, version=version, extraction=extraction
    )

    chunks_indexed = 0
    if index_chunks and version.version_status == "APPROVED":
        chunk_service = chunk_service or ChunkIndexService()
        chunks_indexed = len(chunk_service.index_version(session, version))

    logger.info(
        "Pipeline semántico doc=%s version=%s: %d candidatas nuevas, %d chunks",
        document.id,
        version.id,
        len(created),
        chunks_indexed,
    )
    return {"candidates_created": len(created), "chunks_indexed": chunks_indexed}


def trigger_semantic_pipeline_for_version(version_id: str) -> None:
    """Hook post-aprobación (best-effort, sesión propia).

    Pensado para FastAPI BackgroundTasks: corre después de responder al cliente
    y jamás propaga errores (loguea y sigue).
    """
    try:
        with get_db_session() as session:
            version = session.query(DocumentVersion).filter_by(id=version_id).first()
            if not version:
                logger.warning("Pipeline semántico: versión %s no encontrada", version_id)
                return
            if version.version_status != "APPROVED":
                logger.info(
                    "Pipeline semántico: versión %s no está APPROVED (%s), se omite",
                    version_id,
                    version.version_status,
                )
                return
            document = session.query(Document).filter_by(id=version.document_id).first()
            if not document:
                logger.warning(
                    "Pipeline semántico: documento %s no encontrado", version.document_id
                )
                return
            run_semantic_pipeline(session, document=document, version=version)
    except Exception:
        logger.exception(
            "Pipeline semántico falló para la versión %s (la aprobación no se ve afectada)",
            version_id,
        )
