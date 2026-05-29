"""
Endpoint para gestionar archivos y carpetas jerárquicas de contexto en workspaces.
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Depends, Form, Body
from fastapi.responses import FileResponse
from typing import List
import uuid
import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import ContextFile, ContextFolder, Workspace
from process_ai_core.db.permissions import has_permission
from process_ai_core.config import get_settings

from api.dependencies import get_current_user_id
from ..models.requests import (
    ContextFileMoveRequest,
    ContextFileResponse,
    ContextFolderCreateRequest,
    ContextFolderMoveRequest,
    ContextFolderResponse,
)

router = APIRouter(prefix="/api/v1/workspaces", tags=["context-files"])

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".doc", ".docx"}
TEXT_EXTENSIONS = {".txt", ".md"}


def _get_context_dir(workspace_id: str) -> Path:
    settings = get_settings()
    return Path(settings.output_dir) / "context" / workspace_id


def _guess_media_type(filename: str, fallback: str = "application/octet-stream") -> str:
    media_type, _ = mimetypes.guess_type(filename)
    return media_type or fallback


def _ensure_workspace(session, workspace_id: str) -> Workspace:
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    return workspace


def _ensure_view_permission(session, user_id: str, workspace_id: str) -> None:
    if not has_permission(session, user_id, workspace_id, "workspaces.view") and not has_permission(
        session, user_id, workspace_id, "documents.view"
    ):
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para ver archivos de contexto"
        )


def _ensure_edit_permission(session, user_id: str, workspace_id: str) -> None:
    if not has_permission(session, user_id, workspace_id, "workspaces.edit"):
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para gestionar archivos de contexto"
        )


def _get_context_folder(session, workspace_id: str, folder_id: str | None) -> ContextFolder | None:
    if not folder_id:
        return None
    folder = session.query(ContextFolder).filter_by(id=folder_id, workspace_id=workspace_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Carpeta de contexto no encontrada")
    return folder


def _build_context_folder_path(parent: ContextFolder | None, name: str) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre de la carpeta es requerido")
    return f"{parent.path}/{name}" if parent and parent.path else name


def _is_descendant(session, workspace_id: str, folder_id: str, possible_parent_id: str | None) -> bool:
    current_id = possible_parent_id
    while current_id:
        if current_id == folder_id:
            return True
        current = session.query(ContextFolder).filter_by(id=current_id, workspace_id=workspace_id).first()
        if not current:
            break
        current_id = current.parent_id
    return False


def _update_descendant_paths(session, workspace_id: str, folder: ContextFolder) -> None:
    children = (
        session.query(ContextFolder)
        .filter_by(workspace_id=workspace_id, parent_id=folder.id)
        .order_by(ContextFolder.sort_order.asc(), ContextFolder.name.asc())
        .all()
    )
    for child in children:
        child.path = _build_context_folder_path(folder, child.name)
        _update_descendant_paths(session, workspace_id, child)


def _context_file_response(cf: ContextFile) -> ContextFileResponse:
    return ContextFileResponse(
        id=cf.id,
        workspace_id=cf.workspace_id,
        folder_id=cf.folder_id,
        name=cf.name,
        size=cf.size,
        file_type=cf.file_type,
        content=cf.content,
        created_at=cf.created_at.isoformat(),
    )


def _context_folder_response(folder: ContextFolder) -> ContextFolderResponse:
    return ContextFolderResponse(
        id=folder.id,
        workspace_id=folder.workspace_id,
        name=folder.name,
        path=folder.path,
        parent_id=folder.parent_id,
        sort_order=folder.sort_order,
        created_at=folder.created_at.isoformat(),
    )


@router.get("/{workspace_id}/context-folders", response_model=List[ContextFolderResponse])
async def list_context_folders(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        _ensure_workspace(session, workspace_id)
        _ensure_view_permission(session, user_id, workspace_id)

        folders = (
            session.query(ContextFolder)
            .filter_by(workspace_id=workspace_id)
            .order_by(ContextFolder.path.asc(), ContextFolder.sort_order.asc(), ContextFolder.name.asc())
            .all()
        )
        return [_context_folder_response(folder) for folder in folders]


@router.post("/{workspace_id}/context-folders", response_model=ContextFolderResponse)
async def create_context_folder(
    workspace_id: str,
    request: ContextFolderCreateRequest,
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        _ensure_workspace(session, workspace_id)
        _ensure_edit_permission(session, user_id, workspace_id)

        parent = _get_context_folder(session, workspace_id, request.parent_id)
        folder = ContextFolder(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            name=request.name.strip(),
            parent_id=parent.id if parent else None,
            path=_build_context_folder_path(parent, request.name),
            sort_order=0,
        )
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return _context_folder_response(folder)


@router.patch("/{workspace_id}/context-folders/{folder_id}", response_model=ContextFolderResponse)
async def move_or_update_context_folder(
    workspace_id: str,
    folder_id: str,
    request: ContextFolderMoveRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        _ensure_workspace(session, workspace_id)
        _ensure_edit_permission(session, user_id, workspace_id)

        folder = _get_context_folder(session, workspace_id, folder_id)
        assert folder is not None

        if request.parent_id and _is_descendant(session, workspace_id, folder.id, request.parent_id):
            raise HTTPException(status_code=400, detail="No puede mover una carpeta dentro de sí misma o un descendiente")

        parent = _get_context_folder(session, workspace_id, request.parent_id)
        if request.name is not None:
            folder.name = request.name.strip()
        folder.parent_id = parent.id if parent else None
        folder.path = _build_context_folder_path(parent, folder.name)
        _update_descendant_paths(session, workspace_id, folder)

        session.commit()
        session.refresh(folder)
        return _context_folder_response(folder)


@router.post("/{workspace_id}/context-files", response_model=ContextFileResponse)
async def upload_context_file(
    workspace_id: str,
    file: UploadFile = File(...),
    folder_id: str | None = Form(None),
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        _ensure_workspace(session, workspace_id)
        _ensure_edit_permission(session, user_id, workspace_id)
        folder = _get_context_folder(session, workspace_id, folder_id)

        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        context_dir = _get_context_dir(workspace_id)
        context_dir.mkdir(parents=True, exist_ok=True)

        content_bytes = await file.read()
        content = None
        if ext in TEXT_EXTENSIONS:
            try:
                content = content_bytes.decode("utf-8", errors="replace")
            except Exception:
                content = "(No se pudo leer el contenido)"

        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}{ext}"
        file_path = context_dir / safe_name
        file_path.write_bytes(content_bytes)

        rel_path = f"context/{workspace_id}/{safe_name}"
        cf = ContextFile(
            id=file_id,
            workspace_id=workspace_id,
            folder_id=folder.id if folder else None,
            name=file.filename or safe_name,
            file_path=rel_path,
            content=content,
            file_type=file.content_type or ext,
            size=len(content_bytes),
        )
        session.add(cf)
        session.commit()
        session.refresh(cf)
        return _context_file_response(cf)


@router.get("/{workspace_id}/context-files", response_model=List[ContextFileResponse])
async def list_context_files(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        _ensure_workspace(session, workspace_id)
        _ensure_view_permission(session, user_id, workspace_id)

        files = (
            session.query(ContextFile)
            .filter_by(workspace_id=workspace_id)
            .order_by(ContextFile.created_at.desc())
            .all()
        )
        return [_context_file_response(file) for file in files]


@router.patch("/{workspace_id}/context-files/{file_id}/move", response_model=ContextFileResponse)
async def move_context_file(
    workspace_id: str,
    file_id: str,
    request: ContextFileMoveRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        _ensure_workspace(session, workspace_id)
        _ensure_edit_permission(session, user_id, workspace_id)

        cf = session.query(ContextFile).filter_by(id=file_id, workspace_id=workspace_id).first()
        if not cf:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        folder = _get_context_folder(session, workspace_id, request.folder_id)
        cf.folder_id = folder.id if folder else None
        session.commit()
        session.refresh(cf)
        return _context_file_response(cf)


@router.delete("/{workspace_id}/context-files/{file_id}")
async def delete_context_file(
    workspace_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        cf = session.query(ContextFile).filter_by(id=file_id, workspace_id=workspace_id).first()
        if not cf:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        _ensure_edit_permission(session, user_id, workspace_id)

        settings = get_settings()
        disk_path = Path(settings.output_dir) / cf.file_path
        if disk_path.exists():
            try:
                disk_path.unlink()
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo físico {disk_path}: {e}")

        session.delete(cf)
        session.commit()
        return {"status": "ok"}


@router.get("/{workspace_id}/context-files/{file_id}/download")
async def download_context_file(
    workspace_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        cf = session.query(ContextFile).filter_by(id=file_id, workspace_id=workspace_id).first()
        if not cf:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        _ensure_view_permission(session, user_id, workspace_id)

        settings = get_settings()
        disk_path = Path(settings.output_dir) / cf.file_path
        if not disk_path.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

        return FileResponse(
            path=str(disk_path),
            filename=cf.name,
            media_type=_guess_media_type(cf.name),
        )


@router.get("/{workspace_id}/context-files/{file_id}/view")
async def view_context_file(
    workspace_id: str,
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    with get_db_session() as session:
        cf = session.query(ContextFile).filter_by(id=file_id, workspace_id=workspace_id).first()
        if not cf:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        _ensure_view_permission(session, user_id, workspace_id)

        settings = get_settings()
        disk_path = Path(settings.output_dir) / cf.file_path
        if not disk_path.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

        return FileResponse(
            path=str(disk_path),
            filename=cf.name,
            media_type=_guess_media_type(cf.name),
            content_disposition_type="inline",
        )
