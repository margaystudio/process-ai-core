"""Tests del hook de capa semántica en el import de documentos.

Bug de gobernanza (fix en api/routes/documents/crud.py::import_documents):
el pipeline semántico solo se disparaba al aprobar por el flujo de validación.
El import con requires_approval=false crea la versión ya APPROVED, así que también
debe encolar trigger_semantic_pipeline_for_version — sino ese documento nunca entra
a la red de conocimiento.

Estrategia (misma que test_cross_tenant_isolation.py):
  - TestClient con _decode_and_verify_supabase_jwt y fetch_workspace_context
    mockeados → controlamos el contexto sin JWT reales ni margay-workspace levantado.
  - sync_workspace_access corre el flujo REAL: crea Workspace, User y Membership.
  - has_permission / can_create_in_folder se mockean en el módulo de ruta para no
    depender de seed_permissions (igual que los demás tests de documents).

Espía del hook:
  Reemplazamos trigger_semantic_pipeline_for_version (el callable que el endpoint
  encola vía background_tasks.add_task) por un MagicMock. TestClient ejecuta las
  BackgroundTasks de forma síncrona al terminar el request, así que el mock queda
  registrado con el/los version_id encolados — sin correr trabajo semántico real.
  Si el fix se revierte (se saca el add_task), el mock nunca se llama → caso 1 rojo.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.workspace_client import (
    WorkspaceApplication,
    WorkspaceSessionContext,
    WorkspaceTenant,
    WorkspaceUser,
    _cache_clear,
)
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    DocumentVersion,
    Folder,
    User,
    Workspace,
    WorkspaceMembership,
)


# ── Identidad única por sesión de test ───────────────────────────────────────

_RUN_ID = str(uuid.uuid4())[:8]
TENANT_ID = f"sem-tenant-{_RUN_ID}"
SUB = f"sem-sub-{_RUN_ID}"
EMAIL = f"user-{_RUN_ID}@sem.com"
TOKEN = f"fake-token-sem-{_RUN_ID}"


def _make_ctx() -> WorkspaceSessionContext:
    return WorkspaceSessionContext(
        user=WorkspaceUser(id=SUB, email=EMAIL, first_name="Test", last_name="User"),
        platform_roles=[],
        tenant_roles=["tenant_admin"],
        tenant=WorkspaceTenant(id=TENANT_ID, name="Sem Tenant", slug=f"sem-{_RUN_ID}"),
        tenants=[WorkspaceTenant(id=TENANT_ID, name="Sem Tenant", slug=f"sem-{_RUN_ID}")],
        applications=[WorkspaceApplication(key="process_ai", name="Process AI", type="module")],
    )


CTX = _make_ctx()
_JWT_PAYLOAD = {"sub": SUB, "email": EMAIL, "exp": 9_999_999_999}


def _mock_decode_jwt(token: str) -> dict:
    if token == TOKEN:
        return _JWT_PAYLOAD
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid token")


def _mock_fetch_ctx(token: str, active_tenant_id: str | None = None) -> WorkspaceSessionContext:
    if token == TOKEN:
        return CTX
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid token")


def _membership_based_has_permission(session, user_id, workspace_id, permission_name):
    """True si el usuario tiene membership en el workspace (sin depender de seeds)."""
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    return membership is not None


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def clear_ws_cache_module():
    _cache_clear()
    yield
    _cache_clear()


@pytest.fixture(scope="module")
def client():
    with patch(
        "api.dependencies._decode_and_verify_supabase_jwt",
        side_effect=_mock_decode_jwt,
    ):
        with patch(
            "api.workspace_client.fetch_workspace_context",
            side_effect=_mock_fetch_ctx,
        ):
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


@pytest.fixture
def spy_pipeline(monkeypatch):
    """Reemplaza el hook semántico por un MagicMock y también neutraliza las
    dependencias del endpoint que dependen de seeds/planes (permisos y límite de
    storage), para aislar el test al comportamiento que nos importa: el encolado."""
    import api.routes.documents.crud as docs_route

    spy = MagicMock(name="trigger_semantic_pipeline_for_version")
    monkeypatch.setattr(docs_route, "trigger_semantic_pipeline_for_version", spy)
    monkeypatch.setattr(docs_route, "has_permission", _membership_based_has_permission)
    monkeypatch.setattr(docs_route, "can_create_in_folder", lambda *a, **k: True)
    # enforce_storage_limit se importa lazy desde db.helpers dentro del endpoint.
    monkeypatch.setattr(
        "process_ai_core.db.helpers.enforce_storage_limit", lambda *a, **k: None
    )
    return spy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _h() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _trigger_sync(client: TestClient) -> None:
    client.get("/api/v1/folders", headers=_h())


def _root_folder_id() -> str:
    with get_db_session() as s:
        ws = s.query(Workspace).filter_by(tenant_id=TENANT_ID).first()
        assert ws is not None, "sync debe haber creado el workspace"
        folder = s.query(Folder).filter_by(workspace_id=ws.id, parent_id=None).first()
        assert folder is not None, "sync debe haber creado la carpeta raíz"
        return str(folder.id)


def _approved_version_id(document_id: str) -> str:
    with get_db_session() as s:
        version = (
            s.query(DocumentVersion)
            .filter_by(document_id=document_id, version_status="APPROVED")
            .one()
        )
        return str(version.id)


def _import(client: TestClient, folder_id: str, requires_approval: str, filenames: list[str]):
    files = [
        ("files", (name, f"Contenido de {name}".encode("utf-8"), "text/plain"))
        for name in filenames
    ]
    return client.post(
        "/api/v1/documents/import",
        data={"folder_id": folder_id, "requires_approval": requires_approval},
        files=files,
        headers=_h(),
    )


# ── Tests ───────────────────────────────────────────────────────────────────

def test_import_sin_aprobacion_encola_pipeline_por_documento(client, spy_pipeline):
    """requires_approval=false → se encola trigger_semantic_pipeline_for_version
    una vez por documento, con el version.id APPROVED correcto."""
    _trigger_sync(client)
    folder_id = _root_folder_id()

    resp = _import(
        client, folder_id, "false", [f"a-{_RUN_ID}.txt", f"b-{_RUN_ID}.txt"]
    )
    assert resp.status_code == 200, resp.text
    docs = resp.json()
    assert len(docs) == 2

    # El hook debe haberse encolado (y ejecutado por TestClient) 1 vez por doc.
    assert spy_pipeline.call_count == 2, (
        f"esperado 1 encolado por documento importado, obtuvo {spy_pipeline.call_count}"
    )

    # Y con el version.id APPROVED correcto de cada documento.
    expected_version_ids = {_approved_version_id(d["id"]) for d in docs}
    called_version_ids = {c.args[0] for c in spy_pipeline.call_args_list}
    assert called_version_ids == expected_version_ids, (
        f"se encolaron los version_id {called_version_ids}, "
        f"esperados {expected_version_ids}"
    )


def test_import_con_aprobacion_no_encola_pipeline(client, spy_pipeline):
    """requires_approval=true → NO se encola nada (el pipeline se dispara luego,
    al aprobarse por el flujo de validación)."""
    _trigger_sync(client)
    folder_id = _root_folder_id()

    resp = _import(client, folder_id, "true", [f"draft-{_RUN_ID}.txt"])
    assert resp.status_code == 200, resp.text
    docs = resp.json()
    assert len(docs) == 1

    assert spy_pipeline.call_count == 0, (
        "con requires_approval=true no debe encolarse el pipeline semántico; "
        f"se encoló {spy_pipeline.call_count} vez/veces"
    )

    # Sanity: la versión importada quedó en DRAFT, no APPROVED.
    with get_db_session() as s:
        version = (
            s.query(DocumentVersion).filter_by(document_id=docs[0]["id"]).one()
        )
        assert version.version_status == "DRAFT"
