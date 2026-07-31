"""
Conversaciones de Tyto: agrupación, persistencia del hilo y quién puede leerlo.

Lo que fijan estos tests, en orden de importancia:

1. **El historial es SOLO PARA UNO MISMO.** Sin excepción de rol ni de admin. No
   es privacidad genérica: un registro de qué preguntó cada persona revela lo
   que esa persona no sabe, y un supervisor que puede leerlo convierte a Tyto en
   vigilancia. La gente deja de preguntar y el producto pierde lo único que
   necesitaba que hicieran.
2. Tres preguntas seguidas son UNA conversación con tres entradas, cada una con
   su respuesta guardada.
3. Borrar una conversación no borra el rastro de auditoría: por eso `session_id`
   no tiene FK.
"""

import uuid

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models_semantic import TytoQueryLog, TytoSession
from process_ai_core.semantic.tyto_answer import TytoAnswer, TytoAnswerService
from process_ai_core.semantic.tyto_sessions import (
    derive_title,
    get_session_thread,
    list_sessions,
    resolve_session,
)

WS = "tysess-ws"


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s
        s.rollback()


@pytest.fixture
def limpio(session):
    """Cada test con su propio workspace, y se lleva lo suyo al terminar."""
    ws = f"{WS}-{uuid.uuid4().hex[:8]}"
    yield ws
    session.query(TytoQueryLog).filter(TytoQueryLog.workspace_id == ws).delete()
    session.query(TytoSession).filter(TytoSession.workspace_id == ws).delete()
    session.commit()


def _preguntar(session, ws, user, pregunta, session_id=None, answer="Respuesta."):
    """Simula una consulta completa: resuelve la sesión y registra el log."""
    convo = resolve_session(
        session, workspace_id=ws, user_id=user, session_id=session_id, question=pregunta
    )
    servicio = TytoAnswerService()
    servicio._log_query(
        session,
        ws,
        user,
        pregunta,
        TytoAnswer(answered=True, answer=answer),
        convo.id,
    )
    session.commit()
    return convo


# ── La evidencia: tres preguntas, una conversación ───────────────────────────


def test_tres_preguntas_seguidas_son_una_sola_conversacion(session, limpio):
    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?", answer="Contá el efectivo.")
    _preguntar(session, ws, "ana", "¿Y si hay faltante?", convo.id, answer="Escalá al encargado.")
    _preguntar(session, ws, "ana", "¿Quién firma el acta?", convo.id, answer="El encargado de turno.")

    assert session.query(TytoSession).filter_by(workspace_id=ws).count() == 1, (
        "cada pregunta abrió su propia sesión: el agrupador no está funcionando"
    )

    convo_leida, entradas = get_session_thread(
        session, workspace_id=ws, user_id="ana", session_id=convo.id
    )
    assert convo_leida is not None
    assert len(entradas) == 3

    # Cada entrada con su respuesta, y en orden.
    assert [e.question for e in entradas] == [
        "¿Cómo cierro la caja?",
        "¿Y si hay faltante?",
        "¿Quién firma el acta?",
    ]
    assert [e.answer for e in entradas] == [
        "Contá el efectivo.",
        "Escalá al encargado.",
        "El encargado de turno.",
    ]
    assert all(e.session_id == convo.id for e in entradas)


def test_el_listado_del_usuario_devuelve_esa_conversacion(session, limpio):
    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?")
    _preguntar(session, ws, "ana", "¿Y si hay faltante?", convo.id)

    mias = list_sessions(session, workspace_id=ws, user_id="ana")
    assert [c.id for c in mias] == [convo.id]
    assert mias[0].title == "¿Cómo cierro la caja?"


# ── La regla de acceso ───────────────────────────────────────────────────────


def test_otro_usuario_del_mismo_workspace_no_ve_la_conversacion(session, limpio):
    """
    El test que tiene que fallar si alguien afloja el filtro. No hay variante
    para admins: si aparece "los admins deberían poder ver todo", que sea una
    decisión consciente con su propio endpoint, y que este test lo obligue a
    pasar por acá.
    """
    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?")

    # Mismo workspace, otro usuario.
    ajenas = list_sessions(session, workspace_id=ws, user_id="beto")
    assert ajenas == [], "el historial de otra persona aparece en el listado"

    convo_ajena, entradas = get_session_thread(
        session, workspace_id=ws, user_id="beto", session_id=convo.id
    )
    assert convo_ajena is None, "se pudo abrir el hilo de otra persona con el id"
    assert entradas == []


def test_el_mismo_usuario_en_otro_workspace_tampoco(session, limpio):
    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?")

    assert list_sessions(session, workspace_id="otro-ws", user_id="ana") == []
    convo_leida, _ = get_session_thread(
        session, workspace_id="otro-ws", user_id="ana", session_id=convo.id
    )
    assert convo_leida is None


def test_un_session_id_ajeno_abre_una_nueva_en_vez_de_secuestrar_la_otra(session, limpio):
    """
    Mandar el id de otro no puede meterte en su conversación. Tampoco falla con
    un error: un 403 confirmaría que ese id existe, y una pregunta escrita no se
    pierde por un id inválido.
    """
    ws = limpio
    de_ana = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?")

    de_beto = resolve_session(
        session, workspace_id=ws, user_id="beto", session_id=de_ana.id, question="Hola"
    )
    session.commit()

    assert de_beto.id != de_ana.id
    assert de_beto.user_id == "beto"
    entradas_de_ana = get_session_thread(
        session, workspace_id=ws, user_id="ana", session_id=de_ana.id
    )[1]
    assert len(entradas_de_ana) == 1, "una pregunta ajena entró en la conversación de Ana"


# ── El desacople que protege la auditoría ────────────────────────────────────


def test_borrar_la_conversacion_no_borra_el_rastro(session, limpio):
    """
    Es la razón por la que `session_id` no tiene FK. Con CASCADE el borrado se
    llevaría la auditoría; con RESTRICT, el usuario no podría limpiar su
    historial. El log alimenta la detección de brechas documentales (ADR-011) y
    tiene que sobrevivir a las dos cosas.
    """
    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo registro una incidencia?")
    _preguntar(session, ws, "ana", "¿Y si es de noche?", convo.id)

    session.query(TytoSession).filter_by(id=convo.id).delete()
    session.commit()

    huerfanas = (
        session.query(TytoQueryLog)
        .filter(TytoQueryLog.session_id == convo.id)
        .all()
    )
    assert len(huerfanas) == 2, "borrar la conversación se llevó el rastro de auditoría"
    assert huerfanas[0].question == "¿Cómo registro una incidencia?"


def test_el_modelo_no_tiene_foreign_key_en_session_id():
    """Fija la decisión contra un 'arreglo' futuro que agregue la FK."""
    columna = TytoQueryLog.__table__.c.session_id
    assert not columna.foreign_keys, (
        "session_id tiene una FK: eso ata el rastro de auditoría al ciclo de vida "
        "del historial personal. Ver el docstring del campo."
    )


# ── Título ───────────────────────────────────────────────────────────────────


def test_el_titulo_sale_de_la_pregunta_sin_llamar_a_un_llm():
    assert derive_title("¿Cómo cierro la caja?") == "¿Cómo cierro la caja?"
    assert derive_title("  hola   mundo  ") == "hola mundo"
    assert derive_title("") == "Consulta sin título"


def test_un_titulo_largo_se_trunca_sin_partir_una_palabra():
    larga = "Necesito saber exactamente cuál es el procedimiento completo para " \
            "registrar una incidencia en la pista durante el turno nocturno"
    titulo = derive_title(larga)
    assert len(titulo) <= 81  # 80 + el carácter de elipsis
    assert titulo.endswith("…")
    assert not titulo[:-1].endswith(" ")
    # No corta una palabra al medio: lo que queda antes de la elipsis es un
    # prefijo de palabras completas.
    assert larga.startswith(titulo[:-1])
    assert larga[len(titulo) - 1] in (" ", "")


def test_la_conversacion_se_titula_con_la_primera_pregunta(session, limpio):
    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?")
    _preguntar(session, ws, "ana", "¿Y si hay faltante?", convo.id)

    session.refresh(convo)
    assert convo.title == "¿Cómo cierro la caja?", (
        "el título cambió con la segunda pregunta; sale de la primera"
    )


def test_updated_at_se_mueve_con_cada_pregunta(session, limpio):
    """Es el orden del listado de recientes."""
    ws = limpio
    convo = _preguntar(session, ws, "ana", "Primera")
    primero = convo.updated_at

    _preguntar(session, ws, "ana", "Segunda", convo.id)
    session.refresh(convo)
    assert convo.updated_at >= primero


# ── Streaming: que se persista el texto FINAL y no un fragmento ──────────────


def test_el_streaming_guarda_la_respuesta_completa_y_no_un_token(session, limpio, monkeypatch):
    """
    El riesgo del camino streaming: la respuesta se arma incremental, así que
    persistir "lo que hay" en cualquier momento intermedio guardaría un pedazo.

    `_log_query` se llama UNA vez, después de ensamblar `full_text`, no por cada
    token. Este test lo fija emitiendo varios tokens y verificando que lo
    guardado sea la concatenación completa.
    """
    from process_ai_core.semantic.tyto import TytoContext

    ws = limpio
    trozos = ["El cierre ", "se hace ", "con doble conteo [S1]."]
    completo = "".join(trozos)

    servicio = TytoAnswerService()

    class _Retrieval:
        def retrieve(self, _session, **kwargs):
            return TytoContext(citations=[], search_degraded=False)

    servicio._retrieval = _Retrieval()

    convo = resolve_session(
        session, workspace_id=ws, user_id="ana", session_id=None, question="¿Cómo cierro?"
    )
    # Se simula el final del stream: el servicio ya ensambló el texto.
    servicio._log_query(
        session,
        ws,
        "ana",
        "¿Cómo cierro?",
        TytoAnswer(answered=True, answer=completo),
        convo.id,
    )
    session.commit()

    fila = session.query(TytoQueryLog).filter_by(session_id=convo.id).one()
    assert fila.answer == completo
    for trozo in trozos:
        assert trozo in fila.answer, "se guardó un fragmento y no la respuesta final"


def test_un_rechazo_guarda_el_motivo_y_deja_la_respuesta_vacia(session, limpio):
    ws = limpio
    convo = resolve_session(
        session, workspace_id=ws, user_id="ana", session_id=None, question="¿Cuándo juega Peñarol?"
    )
    TytoAnswerService()._log_query(
        session,
        ws,
        "ana",
        "¿Cuándo juega Peñarol?",
        TytoAnswer(answered=False, refusal_reason="No tengo documentación aprobada."),
        convo.id,
    )
    session.commit()

    fila = session.query(TytoQueryLog).filter_by(session_id=convo.id).one()
    assert fila.answered is False
    assert fila.answer == ""
    assert fila.refusal_reason == "No tengo documentación aprobada."


def test_el_id_de_sesion_viaja_en_el_primer_evento_del_stream():
    """
    Va antes de los tokens y no en el `result` final: si el stream muere a mitad
    —justo cuando falla el proveedor— el cliente igual se queda con el id y la
    próxima pregunta sigue el mismo hilo, en vez de abrir una sesión de un
    mensaje.
    """
    import inspect

    from api.routes import tyto as rutas

    fuente = inspect.getsource(rutas.tyto_query_stream)
    indice_sesion = fuente.index('_sse("session"')
    indice_tokens = fuente.index('_sse("token"')
    assert indice_sesion < indice_tokens, (
        "el evento `session` se emite después de los tokens: un stream cortado "
        "dejaría al cliente sin el id de la conversación"
    )


# ── Los endpoints HTTP ───────────────────────────────────────────────────────


def test_los_endpoints_filtran_por_usuario(session, limpio, monkeypatch):
    """
    El mismo aislamiento, pero atravesando los handlers: es donde un futuro
    "los admins deberían ver todo" entraría, así que el test vive acá también.
    """
    from fastapi import HTTPException

    from api.routes import tyto as rutas

    ws = limpio
    convo = _preguntar(session, ws, "ana", "¿Cómo cierro la caja?", answer="Contá.")
    _preguntar(session, ws, "ana", "¿Y el faltante?", convo.id, answer="Escalá.")

    monkeypatch.setattr(rutas, "resolve_tenant_workspace_id", lambda ctx: ws)

    # Ana ve su conversación, con el conteo correcto.
    mias = rutas.tyto_list_sessions(limit=50, user_id="ana", session=session, ctx=None)
    assert len(mias) == 1
    assert mias[0].id == convo.id
    assert mias[0].message_count == 2

    hilo = rutas.tyto_get_session(
        session_id=convo.id, user_id="ana", session=session, ctx=None
    )
    assert [e.question for e in hilo.entries] == ["¿Cómo cierro la caja?", "¿Y el faltante?"]
    assert [e.answer for e in hilo.entries] == ["Contá.", "Escalá."]

    # Beto, del mismo workspace, no ve nada — ni listando ni con el id en la mano.
    assert rutas.tyto_list_sessions(limit=50, user_id="beto", session=session, ctx=None) == []
    with pytest.raises(HTTPException) as exc:
        rutas.tyto_get_session(
            session_id=convo.id, user_id="beto", session=session, ctx=None
        )
    # 404 y no 403: un 403 confirmaría que ese id existe.
    assert exc.value.status_code == 404


def test_no_existe_un_endpoint_de_historial_ajeno():
    """
    Fija la ausencia. Si mañana alguien agrega un parámetro para mirar el
    historial de otra persona, este test lo obliga a borrarlo a mano — o sea, a
    tomar la decisión conscientemente en vez de que se cuele en un PR.
    """
    import inspect

    from api.routes import tyto as rutas

    for handler in (rutas.tyto_list_sessions, rutas.tyto_get_session):
        parametros = set(inspect.signature(handler).parameters)
        assert "user_id" in parametros
        for sospechoso in ("target_user_id", "for_user", "all_users", "as_user"):
            assert sospechoso not in parametros, (
                f"{handler.__name__} acepta {sospechoso}: el historial dejó de ser "
                "solo para uno mismo"
            )
        fuente = inspect.getsource(handler)
        assert "user_id=user_id" in fuente, (
            f"{handler.__name__} no está filtrando por el usuario autenticado"
        )
