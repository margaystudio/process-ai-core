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
from datetime import datetime

from sqlalchemy.orm import Session

from ..db.database import get_db_session
from ..db.models import Document, DocumentVersion
from .chunking import ChunkIndexService
from .extraction import SemanticExtractionService
from .relations import RelationService

logger = logging.getLogger(__name__)


def _record_run(
    bind,
    *,
    document_id: str,
    version_id: str | None,
    workspace_id: str,
    status: str,
    stage: str,
    error: str | None,
    candidates: int | None,
    chunks: int | None,
    started: datetime,
    trigger: str,
) -> None:
    """Registra la corrida en semantic_pipeline_runs usando una sesión propia
    (bound al mismo engine) para que el rastro persista aunque la sesión del
    pipeline quede en mal estado. Best-effort: nunca rompe el pipeline."""
    from sqlalchemy.orm import Session as _Session

    from ..db.models_semantic import SemanticPipelineRun

    try:
        with _Session(bind=bind) as rec:
            rec.add(
                SemanticPipelineRun(
                    document_id=document_id,
                    version_id=version_id,
                    workspace_id=workspace_id,
                    status=status,
                    stage=stage,
                    error=error,
                    candidates_created=candidates,
                    chunks_indexed=chunks,
                    trigger=trigger,
                    started_at=started,
                    finished_at=datetime.utcnow(),
                )
            )
            rec.commit()
    except Exception:  # pragma: no cover - defensivo
        logger.exception(
            "No se pudo registrar SemanticPipelineRun (doc=%s)", document_id
        )


def run_semantic_pipeline(
    session: Session,
    *,
    document: Document,
    version: DocumentVersion,
    extraction_service: SemanticExtractionService | None = None,
    relation_service: RelationService | None = None,
    chunk_service: ChunkIndexService | None = None,
    index_chunks: bool = True,
    trigger: str = "approval",
) -> dict:
    """Corre extracción → candidatas (→ indexado) para una versión aprobada.

    Loguea cada etapa (con document_id/version_id/workspace_id) y registra la
    corrida en `semantic_pipeline_runs` (status/stage/error), para que un fallo del
    pipeline best-effort sea diagnosticable. Re-lanza la excepción: el hook de
    aprobación la captura sin voltear la aprobación (ver trigger_semantic_pipeline_for_version);
    POST /relations/suggest la propaga como 500 al re-disparo manual.

    `trigger`: "approval" (hook post-aprobación) | "manual" (POST /relations/suggest).
    Devuelve {"candidates_created": int, "chunks_indexed": int}.
    """
    extraction_service = extraction_service or SemanticExtractionService()
    relation_service = relation_service or RelationService()

    # Ids planos (para el registro con sesión propia, sin depender del ORM ligado).
    doc_id, ver_id, ws_id = document.id, version.id, document.workspace_id
    bind = session.get_bind()
    started = datetime.utcnow()
    stage = "extraction"

    try:
        logger.info(
            "semantic pipeline START doc=%s version=%s ws=%s trigger=%s",
            doc_id, ver_id, ws_id, trigger,
        )

        content = version.content_markdown or ""
        extraction = extraction_service.extract(title=document.name, content=content)
        logger.info("semantic[extraction] OK doc=%s version=%s ws=%s", doc_id, ver_id, ws_id)

        stage = "candidates"
        created = relation_service.generate_candidates(
            session, document=document, version=version, extraction=extraction
        )
        logger.info(
            "semantic[candidates] OK doc=%s version=%s ws=%s: %d nuevas",
            doc_id, ver_id, ws_id, len(created),
        )

        stage = "chunking"
        chunks_indexed = 0
        if index_chunks and version.version_status == "APPROVED":
            chunk_service = chunk_service or ChunkIndexService()
            chunks_indexed = len(chunk_service.index_version(session, version))
        logger.info(
            "semantic[chunking] OK doc=%s version=%s ws=%s: %d chunks",
            doc_id, ver_id, ws_id, chunks_indexed,
        )

        _record_run(
            bind, document_id=doc_id, version_id=ver_id, workspace_id=ws_id,
            status="ok", stage="done", error=None, candidates=len(created),
            chunks=chunks_indexed, started=started, trigger=trigger,
        )
        logger.info(
            "semantic pipeline OK doc=%s version=%s: %d candidatas nuevas, %d chunks",
            doc_id, ver_id, len(created), chunks_indexed,
        )
        return {"candidates_created": len(created), "chunks_indexed": chunks_indexed}

    except Exception as exc:
        logger.exception(
            "semantic pipeline FALLÓ stage=%s doc=%s version=%s ws=%s",
            stage, doc_id, ver_id, ws_id,
        )
        _record_run(
            bind, document_id=doc_id, version_id=ver_id, workspace_id=ws_id,
            status="error", stage=stage, error=f"{type(exc).__name__}: {exc}",
            candidates=None, chunks=None, started=started, trigger=trigger,
        )
        raise


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
