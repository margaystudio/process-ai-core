"""Tyto de consulta: preguntar por voz y saber qué preguntar.

Es la superficie para quien trabaja en el piso —el pistero— y solo consulta.
Lo que fijan estos tests:

1. La transcripción NO guarda el audio: es la pregunta de una persona, no
   evidencia del proceso.
2. Las sugerencias son AGREGADAS y ANÓNIMAS: se cuenta la pregunta, nunca
   quién la hizo.
3. Las sugerencias respetan el permiso por carpeta. Sin ese filtro serían un
   canal lateral para enterarse de qué existe en carpetas ajenas — el mismo
   agujero que se cerró en el retrieval de Tyto.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.models import (
    Document,
    Folder,
    FolderPermission,
    OperationalRole,
    User,
    UserOperationalRole,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.db.models_semantic import TytoQueryLog

from api.routes import tyto as tyto_route


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


@pytest.fixture
def env(session, monkeypatch):
    """Dos carpetas: una abierta y una restringida, con un documento en cada una."""
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(ws)
    session.flush()

    abierta = Folder(id=_uid(), workspace_id=ws.id, name="Pista", path="Pista",
                     inherits_permissions=True)
    restringida = Folder(id=_uid(), workspace_id=ws.id, name="RRHH", path="RRHH",
                         inherits_permissions=False)
    session.add_all([abierta, restringida])
    session.flush()

    rol = OperationalRole(id=_uid(), workspace_id=ws.id, name="RRHH", slug="rrhh",
                          access_level="lectura")
    session.add(rol)
    session.flush()
    session.add(FolderPermission(id=_uid(), folder_id=restringida.id,
                                 operational_role_id=rol.id))

    doc_abierto = Document(id=_uid(), workspace_id=ws.id, folder_id=abierta.id,
                           domain="process", document_type="procedimiento",
                           name="Cierre de caja", status="approved")
    doc_restringido = Document(id=_uid(), workspace_id=ws.id, folder_id=restringida.id,
                               domain="process", document_type="procedimiento",
                               name="Sumarios", status="approved")
    session.add_all([doc_abierto, doc_restringido])
    session.commit()

    monkeypatch.setattr(tyto_route, "resolve_tenant_workspace_id", lambda ctx: ws.id)
    return SimpleNamespace(
        session=session, ws=ws, abierta=abierta, restringida=restringida,
        rol=rol, doc_abierto=doc_abierto, doc_restringido=doc_restringido,
    )


def _miembro(env, *, con_rol=False):
    u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
    env.session.add(u)
    env.session.flush()
    m = WorkspaceMembership(id=_uid(), user_id=u.id, workspace_id=env.ws.id,
                            base_access="member")
    env.session.add(m)
    env.session.flush()
    if con_rol:
        env.session.add(UserOperationalRole(
            id=_uid(), workspace_membership_id=m.id, operational_role_id=env.rol.id
        ))
    env.session.commit()
    return u.id


def _pregunta_registrada(env, texto, doc, *, user_id="quien-sea", veces=1):
    for _ in range(veces):
        env.session.add(TytoQueryLog(
            id=_uid(), workspace_id=env.ws.id, user_id=user_id,
            question=texto, answered=True, answer="Respuesta.",
            sources_json=json.dumps([{"source_id": "S1", "document_id": doc.id}]),
        ))
    env.session.commit()


def _ctx():
    return SimpleNamespace(tenant=SimpleNamespace(id="t1"), platform_roles=[])


def _sugerencias(env, user_id, limit=6):
    return tyto_route.tyto_suggestions(
        limit=limit, user_id=user_id, session=env.session, ctx=_ctx()
    )


# ── Sugerencias: agregado anónimo, acotado por carpeta ──────────────────────

def test_sugiere_lo_mas_preguntado_de_lo_que_puedo_ver(env):
    quien_pregunta = _miembro(env)
    _pregunta_registrada(env, "¿Cómo cierro la caja?", env.doc_abierto, veces=3)
    _pregunta_registrada(env, "¿Dónde firmo el arqueo?", env.doc_abierto, veces=1)

    r = _sugerencias(env, quien_pregunta)
    assert [s.question for s in r] == ["¿Cómo cierro la caja?", "¿Dónde firmo el arqueo?"]
    assert r[0].veces == 3


def test_no_sugiere_preguntas_de_carpetas_que_no_puedo_ver(env):
    """Sin este filtro, las sugerencias serían un canal lateral para enterarse
    de qué documentos existen en carpetas ajenas."""
    sin_acceso = _miembro(env, con_rol=False)
    _pregunta_registrada(env, "¿Cómo se tramita un sumario?", env.doc_restringido, veces=5)
    _pregunta_registrada(env, "¿Cómo cierro la caja?", env.doc_abierto, veces=1)

    r = _sugerencias(env, sin_acceso)
    assert [s.question for s in r] == ["¿Cómo cierro la caja?"]


def test_con_el_rol_operativo_si_aparece_la_de_la_carpeta_restringida(env):
    con_acceso = _miembro(env, con_rol=True)
    _pregunta_registrada(env, "¿Cómo se tramita un sumario?", env.doc_restringido, veces=2)

    r = _sugerencias(env, con_acceso)
    assert [s.question for s in r] == ["¿Cómo se tramita un sumario?"]


def test_la_sugerencia_no_dice_quien_pregunto(env):
    """Agregado y anónimo: el historial personal es de cada uno."""
    otro = _miembro(env)
    quien_mira = _miembro(env)
    _pregunta_registrada(env, "¿Cómo cierro la caja?", env.doc_abierto, user_id=otro)

    r = _sugerencias(env, quien_mira)
    assert r and not any(
        hasattr(s, campo) for s in r for campo in ("user_id", "usuario", "quien")
    )
    assert set(r[0].model_dump().keys()) == {"question", "veces"}


def test_no_sugiere_lo_que_tyto_no_pudo_responder(env):
    """Sugerir algo que termina en "no encuentro esa información" es peor que
    no sugerir nada."""
    quien_pregunta = _miembro(env)
    env.session.add(TytoQueryLog(
        id=_uid(), workspace_id=env.ws.id, user_id="x",
        question="¿Cuál es el sueldo del gerente?", answered=False,
        answer="", refusal_reason="sin_contexto", sources_json="[]",
    ))
    env.session.commit()

    assert _sugerencias(env, quien_pregunta) == []


def test_una_respuesta_que_mezcla_carpetas_no_se_sugiere(env):
    """Alcanza con que UNA fuente esté vedada para que la pregunta revele algo
    de esa carpeta."""
    sin_acceso = _miembro(env, con_rol=False)
    env.session.add(TytoQueryLog(
        id=_uid(), workspace_id=env.ws.id, user_id="x",
        question="¿Qué firmo al cerrar?", answered=True, answer="R",
        sources_json=json.dumps([
            {"source_id": "S1", "document_id": env.doc_abierto.id},
            {"source_id": "S2", "document_id": env.doc_restringido.id},
        ]),
    ))
    env.session.commit()

    assert _sugerencias(env, sin_acceso) == []


def test_las_variantes_de_la_misma_pregunta_se_agrupan(env):
    quien_pregunta = _miembro(env)
    _pregunta_registrada(env, "¿Cómo cierro la caja?", env.doc_abierto)
    _pregunta_registrada(env, "¿cómo   CIERRO la caja?", env.doc_abierto)

    r = _sugerencias(env, quien_pregunta)
    assert len(r) == 1 and r[0].veces == 2


# ── Transcripción de la pregunta hablada ────────────────────────────────────

class _ArchivoFalso:
    def __init__(self, filename, contenido=b"audio"):
        self.filename = filename
        self._contenido = contenido

    async def read(self):
        return self._contenido


def test_transcribe_devuelve_el_texto_y_no_guarda_el_audio(monkeypatch, tmp_path):
    """El audio es la pregunta de una persona, no evidencia: se descarta."""
    rutas_vistas: list[str] = []

    class _Proveedor:
        def transcribe(self, ruta, **kwargs):
            rutas_vistas.append(ruta)
            return "  ¿cómo cierro la caja?  "

    monkeypatch.setattr(tyto_route, "get_transcription_provider", lambda: _Proveedor())

    salida = asyncio.run(
        tyto_route.tyto_transcribe(
            file=_ArchivoFalso("pregunta.webm"), user_id="u1", ctx=None
        )
    )
    assert salida == {"text": "¿cómo cierro la caja?"}

    from pathlib import Path as _P

    assert rutas_vistas and not _P(rutas_vistas[0]).exists(), (
        "el archivo temporal del audio debe borrarse después de transcribir"
    )


def test_transcribe_rechaza_un_formato_que_no_es_audio(monkeypatch):
    monkeypatch.setattr(
        tyto_route, "get_transcription_provider",
        lambda: pytest.fail("no debería llamarse al proveedor"),
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            tyto_route.tyto_transcribe(
                file=_ArchivoFalso("payload.exe"), user_id="u1", ctx=None
            )
        )
    assert exc.value.status_code == 400


def test_transcribe_rechaza_un_audio_gigante(monkeypatch):
    """Cada transcripción cuesta plata y sale a un tercero."""
    grande = b"x" * (tyto_route.MAX_AUDIO_PREGUNTA_BYTES + 1)
    monkeypatch.setattr(
        tyto_route, "get_transcription_provider",
        lambda: pytest.fail("no debería llamarse al proveedor"),
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            tyto_route.tyto_transcribe(
                file=_ArchivoFalso("pregunta.webm", grande), user_id="u1", ctx=None
            )
        )
    assert exc.value.status_code == 400


def test_si_falla_el_proveedor_el_temporal_igual_se_borra(monkeypatch):
    rutas: list[str] = []

    class _Proveedor:
        def transcribe(self, ruta, **kwargs):
            rutas.append(ruta)
            raise RuntimeError("proveedor caído")

    monkeypatch.setattr(tyto_route, "get_transcription_provider", lambda: _Proveedor())

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            tyto_route.tyto_transcribe(
                file=_ArchivoFalso("pregunta.webm"), user_id="u1", ctx=None
            )
        )
    assert exc.value.status_code == 502

    from pathlib import Path as _P

    assert rutas and not _P(rutas[0]).exists()
