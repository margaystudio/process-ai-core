"""Endpoint de la capa de respuesta de Tyto (Fase A — no streaming).

Contrato (spec "Tyto — Capa de respuesta (spec v1)" §3):

- POST /api/v1/tyto/query  body: { question }
  → { answered, answer, segments[{text, source_ids, tier}],
      sources[{source_id, document_id, document_name, version, approved_at, tier}],
      refusal_reason? }

Gate: staff autenticado del workspace activo (mismo gate que el resto de la API:
JWT + sync_workspace_access + workspace del contexto de sesión). La gobernanza
del contenido (solo APPROVED vigente + relaciones confirmadas + aislamiento por
workspace) vive en el retrieval y no se reimplementa acá (ADR-002).

Streaming y pantalla de chat = Fase B.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from process_ai_core.ai.openai_provider import AIProviderError
from process_ai_core.semantic import TytoAnswerService
from process_ai_core.semantic.tyto_answer import TytoAnswerError

from ..dependencies import get_current_user_id, get_db
from ..workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/tyto",
    tags=["tyto"],
    dependencies=[Depends(sync_workspace_access)],
)

MAX_QUESTION_LENGTH = 2000


class TytoQueryRequest(BaseModel):
    question: str


class TytoSegmentResponse(BaseModel):
    text: str
    source_ids: list[str]
    tier: str  # aprobado | referencia | inferido


class TytoSourceResponse(BaseModel):
    source_id: str
    document_id: str
    document_name: str
    version: Optional[int] = None
    approved_at: Optional[str] = None
    tier: str  # aprobado | referencia


class TytoQueryResponse(BaseModel):
    answered: bool
    answer: str = ""
    segments: list[TytoSegmentResponse] = []
    sources: list[TytoSourceResponse] = []
    refusal_reason: Optional[str] = None


def _build_service() -> TytoAnswerService:
    """Factory del servicio (punto único para inyectar fakes en tests)."""
    return TytoAnswerService()


@router.post("/query", response_model=TytoQueryResponse)
async def tyto_query(
    request: TytoQueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Responde una pregunta con documentación aprobada, citada y con niveles 🟢🟡🔴."""
    workspace_id = resolve_tenant_workspace_id(ctx)

    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question es obligatoria")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"question supera el máximo de {MAX_QUESTION_LENGTH} caracteres",
        )

    service = _build_service()
    try:
        result = service.answer(
            session, workspace_id=workspace_id, question=question, user_id=user_id
        )
    except (AIProviderError, TytoAnswerError) as exc:
        # Sin respuesta utilizable NO se improvisa nada: error explícito.
        logger.error("Tyto: fallo generando respuesta: %s", exc)
        raise HTTPException(
            status_code=502, detail="Tyto no pudo generar una respuesta confiable"
        )
    session.commit()  # persiste el TytoQueryLog

    return TytoQueryResponse(
        answered=result.answered,
        answer=result.answer,
        segments=[
            TytoSegmentResponse(text=s.text, source_ids=s.source_ids, tier=s.tier)
            for s in result.segments
        ],
        sources=[
            TytoSourceResponse(
                source_id=s.source_id,
                document_id=s.document_id,
                document_name=s.document_name,
                version=s.version,
                approved_at=s.approved_at,
                tier=s.tier,
            )
            for s in result.sources
        ],
        refusal_reason=result.refusal_reason,
    )
