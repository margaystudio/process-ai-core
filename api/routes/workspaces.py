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
import logging
import re
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends
from fastapi import File, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from process_ai_core.storage import get_storage, workspace_branding_key
from process_ai_core.db.database import get_db_session
from ..dependencies import get_db
from process_ai_core.db.helpers import (
    add_user_to_workspace_helper,
)
from process_ai_core.config import get_settings
from process_ai_core.db.models import Workspace, WorkspaceMembership, User, Role
from process_ai_core.db.models import UserOperationalRole
from ..dependencies import get_current_user_id, is_superadmin
from ..models.requests import (
    WorkspaceResponse,
    WorkspaceBrandingUpdateRequest,
    WorkspaceSettingsUpdateRequest,
)
from ..request_identity import capture_request_identity
from ..workspace_client import require_process_ai_access, sync_workspace_access

# require_process_ai_access va por endpoint y no a nivel de router: la ruta del
# icono de branding se carga desde un <link>/<img> del navegador, que no puede
# mandar headers de auth, así que tiene que quedar fuera del gate.
router = APIRouter(
    prefix="/api/v1/workspaces",
    tags=["workspaces"],
    dependencies=[Depends(sync_workspace_access), Depends(capture_request_identity)],
)

logger = logging.getLogger(__name__)

ALLOWED_BRANDING_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
_BRANDING_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def _branding_icon_media_type(filename: str) -> str:
    return _BRANDING_MEDIA_TYPES.get(
        PurePosixPath(filename).suffix.lower(), "application/octet-stream"
    )


def _delete_branding_icon_blob(workspace_id: str, filename: str) -> None:
    """Borra el icono de storage. Best-effort: no romper el flujo si falla."""
    try:
        get_storage().delete(workspace_branding_key(workspace_id, filename))
    except Exception as exc:
        logger.warning(
            "No se pudo borrar el icono %s del workspace %s: %s", filename, workspace_id, exc
        )

MAX_BRANDING_ICON_SIZE_BYTES = 2 * 1024 * 1024
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
ALLOWED_COUNTRY_CODES = frozenset({"UY", "AR", "BR", "CL", "CO", "MX", "ES"})
MAX_CONTEXT_TEXT_LENGTH = 8000
MAX_DESCRIPTION_LENGTH = 500


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
        tenant_id=workspace.tenant_id,
        role=role,
        country=workspace.country,
        business_type=workspace.business_type,
        language_style=workspace.language_style,
        default_audience=workspace.default_audience,
        default_detail_level=workspace.default_detail_level,
        context_text=workspace.context_text,
        description=workspace.description,
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


def _require_workspace_settings_access(session: Session, user_id: str, workspace_id: str) -> None:
    if is_superadmin(user_id, session):
        return
    role_name = _get_workspace_role_name(session, user_id, workspace_id)
    if role_name in {"owner", "creator", "admin"}:
        return
    raise HTTPException(
        status_code=403,
        detail="Solo los roles owner, creator o admin pueden editar la configuración del workspace",
    )


def _normalize_optional_str(value: str | None, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if max_length is not None and len(trimmed) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"El texto no puede superar {max_length} caracteres",
        )
    return trimmed


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



@router.get("", response_model=list[WorkspaceResponse], dependencies=[Depends(require_process_ai_access)])
def list_workspaces(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Lista los workspaces de los que el usuario autenticado es miembro.

    Antes no pedía autenticación y devolvía TODOS los tenants de la
    plataforma. Un superadmin local sigue viendo todos.

    Returns:
        Lista de WorkspaceResponse
    """
    query = session.query(Workspace).filter_by(workspace_type="organization")
    if not is_superadmin(user_id, session):
        query = query.join(
            WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id
        ).filter(WorkspaceMembership.user_id == user_id)
    return [_serialize_workspace(w) for w in query.all()]


@router.get("/{workspace_id}/members", dependencies=[Depends(require_process_ai_access)])
def get_workspace_members(
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
    memberships = (
        session.query(WorkspaceMembership).filter_by(workspace_id=workspace_id).all()
    )

    # Batch-load para evitar N+1 (antes: 3 queries por miembro contra el Postgres
    # remoto). Ahora son 4 queries fijas sin importar la cantidad de miembros.
    user_ids = {m.user_id for m in memberships if m.user_id}
    role_ids = {m.role_id for m in memberships if m.role_id}
    membership_ids = [m.id for m in memberships]

    users_by_id = (
        {u.id: u for u in session.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )
    roles_by_id = (
        {r.id: r for r in session.query(Role).filter(Role.id.in_(role_ids)).all()}
        if role_ids
        else {}
    )
    op_role_ids_by_membership: dict[str, list[str]] = {}
    if membership_ids:
        op_rows = (
            session.query(UserOperationalRole)
            .filter(UserOperationalRole.workspace_membership_id.in_(membership_ids))
            .all()
        )
        for r in op_rows:
            op_role_ids_by_membership.setdefault(
                r.workspace_membership_id, []
            ).append(r.operational_role_id)

    out = []
    for m in memberships:
        user = users_by_id.get(m.user_id)
        role_obj = roles_by_id.get(m.role_id) if m.role_id else None
        role_name = role_obj.name if role_obj else (m.role or "")
        out.append({
            "membership_id": m.id,
            "user_id": m.user_id,
            "email": user.email if user else "",
            "name": user.name if user else "",
            "role": role_name,
            "operational_role_ids": op_role_ids_by_membership.get(m.id, []),
        })
    return {"workspace_id": workspace_id, "members": out}


@router.patch("/{workspace_id}/settings", response_model=WorkspaceResponse, dependencies=[Depends(require_process_ai_access)])
def update_workspace_settings(
    workspace_id: str,
    request: WorkspaceSettingsUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Actualiza preferencias generales del workspace (país, estilo, defaults de documentación).
    Solo owner, creator o superadmin local.
    """
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")

    _require_workspace_settings_access(session, user_id, workspace_id)

    if request.country is not None:
        code = request.country.strip().upper()
        if code and code not in ALLOWED_COUNTRY_CODES:
            raise HTTPException(status_code=400, detail="Código de país no válido")
        workspace.country = code or None

    if request.business_type is not None:
        workspace.business_type = _normalize_optional_str(request.business_type, max_length=50)

    if request.language_style is not None:
        workspace.language_style = _normalize_optional_str(request.language_style, max_length=50)

    if request.default_audience is not None:
        workspace.default_audience = _normalize_optional_str(request.default_audience, max_length=50)

    if request.default_detail_level is not None:
        workspace.default_detail_level = _normalize_optional_str(
            request.default_detail_level, max_length=50
        )

    if request.context_text is not None:
        workspace.context_text = _normalize_optional_str(
            request.context_text, max_length=MAX_CONTEXT_TEXT_LENGTH
        )

    if request.description is not None:
        workspace.description = _normalize_optional_str(
            request.description, max_length=MAX_DESCRIPTION_LENGTH
        )

    session.flush()
    role_name = _get_workspace_role_name(session, user_id, workspace_id)
    return _serialize_workspace(workspace, role=role_name)


@router.get("/{workspace_id}", response_model=WorkspaceResponse, dependencies=[Depends(require_process_ai_access)])
def get_workspace(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Obtiene un workspace por su ID. Solo para miembros (o superadmin).

    404 también para no-miembros: para quien está en otro tenant, este
    workspace no existe (mismo criterio que los documentos).

    Args:
        workspace_id: ID del workspace

    Returns:
        WorkspaceResponse

    Raises:
        404: Si el workspace no existe o el usuario no es miembro
    """
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=404,
            detail=f"Workspace {workspace_id} no encontrado"
        )

    role_name = _get_workspace_role_name(session, user_id, workspace_id)
    if not role_name and not is_superadmin(user_id, session):
        raise HTTPException(
            status_code=404,
            detail=f"Workspace {workspace_id} no encontrado"
        )

    return _serialize_workspace(workspace, role=role_name)


@router.post("/{workspace_id}/branding/icon", dependencies=[Depends(require_process_ai_access)])
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

    # A object storage, no a disco local: el freeze del PDF corre en cualquier
    # instancia de Cloud Run y el filesystem es efímero. Guardarlo local hacía
    # que el PDF oficial se congelara sin logo. Ver api/routes/_branding.py.
    previous_filename = _get_workspace_branding_icon_filename(workspace)
    if previous_filename:
        _delete_branding_icon_blob(workspace_id, previous_filename)

    filename = f"{uuid4().hex}{ext}"
    try:
        get_storage().put(
            workspace_branding_key(workspace_id, filename),
            contents,
            content_type=file.content_type or _branding_icon_media_type(filename),
        )
    except Exception as e:
        logger.exception("No se pudo subir el icono de marca del workspace %s", workspace_id)
        raise HTTPException(status_code=500, detail="No se pudo guardar el icono") from e

    branding = _get_workspace_branding(workspace)
    branding["client_icon_filename"] = filename
    _save_workspace_branding(workspace, branding)
    session.flush()

    return {
        "icon_url": _build_branding_icon_url(workspace_id, filename),
    }


@router.delete("/{workspace_id}/branding/icon", dependencies=[Depends(require_process_ai_access)])
def delete_workspace_branding_icon(
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
        _delete_branding_icon_blob(workspace_id, filename)

    branding = _get_workspace_branding(workspace)
    branding.pop("client_icon_filename", None)
    branding.pop("primary_color", None)
    branding.pop("secondary_color", None)
    _save_workspace_branding(workspace, branding)
    session.flush()

    return {"icon_url": None}


@router.put("/{workspace_id}/branding", dependencies=[Depends(require_process_ai_access)])
def update_workspace_branding(
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
def get_workspace_branding_icon(workspace_id: str, filename: str):
    """
    Sirve el icono personalizado del workspace desde object storage.

    SIN auth a propósito: la UI lo usa como favicon (<link rel="icon">) y en
    <img>, que no pueden mandar el header Authorization. El riesgo es acotado:
    el filename es un uuid4 hex irrecuperable sin conocer la metadata del
    workspace, y el contenido es un logo, no datos.
    """
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")

    key = workspace_branding_key(workspace_id, filename)
    try:
        contents = get_storage().get(key)
    except FileNotFoundError:
        # Compatibilidad: iconos subidos antes de mover el branding a storage.
        legacy = Path(get_settings().output_dir) / "workspace-branding" / workspace_id / filename
        if legacy.exists():
            return FileResponse(path=str(legacy), filename=filename)
        raise HTTPException(status_code=404, detail="Icono no encontrado")

    return Response(
        content=contents,
        media_type=_branding_icon_media_type(filename),
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

