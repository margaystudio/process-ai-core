"""
Qué puede afirmar Tyto cuando la búsqueda semántica está caída, y qué no.

EL INCIDENTE QUE ESTO FIJA
--------------------------
Con la API key de OpenAI revocada en test, los embeddings fallaban, el retriever
degradaba a coincidencia de palabras sin decírselo a nadie, y Tyto respondía
"No tengo documentación aprobada suficiente para responder esta pregunta". Se leyó
como el sistema funcionando bien.

No lo era. Esa frase afirma algo sobre la BIBLIOTECA DEL CLIENTE —que no hay
documentación aprobada que responda— a partir de una falla de infraestructura
propia. Un usuario podía concluir que le faltaba documentar algo que ya estaba
documentado.

La regla: sin embeddings, "no encontré" deja de significar "no está". El sistema
tiene que decir cuál de las dos cosas está diciendo.
"""

import pytest

from process_ai_core.semantic.tyto import TytoContext, TytoQueryService
from process_ai_core.semantic.tyto_answer import (
    REFUSAL_NO_CONTEXT,
    REFUSAL_SEARCH_DEGRADED,
    TytoAnswer,
    TytoAnswerService,
)


class _RetrievalFalsa:
    """Sustituye al retriever: devuelve el contexto que el test quiere probar."""

    def __init__(self, context: TytoContext) -> None:
        self._context = context

    def retrieve(self, session, **kwargs) -> TytoContext:
        return self._context


def _servicio(context: TytoContext) -> TytoAnswerService:
    service = TytoAnswerService()
    service._retrieval = _RetrievalFalsa(context)
    service._log_query = lambda *a, **k: None
    return service


# ── El rechazo dice cuál de las dos cosas pasó ───────────────────────────────


def test_sin_documentacion_el_rechazo_afirma_ausencia():
    """Búsqueda sana y cero resultados: ahí sí, la afirmación es exacta."""
    service = _servicio(TytoContext(citations=[], search_degraded=False))
    result = service.answer(None, workspace_id="ws", question="¿algo?", user_id="u")

    assert result.answered is False
    assert result.refusal_reason == REFUSAL_NO_CONTEXT
    assert result.search_degraded is False


def test_con_la_busqueda_caida_el_rechazo_no_afirma_ausencia():
    service = _servicio(TytoContext(citations=[], search_degraded=True))
    result = service.answer(None, workspace_id="ws", question="¿algo?", user_id="u")

    assert result.answered is False
    assert result.search_degraded is True
    assert result.refusal_reason == REFUSAL_SEARCH_DEGRADED
    assert result.refusal_reason != REFUSAL_NO_CONTEXT


def test_el_texto_degradado_no_dice_que_no_haya_documentacion():
    """
    Es el corazón del arreglo, así que se afirma sobre el TEXTO: tiene que
    admitir que puede existir documentación y no puede afirmar que no la haya.
    """
    texto = REFUSAL_SEARCH_DEGRADED.lower()
    assert "puede existir" in texto
    assert "no tengo documentación aprobada" not in texto
    # Y tiene que decir POR QUÉ, no solo que algo salió mal.
    assert "semántica" in texto


def test_el_mismo_criterio_en_el_stream():
    service = _servicio(TytoContext(citations=[], search_degraded=True))
    eventos = list(
        service.answer_stream(None, workspace_id="ws", question="¿algo?", user_id="u")
    )
    finales = [e for e in eventos if e["type"] == "result"]
    assert len(finales) == 1
    assert finales[0]["answer"].refusal_reason == REFUSAL_SEARCH_DEGRADED
    assert finales[0]["answer"].search_degraded is True


# ── El retriever marca la degradación ────────────────────────────────────────


def test_sin_embeddings_el_contexto_queda_marcado(monkeypatch):
    service = TytoQueryService()
    monkeypatch.setattr(service, "has_approved_current_versions", lambda *a, **k: True)
    monkeypatch.setattr(service, "_embed_query", lambda query: None)
    monkeypatch.setattr(service, "approved_current_versions", lambda *a, **k: [])
    monkeypatch.setattr(service, "_retrieve_python", lambda *a, **k: [])
    monkeypatch.setattr(
        "process_ai_core.semantic.tyto._pg.vector_search_ready", lambda s: False
    )

    context = service.retrieve(None, workspace_id="ws", query="algo", top_k=5)
    assert context.search_degraded is True


def test_con_embeddings_el_contexto_no_queda_marcado(monkeypatch):
    service = TytoQueryService()
    monkeypatch.setattr(service, "has_approved_current_versions", lambda *a, **k: True)
    monkeypatch.setattr(service, "_embed_query", lambda query: [0.1] * 8)
    monkeypatch.setattr(service, "approved_current_versions", lambda *a, **k: [])
    monkeypatch.setattr(service, "_retrieve_python", lambda *a, **k: [])
    monkeypatch.setattr(
        "process_ai_core.semantic.tyto._pg.vector_search_ready", lambda s: False
    )

    context = service.retrieve(None, workspace_id="ws", query="algo", top_k=5)
    assert context.search_degraded is False


def test_un_workspace_sin_documentacion_no_es_degradacion(monkeypatch):
    """
    Distinguir las dos causas es todo el punto. Que no haya documentación
    aprobada es un hecho del workspace; que no haya embeddings es una falla
    nuestra. No pueden reportarse igual.
    """
    service = TytoQueryService()
    monkeypatch.setattr(service, "has_approved_current_versions", lambda *a, **k: False)

    context = service.retrieve(None, workspace_id="ws", query="algo", top_k=5)
    assert context.citations == []
    assert context.search_degraded is False


# ── El flag llega al contrato de la API ──────────────────────────────────────


def test_la_respuesta_de_la_api_expone_la_degradacion():
    from api.routes.tyto import _to_response

    respuesta = _to_response(
        TytoAnswer(answered=False, refusal_reason="x", search_degraded=True)
    )
    assert respuesta.search_degraded is True

    sano = _to_response(TytoAnswer(answered=False, refusal_reason="x"))
    assert sano.search_degraded is False


# ── /health deja de dar verde con una credencial rechazada ───────────────────
#
# El otro lado del mismo incidente: con la key revocada, `/health` decía
# `"openai_api_key": true` porque comprobaba que la VARIABLE estuviera definida.
# Un chequeo que no puede fallar no es un chequeo.


@pytest.fixture(autouse=True)
def _credencial_limpia():
    """Estado de credencial en memoria: aislarlo entre tests."""
    from process_ai_core.ai import credentials

    original = credentials._estado
    credentials._estado = credentials.CredentialState()
    yield
    credentials._estado = original


def _respuesta_401():
    """httpx.Response mínima: AuthenticationError la desarma en el __init__."""
    import httpx

    return httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/x"))


def _infra(session=None, **overrides):
    from process_ai_core.semantic.preflight import SemanticInfraStatus

    base = dict(
        backend="postgresql", pgvector=True, pg_trgm=True,
        embedding_is_vector=True, openai_api_key=True, allow_degraded=True,
    )
    base.update(overrides)
    return SemanticInfraStatus(**base)


def test_una_credencial_rechazada_es_un_issue():
    estado = _infra(openai_credential={"valid": False, "detail": "AuthenticationError"})
    assert estado.ok is False
    assert any("rechazó la credencial" in i for i in estado.issues)


def test_una_credencial_que_funciona_no_es_issue():
    assert _infra(openai_credential={"valid": True}).ok is True


def test_no_haberla_usado_todavia_no_es_un_fallo():
    """
    En Cloud Run las instancias se apagan sin tráfico: "todavía no se usó" es
    normal y frecuente. Reportarlo como credencial rota sería la misma clase de
    mentira que se está arreglando, en el otro sentido.
    """
    estado = _infra(openai_credential={"valid": None})
    assert estado.ok is True
    assert estado.openai_credential_valid is None


def test_el_estado_se_aprende_del_trafico_real():
    """No cuesta una llamada extra: sale de las que el sistema ya hace."""
    from openai import AuthenticationError

    from process_ai_core.ai import credentials
    from process_ai_core.ai.openai_provider import AIProviderError, _openai_call

    assert credentials.get_credential_state().valid is None

    with pytest.raises(AIProviderError):
        with _openai_call("embeddings.create"):
            raise AuthenticationError("401", response=_respuesta_401(), body=None)
    assert credentials.get_credential_state().valid is False
    assert credentials.get_credential_state().source == "trafico"

    with _openai_call("embeddings.create"):
        pass
    assert credentials.get_credential_state().valid is True


def test_un_rate_limit_no_se_confunde_con_una_key_rota():
    """
    Un 500 o un rate-limit no dicen nada sobre la credencial. Marcarlos como
    fallo de auth haría que un pico de carga se lea como una key vencida, y el
    health perdería el poco valor que acaba de ganar.
    """
    import httpx
    from openai import APIError

    from process_ai_core.ai import credentials
    from process_ai_core.ai.openai_provider import AIProviderError, _openai_call

    with _openai_call("chat"):
        pass
    assert credentials.get_credential_state().valid is True

    with pytest.raises(AIProviderError):
        with _openai_call("chat"):
            raise APIError(
                "boom",
                request=httpx.Request("POST", "https://api.openai.com/v1/x"),
                body=None,
            )
    assert credentials.get_credential_state().valid is True, (
        "un error que no es de autenticación no debe marcar la credencial como rota"
    )
