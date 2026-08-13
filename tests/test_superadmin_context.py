"""Tests para la detección de superadmin desde el contexto (tarea D — deprecar workspace sistema).

Cubre:
  E10: platform_roles=['superadmin'] → has_permission devuelve True sin membership local.
  E11: usuario sin platform_roles superadmin NO tiene ese bypass.
  E12: el listado de workspaces del usuario NO incluye workspaces con slug='sistema' / type='system'
       después de correr el cleanup (o si nunca existió).
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa – registra modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.models import User, Workspace, WorkspaceMembership
from process_ai_core.db.permissions import (
    has_permission,
    _is_superadmin,
    can_view_folder,
    can_create_in_folder,
    can_approve_in_folder,
)
from process_ai_core.db.helpers import (
    sync_membership_from_context,
    get_or_create_workspace_for_tenant,
    get_or_create_local_user_from_workspace,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

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


def _uid() -> str:
    return str(uuid.uuid4())


def _make_workspace(session, slug=None, workspace_type="organization") -> Workspace:
    ws = Workspace(
        slug=slug or f"ws-{_uid()[:8]}",
        name="Test Workspace",
        workspace_type=workspace_type,
    )
    session.add(ws)
    session.flush()
    return ws


def _make_user(session) -> User:
    u = User(
        email=f"u-{_uid()[:8]}@test.com",
        name="Test User",
        external_id=_uid(),
        auth_provider="supabase",
    )
    session.add(u)
    session.flush()
    return u


# ── E10: superadmin de plataforma sin membership local tiene todos los permisos ─

class TestPlatformSuperadminBypass:
    """platform_is_superadmin=True → bypass inmediato, sin necesidad de membership."""

    def test_has_permission_returns_true_with_platform_superadmin(self, session):
        user = _make_user(session)
        ws = _make_workspace(session)

        # Sin membership local alguna
        assert not session.query(WorkspaceMembership).filter_by(user_id=user.id).first()

        # Con el flag del contexto → True
        result = has_permission(
            session, user.id, ws.id, "documents.approve",
            platform_is_superadmin=True,
        )
        assert result is True

    def test_has_permission_any_permission_bypassed(self, session):
        user = _make_user(session)
        ws = _make_workspace(session)

        for perm in ("documents.view", "documents.create", "documents.approve", "folders.manage"):
            assert has_permission(session, user.id, ws.id, perm, platform_is_superadmin=True)

    def test_is_superadmin_flag_bypasses_db(self, session):
        user = _make_user(session)

        # Sin membership con rol superadmin en ningún workspace
        assert _is_superadmin(session, user.id, platform_is_superadmin=False) is False
        assert _is_superadmin(session, user.id, platform_is_superadmin=True) is True

    def test_platform_superadmin_via_sync_then_has_permission(self, session):
        """Flujo real: sync_membership_from_context crea membership con rol superadmin
        en el workspace activo; has_permission lo encuentra SIN el flag."""
        user = _make_user(session)
        ws = _make_workspace(session)

        # Simula lo que hace sync_workspace_access: crear membership con rol superadmin
        sync_membership_from_context(
            session,
            local_user_id=user.id,
            workspace_id=ws.id,
            tenant_roles=[],
            platform_roles=["superadmin"],
        )
        session.flush()

        # Ahora has_permission lo encuentra por la membership (base_access='admin')
        assert has_permission(session, user.id, ws.id, "documents.approve")
        # Y también con el flag directo
        assert has_permission(session, user.id, ws.id, "documents.approve", platform_is_superadmin=True)

    def test_can_view_folder_bypassed_for_platform_superadmin(self, session):
        from process_ai_core.db.models import Folder
        user = _make_user(session)
        ws = _make_workspace(session)

        folder = Folder(name="Test Folder", workspace_id=ws.id, path="/test")
        session.add(folder)
        session.flush()

        # Sin membership → normally False; con flag → True
        assert not can_view_folder(session, user.id, ws.id, folder.id, platform_is_superadmin=False)
        assert can_view_folder(session, user.id, ws.id, folder.id, platform_is_superadmin=True)

    def test_can_create_in_folder_bypassed(self, session):
        from process_ai_core.db.models import Folder
        user = _make_user(session)
        ws = _make_workspace(session)

        folder = Folder(name="Test Folder", workspace_id=ws.id, path="/test")
        session.add(folder)
        session.flush()

        assert can_create_in_folder(session, user.id, ws.id, folder.id, platform_is_superadmin=True)

    def test_can_approve_in_folder_bypassed(self, session):
        from process_ai_core.db.models import Folder
        user = _make_user(session)
        ws = _make_workspace(session)

        folder = Folder(name="Test Folder", workspace_id=ws.id, path="/test")
        session.add(folder)
        session.flush()

        assert can_approve_in_folder(session, user.id, ws.id, folder.id, platform_is_superadmin=True)


# ── E11: usuario sin platform_roles superadmin NO tiene el bypass ─────────────

class TestNoPlatformSuperadminBypass:
    """Sin el flag (o flag=False), el bypass NO aplica."""

    def test_has_permission_false_without_membership(self, session):
        user = _make_user(session)
        ws = _make_workspace(session)

        # Sin flag y sin membership → False
        assert has_permission(
            session, user.id, ws.id, "documents.approve",
            platform_is_superadmin=False,
        ) is False

    def test_has_permission_false_default(self, session):
        user = _make_user(session)
        ws = _make_workspace(session)

        # Parámetro omitido (default False) → False
        assert has_permission(session, user.id, ws.id, "documents.approve") is False

    def test_creator_cannot_approve(self, session):
        """tenant_member → rol creator → puede crear, no aprobar."""
        user = _make_user(session)
        ws = _make_workspace(session)

        sync_membership_from_context(
            session,
            local_user_id=user.id,
            workspace_id=ws.id,
            tenant_roles=["tenant_member"],
            platform_roles=[],
        )
        session.flush()

        # Necesita permisos semrados para que has_permission funcione
        # (sin seed_permissions, solo el rol importa; con permisos: testeamos con flag=False)
        assert has_permission(session, user.id, ws.id, "documents.approve", platform_is_superadmin=False) is False

    def test_is_superadmin_false_without_flag_or_membership(self, session):
        user = _make_user(session)

        assert _is_superadmin(session, user.id, platform_is_superadmin=False) is False
        assert _is_superadmin(session, user.id) is False


# ── E12: listado de workspaces no incluye workspace 'sistema' ─────────────────

class TestNoSistemaWorkspaceInList:
    """Después de cleanup (o si nunca existió), el workspace 'sistema' no aparece en el listado."""

    def test_no_sistema_workspace_in_list_when_clean(self, session):
        """Sin workspace 'sistema', el listado de workspaces no lo incluye."""
        user = _make_user(session)

        # Crear workspace normal
        ws_normal = _make_workspace(session, slug="org-test")
        sync_membership_from_context(
            session,
            local_user_id=user.id,
            workspace_id=ws_normal.id,
            tenant_roles=["tenant_admin"],
            platform_roles=[],
        )
        session.flush()

        memberships = session.query(WorkspaceMembership).filter_by(user_id=user.id).all()
        workspace_ids = [m.workspace_id for m in memberships]
        workspaces = session.query(Workspace).filter(Workspace.id.in_(workspace_ids)).all()

        # No debe haber ningún workspace con slug='sistema' o type='system'
        slugs = [ws.slug for ws in workspaces]
        types = [ws.workspace_type for ws in workspaces]
        assert "sistema" not in slugs
        assert "system" not in types

    # (El test del script de cleanup se eliminó: la limpieza del workspace
    # 'sistema' quedó absorbida por la migración 0025_drop_roles_legacy, que
    # además borra las tablas del RBAC legacy.)

    def test_platform_superadmin_has_no_sistema_workspace_in_new_arch(self, session):
        """En la nueva arquitectura, un platform superadmin tiene membership en el
        workspace activo (no en 'sistema'), y 'sistema' no existe."""
        user = _make_user(session)

        # La nueva arquitectura: workspace real creado por get_or_create_workspace_for_tenant
        ws_real = _make_workspace(session, slug="margay-studio")
        sync_membership_from_context(
            session,
            local_user_id=user.id,
            workspace_id=ws_real.id,
            tenant_roles=[],
            platform_roles=["superadmin"],
        )
        session.flush()

        memberships = session.query(WorkspaceMembership).filter_by(user_id=user.id).all()
        workspace_ids = [m.workspace_id for m in memberships]
        workspaces = session.query(Workspace).filter(Workspace.id.in_(workspace_ids)).all()

        # Tiene una membership (en el workspace real, no en 'sistema')
        assert len(memberships) == 1
        assert workspaces[0].slug == "margay-studio"
        assert workspaces[0].workspace_type != "system"

        # La membership es admin del workspace
        assert memberships[0].base_access == "admin"

        # has_permission via membership local (sin flag) → True
        assert has_permission(session, user.id, ws_real.id, "documents.approve")
