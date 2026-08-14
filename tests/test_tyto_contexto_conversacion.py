"""Una repregunta tiene que entenderse en el hilo donde se hizo.

El bug real, encontrado recorriendo el flujo en test: se le preguntaba a Tyto
"¿qué verifico antes de descargar un camión cisterna?" —contestaba bien, citando
el procedimiento— y a la repregunta "¿y si esa diferencia supera el límite?"
respondía que no estaba en los datos. La misma pregunta escrita entera sí se
respondía. O sea: guardábamos el historial pero no lo usábamos, y "retomar una
conversación" no servía para nada.

Lo que fijan estos tests es el reparto de responsabilidades del arreglo:
la conversación previa entra a la BÚSQUEDA (para recuperar el chunk correcto) y
al PROMPT (para resolver a qué se refiere "esa diferencia"), pero **nunca** como
fuente: los hechos siguen saliendo solo de los documentos.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.models_semantic import TytoQueryLog, TytoSession
from process_ai_core.semantic.tyto_answer import (
    CONVERSATION_BLOCK_END,
    CONVERSATION_BLOCK_START,
    DATA_BLOCK_START,
    MAX_TURNOS_CONTEXTO,
    QUESTION_BLOCK_START,
    TytoAnswerService,
    TytoSource,
)
from process_ai_core.semantic.tyto_sessions import turnos_previos


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _fuente() -> TytoSource:
    return TytoSource(
        source_id="S1", document_id=_uid(), document_name="Recepción de combustible",
        document_version_id=_uid(), chunk_id=_uid(), section_title="Desarrollo",
        content="Si la diferencia supera el 0,5 %, no firmar el remito.", score=0.9,
    )


# ── La consulta con la que se busca ─────────────────────────────────────────

def test_una_repregunta_busca_con_los_terminos_del_turno_anterior():
    """"¿Y si se pasa?" no tiene con qué recuperar nada por sí sola."""
    consulta = TytoAnswerService.consulta_para_retrieval(
        "¿Y si esa diferencia se pasa del límite?",
        [("¿Qué verifico al recibir un camión cisterna?", "Hay que medir la varilla.")],
    )
    assert "camión cisterna" in consulta
    assert "se pasa del límite" in consulta


def test_la_pregunta_actual_manda_sobre_el_contexto_viejo():
    """Si el usuario cambia de tema en el mismo hilo, los términos nuevos van
    primero: el contexto anterior desempata, no arrastra."""
    consulta = TytoAnswerService.consulta_para_retrieval(
        "¿Cómo cierro la caja?", [("¿Qué verifico al recibir combustible?", "R")]
    )
    assert consulta.startswith("¿Cómo cierro la caja?")


def test_sin_historial_se_busca_exactamente_lo_que_se_pregunto():
    pregunta = "¿Cómo cierro la caja?"
    assert TytoAnswerService.consulta_para_retrieval(pregunta, None) == pregunta
    assert TytoAnswerService.consulta_para_retrieval(pregunta, []) == pregunta


def test_no_se_arrastran_las_respuestas_a_la_busqueda():
    """Una respuesta larga inundaría la consulta con su propio texto y recuperaría
    los chunks que ya se habían usado."""
    consulta = TytoAnswerService.consulta_para_retrieval(
        "¿Y después?", [("¿Qué mido?", "Hay que medir la varilla del tanque antes.")]
    )
    assert "varilla" not in consulta


def test_una_conversacion_larga_no_arrastra_todo_el_hilo():
    historial = [(f"pregunta {i}", "r") for i in range(10)]
    consulta = TytoAnswerService.consulta_para_retrieval("¿Y eso?", historial)
    assert "pregunta 9" in consulta
    assert "pregunta 0" not in consulta
    assert consulta.count("pregunta ") == MAX_TURNOS_CONTEXTO


# ── Lo que ve el modelo ─────────────────────────────────────────────────────

def test_la_conversacion_previa_va_en_su_propio_bloque_delimitado():
    svc = TytoAnswerService()
    _, user = svc.build_prompt(
        "¿Y si se pasa?", [_fuente()],
        historial=[("¿Qué verifico?", "Hay que medir la varilla.")],
    )
    assert CONVERSATION_BLOCK_START in user and CONVERSATION_BLOCK_END in user
    assert "Hay que medir la varilla." in user
    # Va ANTES de las fuentes y de la pregunta, y por fuera del bloque de datos:
    # el historial no puede confundirse con documentación citable.
    assert user.index(CONVERSATION_BLOCK_END) < user.index(DATA_BLOCK_START)
    assert user.index(DATA_BLOCK_START) < user.index(QUESTION_BLOCK_START)


def test_sin_historial_el_prompt_no_cambia():
    svc = TytoAnswerService()
    _, user = svc.build_prompt("¿Qué verifico?", [_fuente()])
    assert CONVERSATION_BLOCK_START not in user
    assert user.startswith(DATA_BLOCK_START)


def test_el_system_prompt_prohibe_usar_la_conversacion_como_fuente():
    """Sin esta regla, Tyto podría citar como documentación algo que dijo él
    mismo dos turnos atrás — y ahí se cae toda la garantía de groundedness."""
    from process_ai_core.semantic.tyto_answer import SYSTEM_PROMPT, SYSTEM_PROMPT_STREAM

    for prompt in (SYSTEM_PROMPT, SYSTEM_PROMPT_STREAM):
        assert "CONVERSACIÓN PREVIA" in prompt
        assert "ninguna afirmación puede apoyarse en él" in prompt
        assert "Los hechos salen únicamente de DATOS" in prompt


# ── De dónde sale el historial ──────────────────────────────────────────────

def _log(session, sid, pregunta, respuesta, *, answered=True):
    session.add(TytoQueryLog(
        id=_uid(), workspace_id="ws", user_id="u", session_id=sid,
        question=pregunta, answered=answered, answer=respuesta, sources_json="[]",
    ))
    session.commit()


def test_los_turnos_vuelven_del_mas_viejo_al_mas_nuevo(session):
    sid = _uid()
    session.add(TytoSession(id=sid, workspace_id="ws", user_id="u", title="t"))
    session.commit()
    _log(session, sid, "primera", "r1")
    _log(session, sid, "segunda", "r2")

    assert [p for p, _ in turnos_previos(session, session_id=sid)] == ["primera", "segunda"]


def test_no_se_arrastran_los_turnos_que_tyto_no_pudo_responder(session):
    """Arrastrar un "no tengo documentación para eso" ensucia la búsqueda y le
    sugiere al modelo que el tema no está documentado."""
    sid = _uid()
    session.add(TytoSession(id=sid, workspace_id="ws", user_id="u", title="t"))
    session.commit()
    _log(session, sid, "sin respuesta", "", answered=False)
    _log(session, sid, "con respuesta", "r")

    assert [p for p, _ in turnos_previos(session, session_id=sid)] == ["con respuesta"]


def test_no_se_mezclan_los_turnos_de_otra_conversacion(session):
    a, b = _uid(), _uid()
    for sid in (a, b):
        session.add(TytoSession(id=sid, workspace_id="ws", user_id="u", title="t"))
    session.commit()
    _log(session, a, "de la conversación A", "r")
    _log(session, b, "de la conversación B", "r")

    assert [p for p, _ in turnos_previos(session, session_id=a)] == ["de la conversación A"]
