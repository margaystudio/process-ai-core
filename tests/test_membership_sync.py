"""Tests para la sincronización de WorkspaceMembership local (tarea 1.5).

Cubre:
  - Mapeo de roles: tenant_admin→admin, tenant_member→creator,
    tenant_external_client→viewer, superadmin en platform_roles→superadmin.
  - Prioridad de rol cuando llegan varios tenant_roles.
  - Idempotencia: llamar sync N veces no crea memberships duplicadas.
  - Re-sync: si cambia el tenant_role, la membership local se actualiza.
  - get_or_create_local_user_from_workspace: crea usuario nuevo, link por email,
    idempotente por external_id.
  - Integración end-to-end: un tenant_admin tiene permisos de admin en el
    workspace; un tenant_member puede crear pero no aprobar.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa – registra modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.helpers import (
    get_or_create_workspace_for_tenant,
    get_or_create_local_user_from_workspace,
    sync_membership_from_context,
    _resolve_system_role_name,
)
from process_ai_core.db.models import Role, User, Workspace, WorkspaceMembership
from process_ai_core.db.permissions import has_permission


# ── Fixture: DB en memoria ────────────────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _uid() -> str:
    return str(uuid.uuid4())


def _seed_roles(session) -> dict[str, Role]:
    """Siembra los roles de sistema mínimos necesarios para los tests."""
    roles = {}
    for name in ("owner", "admin", "approver", "creator", "viewer", "superadmin"):
        role = Role(name=name, is_system=True)
        session.add(role)
        roles[name] = role
    session.flush()
    return roles


def _make_workspace(session) -> str:
    """Crea un workspace de prueba y devuelve su id."""
    ws = Workspace(
        slug=f"ws-{_uid()[:8]}",
        name="Test Workspace",
        workspace_type="organization",
    )
    session.add(ws)
    session.flush()
    return ws.id


def _make_user(session, external_id: str | None = None, email: str | None = None) -> str:
    email = email or f"u-{_uid()[:8]}@test.com"
    u = User(
        email=email,
        name="Test User",
        external_id=external_id or _uid(),
        auth_provider="supabase",
        password_hash="",
    )
    session.add(u)
    session.flush()
    return u.id


# ── Tests: _resolve_system_role_name ─────────────────────────────────────────

class TestResolveSystemRoleName:
    def test_tenant_admin_maps_to_admin(self):
        assert _resolve_system_role_name(["tenant_admin"], []) == "admin"

    def test_tenant_member_maps_to_creator(self):
        assert _resolve_system_role_name(["tenant_member"], []) == "creator"

    def test_tenant_external_client_maps_to_viewer_by_default(self):
        assert _resolve_system_role_name(["tenant_external_client"], []) == "viewer"

    def test_tenant_external_client_role_is_configurable(self):
        with patch.dict("os.environ", {"TENANT_EXTERNAL_CLIENT_ROLE": "approver"}):
            # Reimportar la función para que lea el env actualizado
            from process_ai_core.db.helpers import _resolve_system_role_name as fn
            assert fn(["tenant_external_client"], []) == "approver"

    def test_superadmin_in_platform_roles_wins_over_tenant_roles(self):
        assert _resolve_system_role_name(["tenant_member"], ["superadmin"]) == "superadmin"

    def test_superadmin_platform_role_alone(self):
        assert _resolve_system_role_name([], ["superadmin"]) == "superadmin"

    def test_no_roles_defaults_to_viewer(self):
        assert _resolve_system_role_name([], []) == "viewer"

    def test_unknown_tenant_role_defaults_to_viewer(self):
        assert _resolve_system_role_name(["unknown_role"], []) == "viewer"

    def test_higher_privilege_wins_when_multiple_tenant_roles(self):
        # tenant_admin (→admin) y tenant_member (→creator): admin > creator
        assert _resolve_system_role_name(["tenant_admin", "tenant_member"], []) == "admin"

    def test_creator_beats_viewer(self):
        assert _resolve_system_role_name(["tenant_member", "tenant_external_client"], []) == "creator"


# ── Tests: get_or_create_local_user_from_workspace ────────────────────────────

class TestGetOrCreateLocalUser:
    def test_creates_new_user(self, session):
        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="new@test.com",
            first_name="New", last_name="User"
        )
        user = session.query(User).filter_by(id=user_id).first()
        assert user is not None
        assert user.email == "new@test.com"
        assert user.external_id == sub
        assert user.name == "New User"

    def test_idempotent_by_external_id(self, session):
        sub = _uid()
        id1 = get_or_create_local_user_from_workspace(session, supabase_sub=sub, email="a@t.com")
        id2 = get_or_create_local_user_from_workspace(session, supabase_sub=sub, email="a@t.com")
        assert id1 == id2
        assert session.query(User).filter_by(external_id=sub).count() == 1

    def test_links_existing_user_by_email(self, session):
        """Si el usuario existe por email pero sin external_id, lo vincula."""
        existing = User(email="link@test.com", name="Old", external_id=None, password_hash="")
        session.add(existing)
        session.flush()

        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="link@test.com"
        )
        assert user_id == existing.id
        assert existing.external_id == sub

    def test_uses_email_prefix_as_name_when_no_first_last(self, session):
        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="john.doe@example.com"
        )
        user = session.query(User).filter_by(id=user_id).first()
        assert user.name == "john.doe"


# ── Tests: sync_membership_from_context ───────────────────────────────────────

class TestSyncMembership:
    def test_creates_membership_for_tenant_admin(self, session):
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        assert membership is not None
        assert membership.user_id == u_id
        assert membership.workspace_id == ws_id
        assert membership.role == "admin"

    def test_creates_membership_for_tenant_member(self, session):
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )
        assert membership.role == "creator"

    def test_creates_membership_for_external_client(self, session):
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_external_client"], platform_roles=[],
        )
        assert membership.role == "viewer"

    def test_creates_membership_for_superadmin(self, session):
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=[], platform_roles=["superadmin"],
        )
        assert membership.role == "superadmin"

    def test_idempotent_same_role(self, session):
        """Llamar dos veces con los mismos datos no crea memberships duplicadas."""
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        count = session.query(WorkspaceMembership).filter_by(
            user_id=u_id, workspace_id=ws_id
        ).count()
        assert count == 1

    def test_resync_updates_role(self, session):
        """Si cambia el tenant_role, la membership local se actualiza (re-sync)."""
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        m = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )
        assert m.role == "creator"

        m2 = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        assert m2.role == "admin"
        assert session.query(WorkspaceMembership).filter_by(
            user_id=u_id, workspace_id=ws_id
        ).count() == 1

    def test_different_users_get_different_memberships(self, session):
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u1 = _make_user(session)
        u2 = _make_user(session)

        sync_membership_from_context(
            session, local_user_id=u1, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        sync_membership_from_context(
            session, local_user_id=u2, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )
        m1 = session.query(WorkspaceMembership).filter_by(user_id=u1, workspace_id=ws_id).first()
        m2 = session.query(WorkspaceMembership).filter_by(user_id=u2, workspace_id=ws_id).first()
        assert m1.role == "admin"
        assert m2.role == "creator"


# ── Tests de integración: permisos efectivos post-sync ────────────────────────

class TestPermissionsAfterSync:
    """
    Verifica que has_permission() funcione correctamente después de sincronizar
    la membership.

    Nota: has_permission() requiere que los permisos estén asignados a los roles
    (seed_permissions.py). En tests unitarios con DB en memoria solo tenemos roles
    creados sin permisos → has_permission() devuelve False para permisos específicos.

    Los tests de integración completa (con seed) están cubiertos en
    test_version_workflow.py. Aquí probamos la mecánica de membership.
    """

    def test_has_permission_returns_false_without_membership(self, session):
        _seed_roles(session)
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        # Sin membership → sin permisos
        assert has_permission(session, u_id, ws_id, "documents.create") is False

    def test_has_permission_after_sync_with_seeded_role_permissions(self, session):
        """
        Con roles correctamente sembrados + permisos asignados, admin puede
        aprobar y creator no puede (segregación).
        """
        from process_ai_core.db.models import RolePermission, Permission

        # Sembrar roles
        roles = _seed_roles(session)

        # Sembrar permisos mínimos para el test
        perm_approve = Permission(name="documents.approve", description="Aprobar documentos", category="documents")
        perm_create = Permission(name="documents.create", description="Crear documentos", category="documents")
        session.add_all([perm_approve, perm_create])
        session.flush()

        # Asignar: admin tiene approve y create; creator solo tiene create
        session.add(RolePermission(role_id=roles["admin"].id, permission_id=perm_approve.id))
        session.add(RolePermission(role_id=roles["admin"].id, permission_id=perm_create.id))
        session.add(RolePermission(role_id=roles["creator"].id, permission_id=perm_create.id))
        session.flush()

        ws_id = _make_workspace(session)
        admin_id = _make_user(session)
        creator_id = _make_user(session)

        # Sincronizar memberships
        sync_membership_from_context(
            session, local_user_id=admin_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        sync_membership_from_context(
            session, local_user_id=creator_id, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )

        # tenant_admin (→admin) puede aprobar
        assert has_permission(session, admin_id, ws_id, "documents.approve") is True
        # tenant_member (→creator) puede crear
        assert has_permission(session, creator_id, ws_id, "documents.create") is True
        # tenant_member NO puede aprobar (segregación creador ≠ aprobador)
        assert has_permission(session, creator_id, ws_id, "documents.approve") is False

    def test_workspace_without_membership_tenant_admin_gets_it_after_sync(self, session):
        """
        Escenario: workspace recién creado (1.4b), tenant_admin entra → sync
        le crea la membership → has_permission pasa de False a True.
        """
        from process_ai_core.db.models import RolePermission, Permission

        roles = _seed_roles(session)
        perm_view = Permission(name="workspace.view", description="Ver workspace", category="workspaces")
        session.add(perm_view)
        session.flush()
        session.add(RolePermission(role_id=roles["admin"].id, permission_id=perm_view.id))
        session.flush()

        tenant_id = _uid()
        ws_id = get_or_create_workspace_for_tenant(
            session, tenant_id=tenant_id, tenant_name="Acme", tenant_slug="acme"
        )

        sub = _uid()
        u_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="admin@acme.com",
            first_name="Admin", last_name="User",
        )

        # Antes de sync → sin permisos
        assert has_permission(session, u_id, ws_id, "workspace.view") is False

        # Sync
        sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )

        # Después de sync → con permisos
        assert has_permission(session, u_id, ws_id, "workspace.view") is True
