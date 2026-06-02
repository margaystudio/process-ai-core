"""Tests para configuración general del workspace (PATCH /settings)."""

import asyncio
import uuid

import pytest
from fastapi import HTTPException

from api.routes import workspaces as workspaces_route
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Role, User, Workspace, WorkspaceMembership
from api.models.requests import WorkspaceSettingsUpdateRequest


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


def _seed_owner_role(session) -> Role:
    role = session.query(Role).filter_by(name="owner", is_system=True).first()
    if not role:
        role = Role(name="owner", is_system=True, description="Owner")
        session.add(role)
        session.flush()
    return role


def _create_workspace_with_owner(session):
    unique = str(uuid.uuid4())[:8]
    user = User(
        id=f"user-{unique}",
        email=f"owner-{unique}@test.com",
        name="Owner Test",
    )
    workspace = Workspace(
        id=f"ws-{unique}",
        slug=f"ws-{unique}",
        name="Test Org",
        workspace_type="organization",
        tenant_id=f"tenant-{unique}",
    )
    session.add(user)
    session.add(workspace)
    session.flush()

    owner_role = _seed_owner_role(session)
    session.add(
        WorkspaceMembership(
            user_id=user.id,
            workspace_id=workspace.id,
            role_id=owner_role.id,
        )
    )
    session.flush()
    session.commit()
    return workspace, user


def test_serialize_workspace_includes_settings_fields(session):
    workspace, _user = _create_workspace_with_owner(session)
    workspace.country = "UY"
    workspace.language_style = "es_uy_formal"
    workspace.default_audience = "operativo"
    workspace.default_detail_level = "estandar"
    workspace.context_text = "Contexto de prueba"
    session.flush()

    resp = workspaces_route._serialize_workspace(workspace)
    assert resp.country == "UY"
    assert resp.language_style == "es_uy_formal"
    assert resp.default_audience == "operativo"
    assert resp.default_detail_level == "estandar"
    assert resp.context_text == "Contexto de prueba"
    assert resp.tenant_id == workspace.tenant_id


def test_owner_can_update_workspace_settings(session):
    workspace, user = _create_workspace_with_owner(session)

    result = asyncio.run(
        workspaces_route.update_workspace_settings(
            workspace_id=workspace.id,
            request=WorkspaceSettingsUpdateRequest(
                country="AR",
                language_style="es_uy_formal",
                default_audience="gestion",
                default_detail_level="detallado",
                context_text="Nuevo contexto",
                business_type="estaciones_servicio",
            ),
            user_id=user.id,
            session=session,
        )
    )

    assert result.country == "AR"
    assert result.default_audience == "gestion"
    assert result.context_text == "Nuevo contexto"

    session.refresh(workspace)
    assert workspace.country == "AR"
    assert workspace.default_detail_level == "detallado"


def test_admin_can_update_workspace_settings(session):
    workspace, owner = _create_workspace_with_owner(session)
    admin_role = session.query(Role).filter_by(name="admin", is_system=True).first()
    if not admin_role:
        admin_role = Role(name="admin", is_system=True, description="Admin")
        session.add(admin_role)
        session.flush()

    unique = str(uuid.uuid4())[:8]
    admin = User(id=f"admin-{unique}", email=f"admin-{unique}@test.com", name="Admin")
    session.add(admin)
    session.add(
        WorkspaceMembership(
            user_id=admin.id,
            workspace_id=workspace.id,
            role_id=admin_role.id,
        )
    )
    session.flush()
    session.commit()

    result = asyncio.run(
        workspaces_route.update_workspace_settings(
            workspace_id=workspace.id,
            request=WorkspaceSettingsUpdateRequest(country="UY", language_style="es_uy_formal"),
            user_id=admin.id,
            session=session,
        )
    )
    assert result.country == "UY"


def test_viewer_cannot_update_workspace_settings(session):
    workspace, owner = _create_workspace_with_owner(session)
    unique = str(uuid.uuid4())[:8]
    viewer = User(
        id=f"viewer-{unique}",
        email=f"viewer-{unique}@test.com",
        name="Viewer",
    )
    session.add(viewer)
    session.flush()
    session.commit()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            workspaces_route.update_workspace_settings(
                workspace_id=workspace.id,
                request=WorkspaceSettingsUpdateRequest(country="UY"),
                user_id=viewer.id,
                session=session,
            )
        )

    assert exc.value.status_code == 403
