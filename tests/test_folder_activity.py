import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.routes import folders as folders_route
from process_ai_core.db.database import Base
from process_ai_core.db.models import AuditLog, Folder, User, Workspace


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    try:
        yield test_session
    finally:
        test_session.close()
        engine.dispose()


def _workspace_folder(session, suffix: str) -> tuple[Workspace, Folder]:
    workspace = Workspace(
        id=f"activity-ws-{suffix}",
        slug=f"activity-ws-{suffix}",
        name=f"Workspace {suffix}",
        workspace_type="organization",
    )
    folder = Folder(
        id=f"activity-folder-{suffix}",
        workspace_id=workspace.id,
        name=f"Carpeta {suffix}",
        path=f"Carpeta {suffix}",
    )
    session.add_all([workspace, folder])
    session.flush()
    return workspace, folder


def test_folder_activity_isolated_by_workspace(session, monkeypatch):
    suffix = str(uuid.uuid4())[:8]
    workspace_a, folder_a = _workspace_folder(session, f"a-{suffix}")
    workspace_b, folder_b = _workspace_folder(session, f"b-{suffix}")
    actor = User(
        id=f"activity-user-{suffix}",
        email=f"activity-{suffix}@example.com",
        name="Ana Auditora",
    )
    session.add(actor)
    session.flush()
    session.add_all(
        [
            AuditLog(
                folder_id=folder_a.id,
                document_id=None,
                user_id=actor.id,
                action="folder.updated",
                entity_type="folder",
                entity_id=folder_a.id,
            ),
            AuditLog(
                folder_id=folder_b.id,
                document_id=None,
                user_id=actor.id,
                action="folder.permissions_updated",
                entity_type="folder",
                entity_id=folder_b.id,
            ),
        ]
    )
    session.commit()

    monkeypatch.setattr(
        folders_route,
        "resolve_tenant_workspace_id",
        lambda _ctx: workspace_a.id,
    )
    monkeypatch.setattr(folders_route, "_require_workspace_member", lambda *_args: None)
    monkeypatch.setattr(folders_route, "can_view_folder", lambda *_args: True)

    response = folders_route.get_folder_activity(
        folder_id=folder_a.id,
        page=1,
        page_size=20,
        user_id=actor.id,
        session=session,
        ctx=None,
    )

    assert response["total"] == 1
    assert response["items"][0]["action"] == "folder.updated"
    assert response["items"][0]["actor"]["name"] == "Ana Auditora"

    with pytest.raises(HTTPException) as exc:
        folders_route.get_folder_activity(
            folder_id=folder_b.id,
            page=1,
            page_size=20,
            user_id=actor.id,
            session=session,
            ctx=None,
        )
    assert exc.value.status_code == 404
