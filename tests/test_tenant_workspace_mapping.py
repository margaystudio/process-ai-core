"""Tests para el mapeo tenant → Workspace local (tarea 1.4b).

Cubre:
  - get-or-create crea el Workspace en la primera llamada
  - get-or-create es idempotente (dos llamadas → un solo Workspace)
  - Tenants distintos → Workspaces distintos (aislamiento)
  - Slug en conflicto → se resuelve con sufijo del tenant_id
  - resolve_tenant_workspace_id delega correctamente al helper
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa – registra los modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.helpers import get_or_create_workspace_for_tenant
from process_ai_core.db.models import Folder, Workspace


# ── Fixture: base de datos en memoria aislada para cada test ────────────────

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    # No llamamos drop_all: la DB en memoria desaparece con el engine.
    # drop_all falla en teardown por dependencias circulares de FK en SQLite.


# ── Helpers ──────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())


def _call(session, tenant_id=None, name="Acme Corp", slug="acme"):
    tid = tenant_id or _uid()
    return get_or_create_workspace_for_tenant(session, tid, name, slug), tid


# ── Tests del helper ─────────────────────────────────────────────────────────

def test_creates_workspace_on_first_call(session):
    """Primera llamada → crea Workspace en la DB."""
    tid = _uid()
    ws_id = get_or_create_workspace_for_tenant(session, tid, "Acme", "acme")

    workspace = session.query(Workspace).filter_by(id=ws_id).first()
    assert workspace is not None
    assert workspace.tenant_id == tid
    assert workspace.name == "Acme"
    assert workspace.slug == "acme"
    assert workspace.workspace_type == "organization"


def test_creates_root_folder(session):
    """Al crear un Workspace se genera automáticamente una carpeta raíz."""
    tid = _uid()
    ws_id = get_or_create_workspace_for_tenant(session, tid, "Acme", "acme")
    session.flush()

    folders = session.query(Folder).filter_by(workspace_id=ws_id).all()
    assert len(folders) == 1
    assert folders[0].parent_id is None


def test_idempotent_returns_same_workspace(session):
    """Dos llamadas con el mismo tenant → mismo id, sin duplicados."""
    tid = _uid()
    ws_id_1 = get_or_create_workspace_for_tenant(session, tid, "Acme", "acme")
    session.flush()
    ws_id_2 = get_or_create_workspace_for_tenant(session, tid, "Acme", "acme")

    assert ws_id_1 == ws_id_2
    count = session.query(Workspace).filter_by(tenant_id=tid).count()
    assert count == 1


def test_different_tenants_get_different_workspaces(session):
    """Tenants distintos → Workspaces locales distintos (aislamiento)."""
    tid_a, tid_b = _uid(), _uid()
    ws_a = get_or_create_workspace_for_tenant(session, tid_a, "Tenant A", "tenant-a")
    session.flush()
    ws_b = get_or_create_workspace_for_tenant(session, tid_b, "Tenant B", "tenant-b")
    session.flush()

    assert ws_a != ws_b
    assert session.query(Workspace).count() == 2


def test_slug_collision_uses_suffix(session):
    """Si el slug ya existe para otro workspace, se añade sufijo del tenant_id."""
    # Crear un workspace existente con slug "acme"
    existing = Workspace(id=_uid(), slug="acme", name="Old Acme", workspace_type="organization")
    session.add(existing)
    session.flush()

    tid = _uid()
    ws_id = get_or_create_workspace_for_tenant(session, tid, "New Acme", "acme")
    session.flush()

    new_workspace = session.query(Workspace).filter_by(id=ws_id).first()
    assert new_workspace.slug == f"acme-{tid[:8]}"
    assert new_workspace.slug != "acme"


def test_returns_local_id_not_tenant_id(session):
    """El helper devuelve el id LOCAL del Workspace, no el tenant_id."""
    tid = _uid()
    ws_id = get_or_create_workspace_for_tenant(session, tid, "Acme", "acme")
    session.flush()

    workspace = session.query(Workspace).filter_by(id=ws_id).first()
    assert ws_id == workspace.id
    assert ws_id != tid


# ── Tests de resolve_tenant_workspace_id ────────────────────────────────────

def test_resolve_calls_helper_with_tenant_data():
    """resolve_tenant_workspace_id pasa los datos correctos del ctx al helper."""
    from api.workspace_client import (
        WorkspaceApplication,
        WorkspaceSessionContext,
        WorkspaceTenant,
        WorkspaceUser,
        resolve_tenant_workspace_id,
    )

    ctx = WorkspaceSessionContext(
        user=WorkspaceUser(id="u1", email="u@example.com"),
        platform_roles=[],
        tenant_roles=[],
        tenant=WorkspaceTenant(id="tenant-xyz", name="My Org", slug="my-org"),
        tenants=[WorkspaceTenant(id="tenant-xyz", name="My Org", slug="my-org")],
        applications=[],
    )

    # El helper se importa dentro de resolve_tenant_workspace_id, así que
    # lo parchamos en su módulo de origen.
    with patch(
        "process_ai_core.db.helpers.get_or_create_workspace_for_tenant",
        return_value="local-ws-id",
    ) as mock_helper:
        with patch("process_ai_core.db.database.get_db_session") as mock_session_ctx:
            fake_session = object()
            mock_session_ctx.return_value.__enter__ = lambda s: fake_session
            mock_session_ctx.return_value.__exit__ = lambda s, *a: False

            result = resolve_tenant_workspace_id(ctx)

    mock_helper.assert_called_once_with(
        fake_session,
        tenant_id="tenant-xyz",
        tenant_name="My Org",
        tenant_slug="my-org",
    )
    assert result == "local-ws-id"
