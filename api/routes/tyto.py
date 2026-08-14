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
import tempfile
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from process_ai_core.ai.factory import get_transcription_provider
from process_ai_core.ai.openai_provider import AIProviderError
from process_ai_core.semantic import TytoAnswerService
from process_ai_core.db.models import Document
from process_ai_core.db.models_semantic import TytoQueryLog
from process_ai_core.db.permissions import build_permission_context
from process_ai_core.semantic.tyto_sessions import (
    get_session_thread,
    list_sessions,
    resolve_session,
    delete_session,    update_session,

)
from process_ai_core.semantic.tyto_answer import TytoAnswerError

from ..dependencies import get_current_user_id, get_db
from ..workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    require_process_ai_access,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)
from ..request_identity import capture_request_identity

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/tyto",
    tags=["tyto"],
    dependencies=[
        Depends(sync_workspace_access),
        Depends(capture_request_identity),
        Depends(require_process_ai_access),
    ],
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
    #: Las fuentes citadas, como se devolvieron al responder. Se guardaban desde
    #: siempre en `sources_json` pero el hilo no las traía, y sin ellas retomar
    #: una conversación pierde la mitad: se ve qué contestó Tyto, no de qué
    #: documento salió ni cómo volver a él.
    sources: list[dict] = []
    created_at: str


class TytoThreadResponse(BaseModel):
    session: TytoSessionResponse
    entries: list[TytoThreadEntryResponse]


#: Ventana de las sugerencias. Lo que se preguntaba hace un año no representa
#: lo que la gente necesita hoy, y el proceso pudo haber cambiado.
VENTANA_SUGERENCIAS_DIAS = 90

#: Tope de filas a considerar. El agregado se hace en memoria a propósito
#: (`sources_json` es JSON y se parsea en Python, no en SQL): con este techo el
#: costo es constante y no depende de cuánto creció el log.
MAX_FILAS_SUGERENCIAS = 2000


def _document_ids_de_fuentes(sources_json: str | None) -> list[str]:
    """Los `document_id` citados por una respuesta."""
    return [
        f["document_id"]
        for f in _parse_sources(sources_json)
        if isinstance(f, dict) and f.get("document_id")
    ]


def _parse_sources(sources_json: str | None) -> list[dict]:
    """Las fuentes guardadas. Un JSON roto no puede tumbar el historial."""
    if not sources_json:
        return []
    try:
        datos = json.loads(sources_json)
    except (TypeError, ValueError):
        logger.warning("sources_json inválido en el log de Tyto; se omite")
        return []
    return datos if isinstance(datos, list) else []


class TytoSessionUpdateRequest(BaseModel):
    """Renombrar y/o anclar. Ambos opcionales: se manda solo lo que cambia."""

    title: Optional[str] = None
    pinned: Optional[bool] = None


@router.get("/sessions", response_model=list[TytoSessionResponse])
def tyto_list_sessions(
    limit: int = Query(50, ge=1, le=200),
    q: Optional[str] = Query(
        None,
        max_length=200,
        description="Busca en el título y en las preguntas de la conversación",
    ),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Mis conversaciones en este workspace. Solo mías: ver la nota de arriba."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    # `q` puede llegar como el objeto Query() cuando el endpoint se invoca sin
    # FastAPI (tests que lo llaman como función). Misma normalización que hace
    # `workspace_client._normalize_active_tenant_id` con los Header().
    buscar = q if isinstance(q, str) else None
    convos = list_sessions(
        session, workspace_id=workspace_id, user_id=user_id, limit=limit, buscar=buscar
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
                sources=_parse_sources(e.sources_json),
                created_at=e.created_at.isoformat(),
            )
            for e in entradas
        ],
    )


@router.patch("/sessions/{session_id}", response_model=TytoSessionResponse)
def tyto_update_session(
    session_id: str,
    request: TytoSessionUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Renombra o ancla una conversación mía. 404 si no es mía (ver arriba)."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    convo = update_session(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        session_id=session_id,
        title=request.title,
        pinned=request.pinned,
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    session.commit()

    total = (
        session.query(func.count(TytoQueryLog.id))
        .filter(TytoQueryLog.session_id == convo.id)
        .scalar()
        or 0
    )
    return TytoSessionResponse(
        id=convo.id,
        title=convo.title,
        pinned=convo.pinned,
        created_at=convo.created_at.isoformat(),
        updated_at=convo.updated_at.isoformat(),
        message_count=total,
    )


@router.delete("/sessions/{session_id}")
def tyto_delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Borra una conversación mía del historial.

    El rastro en `tyto_query_log` NO se borra: queda desligado de la sesión y
    sigue alimentando la detección de brechas documentales, que es agregada y
    anónima. Borrar la conversación es una acción sobre MI vista, no sobre el
    rastro del sistema.
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    if not delete_session(
        session, workspace_id=workspace_id, user_id=user_id, session_id=session_id
    ):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    session.commit()
    return {"deleted": session_id}

# ============================================================
# Consulta desde el piso: preguntar por voz y qué preguntar
# ============================================================

#: Tope del audio de una pregunta. Una pregunta hablada dura segundos; 15 MB es
#: holgado incluso sin comprimir. El límite no es por espacio —el archivo no se
#: guarda— sino porque cada transcripción cuesta plata y sale a un tercero.
MAX_AUDIO_PREGUNTA_BYTES = 15 * 1024 * 1024

#: Formatos que graba un navegador (webm/mp4) más los comunes de un teléfono.
EXTENSIONES_AUDIO_PREGUNTA = {".webm", ".mp4", ".m4a", ".mp3", ".wav", ".ogg", ".aac"}


@router.post("/transcribe")
async def tyto_transcribe(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Convierte una pregunta hablada en texto, para hacérsela a Tyto.

    Existe para el uso desde el piso: quien está en la pista, con guantes o con
    las manos ocupadas, no escribe. Es solo transcripción — no busca ni
    responde—, así que el cliente muestra el texto y decide si lo manda.

    El audio NO se guarda: se transcribe y se descarta. Es la pregunta de una
    persona, no evidencia del proceso; conservarla sería juntar grabaciones de
    voz sin ninguna finalidad que las justifique.
    """
    del user_id  # se exige sesión; la transcripción no depende de quién sea

    nombre = file.filename or "pregunta.webm"
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES_AUDIO_PREGUNTA:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de audio no soportado: {ext or '(sin extensión)'}",
        )

    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El audio está vacío")
    if len(contenido) > MAX_AUDIO_PREGUNTA_BYTES:
        raise HTTPException(status_code=400, detail="El audio es demasiado largo")

    # A disco temporal porque el proveedor recibe una ruta (y puede tener que
    # convertir el formato con ffmpeg antes de mandarlo).
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(contenido)
        ruta = tmp.name
    try:
        texto = get_transcription_provider().transcribe(ruta)
    except Exception as exc:
        logger.warning("Falló la transcripción de la pregunta: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502, detail="No se pudo transcribir el audio"
        ) from exc
    finally:
        Path(ruta).unlink(missing_ok=True)

    return {"text": (texto or "").strip()}


class TytoSugerenciaResponse(BaseModel):
    question: str
    veces: int


@router.get("/suggestions", response_model=list[TytoSugerenciaResponse])
def tyto_suggestions(
    limit: int = Query(6, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Qué suele preguntar la gente sobre los documentos que ESTE usuario puede ver.

    Para quien abre Tyto sin saber qué preguntar, que es el caso normal en el
    piso: una pantalla en blanco con un cursor no invita a nada.

    Dos propiedades que lo hacen aceptable, y que no son negociables:

    - **Agregado y anónimo.** Se cuenta la pregunta, nunca quién la hizo. El
      historial personal es de cada uno (ver la nota de arriba); esto es otra
      cosa: el uso del workspace, sin dueño.
    - **Acotado a lo que este usuario puede ver.** Una pregunta se propone solo
      si las fuentes que la respondieron están en carpetas a las que el usuario
      tiene acceso. Sin ese filtro, el listado de sugerencias sería un canal
      lateral para enterarse de qué documentos existen en carpetas ajenas.

    Solo se consideran preguntas que Tyto SÍ pudo responder: sugerir algo que
    va a terminar en "no encuentro esa información" es peor que no sugerir nada.
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    perm_ctx = build_permission_context(
        session, user_id, workspace_id, "superadmin" in (ctx.platform_roles or [])
    )

    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=VENTANA_SUGERENCIAS_DIAS)
    filas = (
        session.query(TytoQueryLog)
        .filter(
            TytoQueryLog.workspace_id == workspace_id,
            TytoQueryLog.answered.is_(True),
            TytoQueryLog.created_at >= desde,
        )
        .order_by(TytoQueryLog.created_at.desc())
        .limit(MAX_FILAS_SUGERENCIAS)
        .all()
    )

    # Carpeta de cada documento citado, en una query (no una por fila).
    doc_ids = {
        d for f in filas for d in _document_ids_de_fuentes(f.sources_json)
    }
    carpeta_por_doc = dict(
        session.query(Document.id, Document.folder_id).filter(Document.id.in_(doc_ids))
    ) if doc_ids else {}

    conteo: dict[str, dict] = {}
    for fila in filas:
        citados = _document_ids_de_fuentes(fila.sources_json)
        if not citados:
            continue
        # TODAS las fuentes tienen que ser visibles: alcanza con una carpeta
        # vedada para que la pregunta revele algo de esa carpeta.
        if not all(
            perm_ctx.can_view_folder(carpeta_por_doc.get(d)) for d in citados
        ):
            continue
        clave = " ".join((fila.question or "").lower().split())
        if not clave:
            continue
        entrada = conteo.setdefault(clave, {"question": fila.question.strip(), "veces": 0})
        entrada["veces"] += 1

    top = sorted(conteo.values(), key=lambda e: (-e["veces"], e["question"]))[:limit]
    return [TytoSugerenciaResponse(**e) for e in top]

