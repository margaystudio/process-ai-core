import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routes import folders as folders_route
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Folder, Workspace


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


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
    _, folder = _create_workspace_and_folder(session)

    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(folders_route, "get_user_role", lambda *_args, **_kwargs: None)

    resp = asyncio.run(
        folders_route.get_folder_permissions(
            folder_id=folder.id,
            user_id="superadmin-user",
            session=session,
        )
    )

    assert resp["folder_id"] == folder.id
    assert "operational_role_ids" in resp


def test_viewer_miembro_devuelve_403(session, monkeypatch):
    _, folder = _create_workspace_and_folder(session)

    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(folders_route, "get_user_role", lambda *_args, **_kwargs: SimpleNamespace(name="viewer"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            folders_route.get_folder_permissions(
                folder_id=folder.id,
                user_id="viewer-user",
                session=session,
            )
        )

    assert exc.value.status_code == 403


def test_admin_miembro_devuelve_200(session, monkeypatch):
    _, folder = _create_workspace_and_folder(session)

    monkeypatch.setattr(folders_route, "is_superadmin", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(folders_route, "get_user_role", lambda *_args, **_kwargs: SimpleNamespace(name="admin"))

    resp = asyncio.run(
        folders_route.get_folder_permissions(
            folder_id=folder.id,
            user_id="admin-user",
            session=session,
        )
    )

    assert resp["folder_id"] == folder.id

