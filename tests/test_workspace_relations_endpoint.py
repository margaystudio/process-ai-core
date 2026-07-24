"""Contrato y aislamiento de la bandeja global de relaciones."""

import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa: F401
import process_ai_core.db.models_semantic  # noqa: F401
from api.routes import semantic
from api.workspace_client import WorkspaceSessionContext, WorkspaceTenant, WorkspaceUser
from process_ai_core.db.database import Base
from process_ai_core.db.models import Folder, Process, Workspace
from process_ai_core.db.models_semantic import DocumentRelation, KnowledgeObject


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


def _ctx(workspace_id: str) -> WorkspaceSessionContext:
    tenant = WorkspaceTenant(id=workspace_id, name=workspace_id, slug=workspace_id)
    return WorkspaceSessionContext(
        user=WorkspaceUser(id=_uid(), email=f"{workspace_id}@example.com"),
        platform_roles=[],
        tenant_roles=["tenant_admin"],
        tenant=tenant,
        tenants=[tenant],
    )


def _workspace_data(session, workspace_id: str, confidence_values: list[float]):
    workspace = Workspace(
        id=workspace_id,
        tenant_id=workspace_id,
        slug=workspace_id,
        name=workspace_id,
        workspace_type="organization",
    )
    folder = Folder(
        id=_uid(),
        workspace_id=workspace_id,
        name=f"Folder {workspace_id}",
        path=f"Folder {workspace_id}",
    )
    document = Process(
        id=_uid(),
        workspace_id=workspace_id,
        folder_id=folder.id,
        document_type="procedimiento",
        name=f"Documento {workspace_id}",
        status="approved",
    )
    target = KnowledgeObject(
        id=_uid(),
        workspace_id=workspace_id,
        type="sistema",
        canonical_name=f"Sistema {workspace_id}",
        normalized_name=f"sistema {workspace_id}",
    )
    session.add_all([workspace, folder, document, target])
    session.flush()

    relations = []
    for index, confidence in enumerate(confidence_values):
        relation = DocumentRelation(
            id=_uid(),
            workspace_id=workspace_id,
            document_id=document.id,
            source_type="document",
            source_id=document.id,
            relation_type="usa" if index == 0 else "requiere",
            target_type=target.type,
            target_id=target.id,
            confidence=confidence,
            status="candidate",
            created_by_ai=True,
        )
        session.add(relation)
        relations.append(relation)
    session.commit()
    return folder, document, relations


def test_workspace_relations_are_isolated_sorted_filtered_and_paginated(session, monkeypatch):
    folder_a, document_a, relations_a = _workspace_data(session, "workspace-a", [0.72, 0.91])
    _folder_b, _document_b, relations_b = _workspace_data(session, "workspace-b", [0.99])

    monkeypatch.setattr(
        semantic,
        "resolve_tenant_workspace_id",
        lambda ctx: ctx.tenant.id,
    )
    permission_checks = []

    def allow_admin(_session, _user_id, workspace_id, permission_name, **_kwargs):
        permission_checks.append((workspace_id, permission_name))
        return True

    monkeypatch.setattr(semantic, "has_permission", allow_admin)

    first_page = asyncio.run(
        semantic.get_workspace_relations(
            status="candidate",
            relation_type=None,
            folder_id=None,
            page=1,
            page_size=1,
            user_id="admin-a",
            session=session,
            ctx=_ctx("workspace-a"),
        )
    )

    assert first_page.total == 2
    assert first_page.total_pages == 2
    assert [item.id for item in first_page.items] == [relations_a[1].id]
    assert first_page.items[0].document.id == document_a.id
    assert first_page.items[0].document.folder_id == folder_a.id
    assert relations_b[0].id not in {item.id for item in first_page.items}
    assert permission_checks == [("workspace-a", "workspaces.edit")]

    filtered = asyncio.run(
        semantic.get_workspace_relations(
            status="candidate",
            relation_type="usa",
            folder_id=folder_a.id,
            page=1,
            page_size=25,
            user_id="admin-a",
            session=session,
            ctx=_ctx("workspace-a"),
        )
    )

    assert filtered.total == 1
    assert filtered.items[0].id == relations_a[0].id
    assert filtered.items[0].target.name == "Sistema workspace-a"


def test_workspace_relations_requires_workspace_administration_permission(
    session,
    monkeypatch,
):
    _workspace_data(session, "workspace-no-admin", [0.8])
    monkeypatch.setattr(
        semantic,
        "resolve_tenant_workspace_id",
        lambda ctx: ctx.tenant.id,
    )
    monkeypatch.setattr(semantic, "has_permission", lambda *_args, **_kwargs: False)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            semantic.get_workspace_relations(
                status="candidate",
                relation_type=None,
                folder_id=None,
                page=1,
                page_size=25,
                user_id="member",
                session=session,
                ctx=_ctx("workspace-no-admin"),
            )
        )

    assert error.value.status_code == 403
