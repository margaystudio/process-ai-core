"""Tipos documentales por-tenant: siembra, idempotencia y aislamiento (Fases 2/3/7).

Ver docs/PLAN_DOCUMENT_TYPES.md. Cada tenant es dueño de su set de tipos; se siembra
con los defaults al provisionar y editar los de un tenant no afecta a otro.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from process_ai_core.db.database import Base
from process_ai_core.db.models import DocumentType, Workspace
from process_ai_core.db.helpers import seed_default_document_types
from process_ai_core.domains.document_types import DEFAULT_DOCUMENT_TYPES, normalize_behaviors

N = len(DEFAULT_DOCUMENT_TYPES)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def _ws(session, slug: str) -> Workspace:
    ws = Workspace(id=str(uuid.uuid4()), slug=slug, name="WS", workspace_type="organization")
    session.add(ws)
    session.commit()
    return ws


def test_siembra_los_defaults(session):
    ws = _ws(session, "a")
    seed_default_document_types(session, ws.id)
    session.commit()

    rows = session.query(DocumentType).filter_by(workspace_id=ws.id).all()
    assert len(rows) == N
    assert all(r.origin == "default" for r in rows)

    proc = next(r for r in rows if r.key == "procedimiento")
    assert proc.label == "Procedimiento"
    assert proc.icon and proc.color.startswith("#")
    assert normalize_behaviors(json.loads(proc.behaviors_json))["tyto"] is True


def test_siembra_es_idempotente(session):
    ws = _ws(session, "a")
    seed_default_document_types(session, ws.id)
    session.commit()
    seed_default_document_types(session, ws.id)  # segunda vez: no duplica
    session.commit()
    assert session.query(DocumentType).filter_by(workspace_id=ws.id).count() == N


def test_aislamiento_entre_tenants(session):
    a = _ws(session, "a")
    b = _ws(session, "b")
    seed_default_document_types(session, a.id)
    seed_default_document_types(session, b.id)
    session.commit()

    # Editar el "procedimiento" del tenant A...
    pa = session.query(DocumentType).filter_by(workspace_id=a.id, key="procedimiento").one()
    pa.label = "Proceso custom de A"
    pa.origin = "custom"
    session.commit()

    # ...no toca el del tenant B.
    pb = session.query(DocumentType).filter_by(workspace_id=b.id, key="procedimiento").one()
    assert pb.label == "Procedimiento"
    assert pb.origin == "default"


def test_mismo_key_en_dos_tenants_es_valido(session):
    a = _ws(session, "a")
    b = _ws(session, "b")
    seed_default_document_types(session, a.id)
    seed_default_document_types(session, b.id)
    session.commit()
    # UNIQUE es (workspace_id, key): "procedimiento" existe una vez por tenant.
    assert session.query(DocumentType).filter_by(key="procedimiento").count() == 2
