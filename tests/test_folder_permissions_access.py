import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.models.requests import FolderPermissionsUpdateRequest
from api.routes import folders as folders_route
from process_ai_core.db.database import Base
from process_ai_core.db.models import Folder, FolderPermission, OperationalRole, Workspace


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        Workspace.__table__,
        Folder.__table__,
        OperationalRole.__table__,
        FolderPermission.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    test_session = sessionmaker(bind=engine)()
    try:
        yield test_session
    finally:
        test_session.close()
        engine.dispose()


def _create_workspace_and_folder(session, *, workspace_type: str = "organization"):
    unique_id = str(uuid.uuid4())[:8]
    workspace = Workspace(
        id=f"test-workspace-{unique_id}",
        slug=f"test-workspace-{unique_id}",
        name="Test Workspace",
        workspace_type=workspace_type,
    )
    folder = Folder(
        id=f"test-folder-{unique_id}",
        workspace_id=workspace.id,
        name="Test Folder",
        path="Test",
        parent_id=None,
    )
    session.add(workspace)
    session.add(folder)
    session.flush()
    session.commit()
    return workspace, folder


def test_superadmin_puede_ver_permissions(session, monkeypatch):
    workspace, folder = _create_workspace_and_folder(session)

    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(folders_route, "get_user_role", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id)

    resp = asyncio.run(
        folders_route.get_folder_permissions(
            folder_id=folder.id,
            user_id="superadmin-user",
            session=session,
            ctx=None,
        )
    )

    assert resp["folder_id"] == folder.id
    assert "operational_role_ids" in resp


def test_viewer_miembro_devuelve_403(session, monkeypatch):
    workspace, folder = _create_workspace_and_folder(session)

    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(folders_route, "get_user_role", lambda *_args, **_kwargs: SimpleNamespace(name="viewer"))
    monkeypatch.setattr(folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            folders_route.get_folder_permissions(
                folder_id=folder.id,
                user_id="viewer-user",
                session=session,
                ctx=None,
            )
        )

    assert exc.value.status_code == 403


def test_admin_miembro_devuelve_200(session, monkeypatch):
    workspace, folder = _create_workspace_and_folder(session)

    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(folders_route, "get_user_role", lambda *_args, **_kwargs: SimpleNamespace(name="admin"))
    monkeypatch.setattr(folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id)

    resp = asyncio.run(
        folders_route.get_folder_permissions(
            folder_id=folder.id,
            user_id="admin-user",
            session=session,
            ctx=None,
        )
    )

    assert resp["folder_id"] == folder.id


def _create_permission_tree(session):
    workspace, root = _create_workspace_and_folder(session)
    root.name = "Carpeta origen"
    root.inherits_permissions = False
    child = Folder(
        id=f"test-child-{uuid.uuid4()}",
        workspace_id=workspace.id,
        name="Carpeta hija",
        path="Test/Child",
        parent_id=root.id,
        inherits_permissions=True,
    )
    role = OperationalRole(
        id=f"test-role-{uuid.uuid4()}",
        workspace_id=workspace.id,
        name="Operaciones",
        slug=f"operaciones-{uuid.uuid4()}",
    )
    session.add_all([child, role])
    session.flush()
    session.add(
        FolderPermission(
            id=f"test-permission-{uuid.uuid4()}",
            folder_id=root.id,
            operational_role_id=role.id,
        )
    )
    session.commit()
    return workspace, root, child, role


def _allow_admin(monkeypatch, workspace_id):
    monkeypatch.setattr(
        folders_route,
        "get_user_role",
        lambda *_args, **_kwargs: SimpleNamespace(name="admin"),
    )
    monkeypatch.setattr(folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace_id)


def test_get_permissions_devuelve_roles_heredados_y_origen(session, monkeypatch):
    workspace, root, child, role = _create_permission_tree(session)
    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: False)
    _allow_admin(monkeypatch, workspace.id)

    resp = asyncio.run(
        folders_route.get_folder_permissions(
            folder_id=child.id,
            user_id="admin-user",
            session=session,
            ctx=None,
        )
    )

    assert resp["inherits_permissions"] is True
    assert resp["operational_role_ids"] == [role.id]
    assert resp["origin"] == "heredado"
    assert resp["from"] == root.name


def test_get_permissions_devuelve_origen_personalizado(session, monkeypatch):
    workspace, root, _child, role = _create_permission_tree(session)
    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: False)
    _allow_admin(monkeypatch, workspace.id)

    resp = asyncio.run(
        folders_route.get_folder_permissions(
            folder_id=root.id,
            user_id="admin-user",
            session=session,
            ctx=None,
        )
    )

    assert resp["inherits_permissions"] is False
    assert resp["operational_role_ids"] == [role.id]
    assert resp["origin"] == "personalizado"
    assert resp["from"] is None


def test_put_permissions_reemplaza_roles_personalizados(session, monkeypatch):
    workspace, _root, child, inherited_role = _create_permission_tree(session)
    own_role = OperationalRole(
        id=f"test-role-{uuid.uuid4()}",
        workspace_id=workspace.id,
        name="Administracion",
        slug=f"administracion-{uuid.uuid4()}",
    )
    session.add(own_role)
    session.commit()
    _allow_admin(monkeypatch, workspace.id)

    asyncio.run(
        folders_route.update_folder_permissions(
            folder_id=child.id,
            request=FolderPermissionsUpdateRequest(
                inherits_permissions=False,
                operational_role_ids=[own_role.id],
            ),
            user_id="admin-user",
            session=session,
            ctx=None,
        )
    )

    session.refresh(child)
    stored_role_ids = {
        row[0]
        for row in session.query(FolderPermission.operational_role_id)
        .filter_by(folder_id=child.id)
        .all()
    }
    assert child.inherits_permissions is False
    assert stored_role_ids == {own_role.id}
    assert inherited_role.id not in stored_role_ids


def test_put_permissions_materializa_roles_al_cortar_herencia(session, monkeypatch):
    workspace, _root, child, role = _create_permission_tree(session)
    _allow_admin(monkeypatch, workspace.id)

    asyncio.run(
        folders_route.update_folder_permissions(
            folder_id=child.id,
            request=FolderPermissionsUpdateRequest(inherits_permissions=False),
            user_id="admin-user",
            session=session,
            ctx=None,
        )
    )

    session.refresh(child)
    stored_role_ids = [
        row[0]
        for row in session.query(FolderPermission.operational_role_id)
        .filter_by(folder_id=child.id)
        .all()
    ]
    assert child.inherits_permissions is False
    assert stored_role_ids == [role.id]


def test_put_permissions_rechaza_lista_si_la_carpeta_hereda(session, monkeypatch):
    workspace, _root, child, role = _create_permission_tree(session)
    _allow_admin(monkeypatch, workspace.id)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            folders_route.update_folder_permissions(
                folder_id=child.id,
                request=FolderPermissionsUpdateRequest(operational_role_ids=[role.id]),
                user_id="admin-user",
                session=session,
                ctx=None,
            )
        )

    assert exc.value.status_code == 400

