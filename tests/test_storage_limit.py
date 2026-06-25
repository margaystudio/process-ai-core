"""
Test del enforcement del límite de storage por plan (diferido #1).

Verifica `enforce_storage_limit`:
  - sin suscripción → no enforce (None),
  - plan con max_storage_gb=None → ilimitado (None),
  - uso < límite → None; uso >= límite → mensaje de error.
"""

import uuid
from datetime import datetime, timedelta, UTC

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Folder, SubscriptionPlan, Workspace, WorkspaceSubscription,
)
from process_ai_core.db.helpers import enforce_storage_limit


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


def _make_ws(session):
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(id=f"lim-ws-{uid}", slug=f"lim-ws-{uid}", name="Lim", workspace_type="organization")
    session.add(ws)
    session.add(Folder(id=f"lim-fol-{uid}", workspace_id=ws.id, name="root", path="root"))
    session.flush()
    return ws


def _make_sub(session, ws, max_gb, used_gb):
    uid = str(uuid.uuid4())[:8]
    plan = SubscriptionPlan(
        id=f"lim-plan-{uid}", name=f"plan-{uid}", display_name="Plan",
        plan_type="b2b", max_storage_gb=max_gb,
    )
    session.add(plan); session.flush()
    sub = WorkspaceSubscription(
        id=f"lim-sub-{uid}", workspace_id=ws.id, plan_id=plan.id, status="active",
        current_period_start=datetime.now(UTC), current_period_end=datetime.now(UTC) + timedelta(days=30),
        current_storage_gb=used_gb,
    )
    session.add(sub); session.flush()
    return plan, sub


def test_no_subscription_no_enforce(session):
    ws = _make_ws(session)
    try:
        assert enforce_storage_limit(session, ws.id) is None
    finally:
        session.query(Folder).filter_by(workspace_id=ws.id).delete()
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


def test_under_over_and_unlimited(session):
    ws = _make_ws(session)
    plan, sub = _make_sub(session, ws, max_gb=0.001, used_gb=0.0)
    try:
        # Bajo el límite → permite
        assert enforce_storage_limit(session, ws.id) is None

        # Igual/encima del límite → bloquea con mensaje
        sub.current_storage_gb = 0.001
        session.flush()
        msg = enforce_storage_limit(session, ws.id)
        assert msg is not None and "almacenamiento" in msg.lower()

        # Plan ilimitado → permite aunque haya uso
        plan.max_storage_gb = None
        session.flush()
        assert enforce_storage_limit(session, ws.id) is None
    finally:
        session.query(WorkspaceSubscription).filter_by(id=sub.id).delete()
        session.query(SubscriptionPlan).filter_by(id=plan.id).delete()
        session.query(Folder).filter_by(workspace_id=ws.id).delete()
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()
