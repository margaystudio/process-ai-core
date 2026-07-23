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

import json
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
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


def _validate_question(raw: str) -> str:
    question = (raw or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question es obligatoria")
    if len(question) > MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"question supera el máximo de {MAX_QUESTION_LENGTH} caracteres",
        )
    return question


def _to_response(result) -> TytoQueryResponse:
    """Contrato §3 del spec — único para la Fase A y el evento final del stream."""
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


@router.post("/query", response_model=TytoQueryResponse)
async def tyto_query(
    request: TytoQueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Responde una pregunta con documentación aprobada, citada y con niveles 🟢🟡🔴."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    question = _validate_question(request.question)

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

    return _to_response(result)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/query/stream")
async def tyto_query_stream(
    request: TytoQueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Fase B: misma respuesta que /query pero streameada por SSE.

    El streaming es percepción de velocidad, NO relajación de garantías: los
    eventos `token` traen solo el texto (prosa con [Sn] inline); los niveles de
    confianza y las fuentes llegan únicamente en el evento final `result`, tras
    correr el MISMO groundedness guard de la Fase A sobre la salida completa.
    Rechazo → un único evento `result` sin tokens (el LLM no se llama). Salida
    inutilizable del LLM → evento `error` explícito, jamás una respuesta a medias.

    Eventos SSE:
      event: token   data: {"text": "..."}
      event: result  data: <contrato §3, idéntico a POST /query>
      event: error   data: {"detail": "..."}
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    question = _validate_question(request.question)
    service = _build_service()

    def event_stream():
        try:
            for ev in service.answer_stream(
                session, workspace_id=workspace_id, question=question, user_id=user_id
            ):
                if ev["type"] == "token":
                    yield _sse("token", {"text": ev["text"]})
                else:
                    session.commit()  # persiste el TytoQueryLog
                    yield _sse("result", _to_response(ev["answer"]).model_dump())
        except (AIProviderError, TytoAnswerError) as exc:
            logger.error("Tyto: fallo en el stream: %s", exc)
            yield _sse("error", {"detail": "Tyto no pudo generar una respuesta confiable"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
