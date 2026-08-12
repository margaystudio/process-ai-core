"""Tests para la sincronización de WorkspaceMembership local.

Cubre (modelo fase 3 — acceso base, sin roles de sistema):
  - Mapeo del rol macro: tenant_admin→'admin', tenant_member→'member',
    tenant_external_client→'external', superadmin en platform_roles→'admin'.
  - Prioridad cuando llegan varios tenant_roles; fallback a 'external'.
  - Idempotencia: llamar sync N veces no crea memberships duplicadas.
  - Re-sync: si cambia el rol macro, base_access se actualiza.
  - get_or_create_local_user_from_workspace: crea usuario nuevo, link por email,
    idempotente por external_id.
  - Integración: admin puede aprobar; member crea pero no aprueba; external
    solo lee. Sin ningún seed: el modelo no depende de tablas de roles.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa – registra modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.helpers import (
    get_or_create_workspace_for_tenant,
    get_or_create_local_user_from_workspace,
    sync_membership_from_context,
    _resolve_base_access,
)
from process_ai_core.db.models import User, Workspace, WorkspaceMembership
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
    )
    session.add(u)
    session.flush()
    return u.id


# ── Tests: _resolve_base_access ───────────────────────────────────────────────

class TestResolveBaseAccess:
    def test_tenant_admin_maps_to_admin(self):
        assert _resolve_base_access(["tenant_admin"], []) == "admin"

    def test_tenant_member_maps_to_member(self):
        assert _resolve_base_access(["tenant_member"], []) == "member"

    def test_tenant_external_client_maps_to_external(self):
        assert _resolve_base_access(["tenant_external_client"], []) == "external"

    def test_superadmin_in_platform_roles_wins_over_tenant_roles(self):
        assert _resolve_base_access(["tenant_member"], ["superadmin"]) == "admin"

    def test_superadmin_platform_role_alone(self):
        assert _resolve_base_access([], ["superadmin"]) == "admin"

    def test_no_roles_defaults_to_external(self):
        """Fallback = el acceso MÁS restrictivo, nunca uno inventado."""
        assert _resolve_base_access([], []) == "external"

    def test_unknown_tenant_role_defaults_to_external(self):
        assert _resolve_base_access(["unknown_role"], []) == "external"

    def test_higher_privilege_wins_when_multiple_tenant_roles(self):
        assert _resolve_base_access(["tenant_admin", "tenant_member"], []) == "admin"

    def test_member_beats_external(self):
        assert _resolve_base_access(["tenant_member", "tenant_external_client"], []) == "member"


# ── Tests: get_or_create_local_user_from_workspace ────────────────────────────

class TestGetOrCreateLocalUser:
    def test_creates_new_user(self, session):
        """El nombre es el `display_name` que manda Workspace, tal cual."""
        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="new@test.com",
            first_name="New", last_name="User", display_name="New User",
        )
        user = session.query(User).filter_by(id=user_id).first()
        assert user is not None
        assert user.email == "new@test.com"
        assert user.external_id == sub
        assert user.name == "New User"

    def test_no_concatena_first_y_last_name(self, session):
        """Anti-patrón #6: el módulo NO arma el nombre.

        Si Workspace manda un `display_name` con otro formato, es ese el que se
        guarda — no `first_name + last_name`. Es lo que evita que dos módulos
        muestren "Juan Pérez" y "Pérez, J." para la misma persona.
        """
        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="fmt@test.com",
            first_name="Juan", last_name="Pérez", display_name="Pérez, Juan",
        )
        user = session.query(User).filter_by(id=user_id).first()
        assert user.name == "Pérez, Juan"

    def test_idempotent_by_external_id(self, session):
        sub = _uid()
        id1 = get_or_create_local_user_from_workspace(session, supabase_sub=sub, email="a@t.com")
        id2 = get_or_create_local_user_from_workspace(session, supabase_sub=sub, email="a@t.com")
        assert id1 == id2
        assert session.query(User).filter_by(external_id=sub).count() == 1

    def test_links_existing_user_by_email(self, session):
        """Si el usuario existe por email pero sin external_id, lo vincula."""
        existing = User(email="link@test.com", name="Old", external_id=None)
        session.add(existing)
        session.flush()

        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="link@test.com"
        )
        assert user_id == existing.id
        assert existing.external_id == sub

    def test_uses_email_prefix_as_name_when_no_display_name(self, session):
        """Workspace garantiza `display_name`; el fallback es para un control
        plane anterior a la v1.1.0 del contrato."""
        sub = _uid()
        user_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="john.doe@example.com"
        )
        user = session.query(User).filter_by(id=user_id).first()
        assert user.name == "john.doe"


# ── Tests: sync_membership_from_context ───────────────────────────────────────

class TestSyncMembership:
    def test_creates_membership_for_tenant_admin(self, session):
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        assert membership is not None
        assert membership.user_id == u_id
        assert membership.workspace_id == ws_id
        assert membership.base_access == "admin"

    def test_creates_membership_for_tenant_member(self, session):
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )
        assert membership.base_access == "member"

    def test_creates_membership_for_external_client(self, session):
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_external_client"], platform_roles=[],
        )
        assert membership.base_access == "external"

    def test_creates_membership_for_superadmin(self, session):
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=[], platform_roles=["superadmin"],
        )
        assert membership.base_access == "admin"

    def test_no_escribe_role_id_legacy(self, session):
        """El sync ya no toca las columnas legacy de roles de sistema."""
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        membership = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        assert membership.role_id is None
        assert membership.role is None

    def test_idempotent_same_role(self, session):
        """Llamar dos veces con los mismos datos no crea memberships duplicadas."""
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

    def test_resync_updates_base_access(self, session):
        """Si cambia el rol macro, el acceso base local se actualiza (re-sync)."""
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        m = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )
        assert m.base_access == "member"

        m2 = sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        assert m2.base_access == "admin"
        assert session.query(WorkspaceMembership).filter_by(
            user_id=u_id, workspace_id=ws_id
        ).count() == 1

    def test_different_users_get_different_memberships(self, session):
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
        assert m1.base_access == "admin"
        assert m2.base_access == "member"


# ── Tests de integración: permisos efectivos post-sync ────────────────────────

class TestPermissionsAfterSync:
    """
    has_permission() después del sync, SIN ningún seed: los permisos se derivan
    del acceso base y de los niveles de los roles operativos, no de tablas.
    """

    def test_has_permission_returns_false_without_membership(self, session):
        ws_id = _make_workspace(session)
        u_id = _make_user(session)

        assert has_permission(session, u_id, ws_id, "documents.create") is False

    def test_admin_aprueba_member_crea_pero_no_aprueba(self, session):
        ws_id = _make_workspace(session)
        admin_id = _make_user(session)
        member_id = _make_user(session)

        sync_membership_from_context(
            session, local_user_id=admin_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )
        sync_membership_from_context(
            session, local_user_id=member_id, workspace_id=ws_id,
            tenant_roles=["tenant_member"], platform_roles=[],
        )

        assert has_permission(session, admin_id, ws_id, "documents.approve") is True
        assert has_permission(session, member_id, ws_id, "documents.create") is True
        # member no aprueba salvo que un rol operativo con nivel 'aprobacion' se lo dé
        assert has_permission(session, member_id, ws_id, "documents.approve") is False

    def test_external_solo_lectura(self, session):
        ws_id = _make_workspace(session)
        ext_id = _make_user(session)

        sync_membership_from_context(
            session, local_user_id=ext_id, workspace_id=ws_id,
            tenant_roles=["tenant_external_client"], platform_roles=[],
        )

        assert has_permission(session, ext_id, ws_id, "documents.view") is True
        assert has_permission(session, ext_id, ws_id, "documents.export") is True
        assert has_permission(session, ext_id, ws_id, "documents.create") is False
        assert has_permission(session, ext_id, ws_id, "documents.approve") is False

    def test_workspace_without_membership_tenant_admin_gets_it_after_sync(self, session):
        """
        Escenario: workspace recién creado, tenant_admin entra → sync le crea
        la membership → has_permission pasa de False a True.
        """
        tenant_id = _uid()
        ws_id = get_or_create_workspace_for_tenant(
            session, tenant_id=tenant_id, tenant_name="Acme", tenant_slug="acme"
        )

        sub = _uid()
        u_id = get_or_create_local_user_from_workspace(
            session, supabase_sub=sub, email="admin@acme.com",
            first_name="Admin", last_name="User",
        )

        assert has_permission(session, u_id, ws_id, "workspaces.view") is False

        sync_membership_from_context(
            session, local_user_id=u_id, workspace_id=ws_id,
            tenant_roles=["tenant_admin"], platform_roles=[],
        )

        assert has_permission(session, u_id, ws_id, "workspaces.view") is True
