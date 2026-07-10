"""Tests del preflight de infraestructura de la capa semántica (Tarea 1).

Verifican la política estricto/degradado sin necesitar un Postgres real: sobre
SQLite el preflight reporta "degradado" (no hay pgvector/pg_trgm), lo que permite
ejercitar ambas ramas de la política controlando `semantic_allow_degraded` y la
presencia de `OPENAI_API_KEY`.
"""

from __future__ import annotations

import logging
import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from process_ai_core.semantic import preflight as pf


def _sqlite_session() -> Session:
    return Session(create_engine("sqlite:///:memory:"))


def _fake_settings(monkeypatch, *, allow_degraded: bool, api_key: str) -> None:
    fake = types.SimpleNamespace(
        semantic_allow_degraded=allow_degraded,
        openai_api_key=api_key,
    )
    monkeypatch.setattr(pf, "get_settings", lambda: fake)


def test_check_en_sqlite_reporta_degradado(monkeypatch):
    _fake_settings(monkeypatch, allow_degraded=True, api_key="sk-x")
    st = pf.check_semantic_infra(_sqlite_session())
    assert st.backend == "sqlite"
    assert st.pgvector is False
    assert st.pg_trgm is False
    assert st.embedding_is_vector is False
    assert st.openai_api_key is True
    assert st.ok is False
    assert st.healthy is True  # degradado permitido


def test_estricto_falla_con_mensaje_accionable(monkeypatch):
    _fake_settings(monkeypatch, allow_degraded=False, api_key="")
    with pytest.raises(pf.SemanticInfraError) as ei:
        pf.enforce_semantic_infra(_sqlite_session())
    msg = str(ei.value)
    assert "SEMANTIC_ALLOW_DEGRADED=false" in msg
    assert "pgvector" in msg
    assert "OPENAI_API_KEY" in msg
    assert "alembic upgrade head" in msg  # acción concreta


def test_degradado_no_falla_y_loguea_warnings(monkeypatch, caplog):
    _fake_settings(monkeypatch, allow_degraded=True, api_key="")
    with caplog.at_level(logging.WARNING):
        st = pf.enforce_semantic_infra(_sqlite_session())
    assert st.healthy is True
    assert any("DEGRADADA" in r.getMessage() for r in caplog.records)


def test_deteccion_de_api_key(monkeypatch):
    _fake_settings(monkeypatch, allow_degraded=True, api_key="")
    assert pf.check_semantic_infra(_sqlite_session()).openai_api_key is False
    _fake_settings(monkeypatch, allow_degraded=True, api_key="sk-abc")
    assert pf.check_semantic_infra(_sqlite_session()).openai_api_key is True


def test_status_as_dict(monkeypatch):
    _fake_settings(monkeypatch, allow_degraded=False, api_key="sk-x")
    d = pf.check_semantic_infra(_sqlite_session()).as_dict()
    assert d["ok"] is False
    assert d["backend"] == "sqlite"
    assert isinstance(d["issues"], list) and d["issues"]
