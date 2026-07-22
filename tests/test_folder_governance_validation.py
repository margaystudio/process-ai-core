"""Gobierno de carpetas: validación de default_document_type + aislamiento cross-tenant.

Cubre los dos pendientes del review de Config·Carpetas (GDD-39/41):
- El PUT debe rechazar un `default_document_type` que no exista (o esté inactivo) en el
  workspace de la carpeta. `null` sigue siendo válido (= heredar del padre).
- Un tenant no puede editar el gobierno de una carpeta de otro workspace (404, sin
  filtrar su existencia).
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.models.requests import FolderUpdateRequest
from api.routes import folders as folders_route
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import DocumentType, Folder, Workspace


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


def _workspace_con_carpeta(session) -> tuple[Workspace, Folder]:
    uid = str(uuid.uuid4())[:8]
    workspace = Workspace(
        id=f"gov-ws-{uid}",
        slug=f"gov-ws-{uid}",
        name="Workspace gobierno",
        workspace_type="organization",
    )
    folder = Folder(
        id=f"gov-folder-{uid}",
        workspace_id=workspace.id,
        name="Carpeta",
        path="Carpeta",
        parent_id=None,
    )
    session.add_all([workspace, folder])
    session.flush()
    session.commit()
    return workspace, folder


def _permitir_escritura(monkeypatch, workspace_id: str) -> None:
    """Deja pasar membresía/permisos para aislar lo que se está testeando."""
    monkeypatch.setattr(folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace_id)
    monkeypatch.setattr(
        folders_route, "get_user_role", lambda *_a, **_k: SimpleNamespace(name="admin")
    )
    monkeypatch.setattr(folders_route, "can_create_in_folder", lambda *_a, **_k: True)


def _put(session, folder_id: str, request: FolderUpdateRequest):
    return asyncio.run(
        folders_route.update_folder_endpoint(
            folder_id=folder_id,
            request=request,
            user_id="user-gobierno",
            session=session,
            ctx=None,
        )
    )


def test_default_document_type_inexistente_da_400(session, monkeypatch):
    workspace, folder = _workspace_con_carpeta(session)
    _permitir_escritura(monkeypatch, workspace.id)

    with pytest.raises(HTTPException) as exc:
        _put(session, folder.id, FolderUpdateRequest(default_document_type="tipo_que_no_existe"))

    assert exc.value.status_code == 400
    assert "no existe" in str(exc.value.detail).lower()


def test_default_document_type_de_otro_workspace_da_400(session, monkeypatch):
    """Un tipo que existe pero pertenece a OTRO workspace tampoco es válido acá."""
    workspace_a, folder_a = _workspace_con_carpeta(session)
    workspace_b, _folder_b = _workspace_con_carpeta(session)
    session.add(DocumentType(workspace_id=workspace_b.id, key="solo_de_b", label="Solo de B"))
    session.commit()

    _permitir_escritura(monkeypatch, workspace_a.id)

    with pytest.raises(HTTPException) as exc:
        _put(session, folder_a.id, FolderUpdateRequest(default_document_type="solo_de_b"))

    assert exc.value.status_code == 400


def test_default_document_type_valido_persiste(session, monkeypatch):
    workspace, folder = _workspace_con_carpeta(session)
    session.add(DocumentType(workspace_id=workspace.id, key="procedimiento", label="Procedimiento"))
    session.commit()

    _permitir_escritura(monkeypatch, workspace.id)
    _put(session, folder.id, FolderUpdateRequest(default_document_type="procedimiento"))

    session.refresh(folder)
    assert folder.default_document_type == "procedimiento"


def test_default_document_type_null_resetea_a_heredar(session, monkeypatch):
    """null significa 'heredar del padre': no se valida y debe persistirse."""
    workspace, folder = _workspace_con_carpeta(session)
    session.add(DocumentType(workspace_id=workspace.id, key="instructivo", label="Instructivo"))
    session.commit()
    _permitir_escritura(monkeypatch, workspace.id)

    _put(session, folder.id, FolderUpdateRequest(default_document_type="instructivo"))
    session.refresh(folder)
    assert folder.default_document_type == "instructivo"

    _put(session, folder.id, FolderUpdateRequest(default_document_type=None))
    session.refresh(folder)
    assert folder.default_document_type is None


def test_otro_tenant_no_puede_editar_el_gobierno(session, monkeypatch):
    """Aislamiento: con el workspace activo de B, editar una carpeta de A da 404."""
    _workspace_a, folder_a = _workspace_con_carpeta(session)
    workspace_b, _folder_b = _workspace_con_carpeta(session)

    # Workspace activo = B, pero la carpeta es de A.
    _permitir_escritura(monkeypatch, workspace_b.id)

    with pytest.raises(HTTPException) as exc:
        _put(session, folder_a.id, FolderUpdateRequest(name="hackeado por B"))

    assert exc.value.status_code == 404, "no debe filtrar la existencia de la carpeta de otro tenant"
