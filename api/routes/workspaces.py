"""
Endpoint para gestionar workspaces (clientes/organizaciones).

Este endpoint maneja:
- POST /api/v1/workspaces: Crear un nuevo workspace
- GET /api/v1/workspaces: Listar workspaces
- GET /api/v1/workspaces/{workspace_id}: Obtener un workspace
- POST /api/v1/workspaces/{workspace_id}/branding/icon: Subir icono personalizado
- DELETE /api/v1/workspaces/{workspace_id}/branding/icon: Eliminar icono personalizado
"""

import json
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from process_ai_core.db.database import get_db_session
from ..dependencies import get_db
from process_ai_core.db.helpers import (
    add_user_to_workspace_helper,
)
from process_ai_core.config import get_settings
from process_ai_core.db.models import Workspace, WorkspaceMembership, User, Role
from process_ai_core.db.models import UserOperationalRole
from ..dependencies import get_current_user_id
from ..models.requests import WorkspaceResponse, WorkspaceBrandingUpdateRequest

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])

ALLOWED_BRANDING_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_BRANDING_ICON_SIZE_BYTES = 2 * 1024 * 1024
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _get_workspace_branding(workspace: Workspace) -> dict:
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    branding = metadata.get("branding") or {}
    if not isinstance(branding, dict):
        return {}
    return branding


def _get_workspace_branding_icon_filename(workspace: Workspace) -> str | None:
    branding = _get_workspace_branding(workspace)
    filename = branding.get("client_icon_filename")
    return filename if isinstance(filename, str) and filename.strip() else None


def _get_workspace_branding_color(workspace: Workspace, key: str) -> str | None:
    branding = _get_workspace_branding(workspace)
    color = branding.get(key)
    if isinstance(color, str) and HEX_COLOR_RE.match(color):
        return color.upper()
    return None


def _build_branding_icon_url(workspace_id: str, filename: str | None) -> str | None:
    if not filename:
        return None
    return f"/api/v1/workspaces/{workspace_id}/branding/icon/{filename}"


def _serialize_workspace(workspace: Workspace, role: str | None = None) -> WorkspaceResponse:
    filename = _get_workspace_branding_icon_filename(workspace)
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        workspace_type=workspace.workspace_type,
        role=role,
        branding_icon_url=_build_branding_icon_url(workspace.id, filename),
        branding_primary_color=_get_workspace_branding_color(workspace, "primary_color"),
        branding_secondary_color=_get_workspace_branding_color(workspace, "secondary_color"),
        created_at=workspace.created_at.isoformat(),
    )


def _get_workspace_role_name(session: Session, user_id: str, workspace_id: str) -> str | None:
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    if not membership:
        return None
    if membership.role_id:
        role = session.query(Role).filter_by(id=membership.role_id).first()
        if role:
            return role.name
    return membership.role


def _require_workspace_branding_access(session: Session, user_id: str, workspace_id: str) -> None:
    role_name = _get_workspace_role_name(session, user_id, workspace_id)
    if role_name not in {"owner", "creator"}:
        raise HTTPException(
            status_code=403,
            detail="Solo los roles owner o creator pueden personalizar el icono del workspace",
        )


def _save_workspace_branding(workspace: Workspace, branding: dict) -> None:
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    metadata["branding"] = branding
    workspace.metadata_json = json.dumps(metadata)


def _validate_hex_color(color: str, field_name: str) -> str:
    normalized = color.strip().upper()
    if not HEX_COLOR_RE.match(normalized):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} debe tener formato hexadecimal #RRGGBB",
        )
    return normalized



@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces():
    """
    Lista todos los workspaces (clientes/organizaciones).

    Returns:
        Lista de WorkspaceResponse
    """
    with get_db_session() as session:
        workspaces = session.query(Workspace).filter_by(workspace_type="organization").all()
        return [_serialize_workspace(w) for w in workspaces]


@router.get("/{workspace_id}/members")
async def get_workspace_members(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Lista los miembros del workspace (memberships) con usuario, rol de sistema y roles operativos.
    Requiere ser miembro del workspace (owner/admin para gestión).
    """
    from process_ai_core.db.permissions import get_user_role
    role = get_user_role(session, user_id, workspace_id)
    if not role:
        raise HTTPException(status_code=403, detail="No eres miembro de este workspace")
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    memberships = session.query(WorkspaceMembership).filter_by(workspace_id=workspace_id).all()
    out = []
    for m in memberships:
        user = session.query(User).filter_by(id=m.user_id).first()
        role_obj = session.query(Role).filter_by(id=m.role_id).first() if m.role_id else None
        role_name = role_obj.name if role_obj else (m.role or "")
        op_roles = session.query(UserOperationalRole).filter_by(workspace_membership_id=m.id).all()
        op_role_ids = [r.operational_role_id for r in op_roles]
        out.append({
            "membership_id": m.id,
            "user_id": m.user_id,
            "email": user.email if user else "",
            "name": user.name if user else "",
            "role": role_name,
            "operational_role_ids": op_role_ids,
        })
    return {"workspace_id": workspace_id, "members": out}


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str):
    """
    Obtiene un workspace por su ID.

    Args:
        workspace_id: ID del workspace

    Returns:
        WorkspaceResponse

    Raises:
        404: Si el workspace no existe
    """
    with get_db_session() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id).first()
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace {workspace_id} no encontrado"
            )

        return _serialize_workspace(workspace)


@router.post("/{workspace_id}/branding/icon")
async def upload_workspace_branding_icon(
    workspace_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Sube un icono personalizado del workspace para mostrarlo junto a la marca Process AI.
    Solo accesible para roles owner o creator.
    """
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")

    _require_workspace_branding_access(session, user_id, workspace_id)

    ext = Path(file.filename or "icon.png").suffix.lower() or ".png"
    if ext not in ALLOWED_BRANDING_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Usa PNG, JPG, JPEG, WEBP o SVG.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(contents) > MAX_BRANDING_ICON_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="El icono no puede superar 2 MB")

    settings = get_settings()
    branding_dir = Path(settings.output_dir) / "workspace-branding" / workspace_id
    branding_dir.mkdir(parents=True, exist_ok=True)

    previous_filename = _get_workspace_branding_icon_filename(workspace)
    if previous_filename:
        previous_path = branding_dir / previous_filename
        if previous_path.exists():
            previous_path.unlink(missing_ok=True)

    filename = f"{uuid4().hex}{ext}"
    target_path = branding_dir / filename
    try:
        target_path.write_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail="No se pudo guardar el icono") from e

    branding = _get_workspace_branding(workspace)
    branding["client_icon_filename"] = filename
    _save_workspace_branding(workspace, branding)
    session.flush()

    return {
        "icon_url": _build_branding_icon_url(workspace_id, filename),
    }


@router.delete("/{workspace_id}/branding/icon")
async def delete_workspace_branding_icon(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Elimina el icono personalizado del workspace.
    Solo accesible para roles owner o creator.
    """
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")

    _require_workspace_branding_access(session, user_id, workspace_id)

    filename = _get_workspace_branding_icon_filename(workspace)
    if filename:
        settings = get_settings()
        branding_dir = Path(settings.output_dir) / "workspace-branding" / workspace_id
        icon_path = branding_dir / filename
        if icon_path.exists():
            icon_path.unlink(missing_ok=True)

    branding = _get_workspace_branding(workspace)
    branding.pop("client_icon_filename", None)
    branding.pop("primary_color", None)
    branding.pop("secondary_color", None)
    _save_workspace_branding(workspace, branding)
    session.flush()

    return {"icon_url": None}


@router.put("/{workspace_id}/branding")
async def update_workspace_branding(
    workspace_id: str,
    request: WorkspaceBrandingUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Actualiza los dos colores principales del branding del workspace.
    Solo accesible para roles owner o creator.
    """
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")

    _require_workspace_branding_access(session, user_id, workspace_id)

    primary_color = _validate_hex_color(request.primary_color, "primary_color")
    secondary_color = _validate_hex_color(request.secondary_color, "secondary_color")

    branding = _get_workspace_branding(workspace)
    branding["primary_color"] = primary_color
    branding["secondary_color"] = secondary_color
    _save_workspace_branding(workspace, branding)
    session.flush()

    return {
        "primary_color": primary_color,
        "secondary_color": secondary_color,
    }


@router.get("/{workspace_id}/branding/icon/{filename}")
async def get_workspace_branding_icon(workspace_id: str, filename: str):
    """
    Sirve el icono personalizado del workspace.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")

    settings = get_settings()
    base_dir = Path(settings.output_dir) / "workspace-branding" / workspace_id
    file_path = base_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Icono no encontrado")

    try:
        file_path.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    return FileResponse(path=str(file_path), filename=filename)

