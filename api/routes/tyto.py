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

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from process_ai_core.ai.openai_provider import AIProviderError
from process_ai_core.semantic import TytoAnswerService
from process_ai_core.db.models_semantic import TytoQueryLog
from process_ai_core.semantic.tyto_sessions import (
    get_session_thread,
    list_sessions,
    resolve_session,
)
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
    #: Conversación en curso. Si viene vacío —o si no es del usuario— el servidor
    #: abre una nueva y devuelve su id. Ver process_ai_core/semantic/tyto_sessions.py
    #: para por qué la emite el servidor y no el cliente.
    session_id: Optional[str] = None


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
    #: La búsqueda semántica no estaba disponible y se rankeó por coincidencia de
    #: palabras. La UI lo muestra: un rechazo en ese estado no significa que no
    #: haya documentación, significa que se buscó peor.
    search_degraded: bool = False
    #: Conversación a la que quedó asociada esta pregunta. El cliente la manda de
    #: vuelta en la siguiente para que el hilo no se parta.
    session_id: Optional[str] = None


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


def _to_response(result, session_id: str | None = None) -> TytoQueryResponse:
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
        search_degraded=getattr(result, "search_degraded", False),
        session_id=session_id,
    )


@router.post("/query", response_model=TytoQueryResponse)
def tyto_query(
    request: TytoQueryRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Responde una pregunta con documentación aprobada, citada y con niveles 🟢🟡🔴."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    question = _validate_question(request.question)

    convo = resolve_session(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        session_id=request.session_id,
        question=question,
    )

    service = _build_service()
    try:
        result = service.answer(
            session,
            workspace_id=workspace_id,
            question=question,
            user_id=user_id,
            session_id=convo.id,
        )
    except (AIProviderError, TytoAnswerError) as exc:
        # Sin respuesta utilizable NO se improvisa nada: error explícito.
        logger.error("Tyto: fallo generando respuesta: %s", exc)
        raise HTTPException(
            status_code=502, detail="Tyto no pudo generar una respuesta confiable"
        )
    session.commit()  # persiste el TytoQueryLog y la sesión

    return _to_response(result, convo.id)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/query/stream")
def tyto_query_stream(
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

    convo = resolve_session(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        session_id=request.session_id,
        question=question,
    )
    session.commit()  # la sesión existe aunque después falle la respuesta
    session_id = convo.id

    def event_stream():
        # El id va PRIMERO, antes de cualquier token. Si fuera solo en el
        # `result` final, un stream que muere a mitad —justo cuando falla el
        # proveedor— dejaría al cliente sin id: la próxima pregunta abriría otra
        # conversación y el historial se llenaría de sesiones de un mensaje.
        yield _sse("session", {"session_id": session_id})
        try:
            for ev in service.answer_stream(
                session,
                workspace_id=workspace_id,
                question=question,
                user_id=user_id,
                session_id=session_id,
            ):
                if ev["type"] == "token":
                    yield _sse("token", {"text": ev["text"]})
                else:
                    session.commit()  # persiste el TytoQueryLog
                    yield _sse("result", _to_response(ev["answer"], session_id).model_dump())
        except (AIProviderError, TytoAnswerError) as exc:
            logger.error("Tyto: fallo en el stream: %s", exc)
            yield _sse("error", {"detail": "Tyto no pudo generar una respuesta confiable"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Historial (tarea 4) ──────────────────────────────────────────────────────
#
# REGLA DE ACCESO, EXPLÍCITA Y SIN EXCEPCIONES: el historial es SOLO PARA UNO
# MISMO. Los dos endpoints de acá filtran por `user_id` además de por workspace,
# y NO existe una variante para administradores.
#
# El motivo es de producto, no de privacidad genérica. Un registro de qué
# preguntó cada persona revela lo que esa persona no sabe. Si un supervisor
# puede ver "Juan preguntó doce veces cómo cerrar caja", se construyó una
# herramienta de vigilancia que nadie pidió, y la gente deja de preguntar — que
# es exactamente lo contrario de lo que Tyto necesita que hagan.
#
# Para detectar brechas documentales está `tyto_query_log` agregado y anónimo,
# que para eso es una tabla desacoplada.
#
# Si en algún momento aparece "los admins deberían poder ver todo": que sea una
# decisión consciente, discutida y con su propio endpoint. Hay un test que falla
# si alguien afloja este filtro sin darse cuenta.


class TytoSessionResponse(BaseModel):
    id: str
    title: str
    pinned: bool
    created_at: str
    updated_at: str
    message_count: int = 0


class TytoThreadEntryResponse(BaseModel):
    id: str
    question: str
    answered: bool
    answer: str = ""
    refusal_reason: Optional[str] = None
    created_at: str


class TytoThreadResponse(BaseModel):
    session: TytoSessionResponse
    entries: list[TytoThreadEntryResponse]


@router.get("/sessions", response_model=list[TytoSessionResponse])
def tyto_list_sessions(
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Mis conversaciones en este workspace. Solo mías: ver la nota de arriba."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    convos = list_sessions(
        session, workspace_id=workspace_id, user_id=user_id, limit=limit
    )
    if not convos:
        return []

    # Conteo en UNA query para las N sesiones, no una por sesión.
    conteos = dict(
        session.query(TytoQueryLog.session_id, func.count(TytoQueryLog.id))
        .filter(TytoQueryLog.session_id.in_([c.id for c in convos]))
        .group_by(TytoQueryLog.session_id)
        .all()
    )
    return [
        TytoSessionResponse(
            id=c.id,
            title=c.title,
            pinned=c.pinned,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
            message_count=conteos.get(c.id, 0),
        )
        for c in convos
    ]


@router.get("/sessions/{session_id}", response_model=TytoThreadResponse)
def tyto_get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    El hilo de una conversación mía.

    404 —y no 403— cuando la sesión es de otro: un 403 confirmaría que ese id
    existe, que es justo lo que no se quiere filtrar de un historial ajeno.
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    convo, entradas = get_session_thread(
        session, workspace_id=workspace_id, user_id=user_id, session_id=session_id
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    return TytoThreadResponse(
        session=TytoSessionResponse(
            id=convo.id,
            title=convo.title,
            pinned=convo.pinned,
            created_at=convo.created_at.isoformat(),
            updated_at=convo.updated_at.isoformat(),
            message_count=len(entradas),
        ),
        entries=[
            TytoThreadEntryResponse(
                id=e.id,
                question=e.question,
                answered=e.answered,
                answer=e.answer or "",
                refusal_reason=e.refusal_reason,
                created_at=e.created_at.isoformat(),
            )
            for e in entradas
        ],
    )
