import asyncio
import json
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from api.routes import documents as documents_route
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import DocumentVersion, Folder, Process, Workspace


@pytest.fixture
def session():
    with get_db_session() as db_session:
        yield db_session


def test_get_document_devuelve_preguntas_abiertas_en_metadata(monkeypatch, session):
    unique_id = str(uuid.uuid4())[:8]
    workspace = Workspace(
        id=f"test-workspace-{unique_id}",
        slug=f"test-workspace-{unique_id}",
        name="Test Workspace",
        workspace_type="organization",
    )
    folder = Folder(
        id=f"test-folder-{unique_id}",
        workspace_id=workspace.id,
        name="Test Folder",
        path="Test",
    )
    doc = Process(
        id=f"test-doc-{unique_id}",
        workspace_id=workspace.id,
        folder_id=folder.id,
        document_type="process",
        name="Test Process",
        description="Test",
        status="approved",
    )
    session.add(workspace)
    session.add(folder)
    session.add(doc)
    session.flush()

    approved_question = "Aprobada: definir responsable final."
    draft_question = "Draft: esto no debería exponerse."
    approved_version = DocumentVersion(
        id=f"approved-version-{unique_id}",
        document_id=doc.id,
        version_number=1,
        version_status="APPROVED",
        content_type="generated",
        content_json=json.dumps({"preguntas_abiertas": approved_question}),
        content_markdown="# Approved",
        is_current=True,
    )
    draft_version = DocumentVersion(
        id=f"draft-version-{unique_id}",
        document_id=doc.id,
        version_number=2,
        version_status="DRAFT",
        content_type="manual_edit",
        content_json=json.dumps({"preguntas_abiertas": draft_question}),
        content_markdown="# Draft",
        is_current=False,
    )
    session.add(approved_version)
    session.add(draft_version)
    session.flush()
    doc.approved_version_id = approved_version.id
    session.commit()

    @contextmanager
    def fake_db_session():
        yield session

    monkeypatch.setattr(documents_route, "get_db_session", fake_db_session)
    monkeypatch.setattr(documents_route, "has_permission", lambda *_args, **_kwargs: True)
    import process_ai_core.db.permissions as permissions_module

    monkeypatch.setattr(
        permissions_module,
        "get_user_role",
        lambda *_args, **_kwargs: SimpleNamespace(name="viewer"),
    )

    response = asyncio.run(documents_route.get_document(doc.id, user_id="test-user"))

    assert response.metadata == {"preguntas_abiertas": approved_question}
