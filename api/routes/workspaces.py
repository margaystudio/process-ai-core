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
from process_ai_core.config import get_settings
from process_ai_core.db.models import Workspace, WorkspaceMembership, User
from process_ai_core.db.models import UserOperationalRole
from ..dependencies import get_current_user_id
from process_ai_core.db.permissions import (
    get_membership_base_access,
    is_workspace_admin,
    resolve_folder_permissions_source,
)
from ..models.requests import (
    WorkspaceResponse,
    WorkspaceBrandingUpdateRequest,
    WorkspaceSettingsUpdateRequest,
)
from ..request_identity import capture_request_identity
from ..workspace_client import (
    get_workspace_context,
    require_process_ai_access,
    sync_workspace_access,
)

# require_process_ai_access va por endpoint y no a nivel de router: la ruta del
# icono de branding se carga desde un <link>/<img> del navegador, que no puede
# mandar headers de auth, así que tiene que quedar fuera del gate.
router = APIRouter(
    prefix="/api/v1/workspaces",
    tags=["workspaces"],
    dependencies=[Depends(sync_workspace_access), Depends(capture_request_identity)],
)

logger = logging.getLogger(__name__)

# Sin `.svg` a propósito. Un SVG es un documento XML que puede traer <script>
# adentro, y este icono se sirve SIN autenticación (es el favicon) desde el
# origen de la API: alcanzaba con subir un logo y abrir su URL para ejecutar JS
# en ese origen. Además el mismo archivo se embebe en el PDF, donde un SVG con
# referencias externas reabre el problema del fetcher. Los formatos ráster no
# tienen esa capacidad.
ALLOWED_BRANDING_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_BRANDING_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


#: Cabeceras del icono público. `nosniff` evita que el navegador reinterprete
#: como HTML un archivo servido como imagen, y la CSP lo deja inerte aunque
#: alguien logre servir markup por acá (cubre los SVG subidos antes de que se
#: sacara `.svg` de la allow-list).
_CABECERAS_ICONO = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
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


def _require_workspace_settings_access(session: Session, user_id: str, workspace_id: str) -> None:
    """Configuración y branding del workspace: solo el admin del módulo.

    Antes había dos listas distintas de roles de sistema (settings:
    owner/creator/admin; branding: owner/creator). Con los roles de sistema
    eliminados, toda la gestión del workspace es del admin (tenant_admin o
    superadmin de plataforma).
    """
    if not is_workspace_admin(session, user_id, workspace_id):
        raise HTTPException(
            status_code=403,
            detail="Solo un administrador del workspace puede editar su configuración",
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
    from process_ai_core.db.permissions import _is_superadmin

    query = session.query(Workspace).filter_by(workspace_type="organization")
    if not _is_superadmin(session, user_id):
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
    if not get_membership_base_access(session, user_id, workspace_id) and not is_workspace_admin(
        session, user_id, workspace_id
    ):
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
    membership_ids = [m.id for m in memberships]

    users_by_id = (
        {u.id: u for u in session.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
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
        out.append({
            "membership_id": m.id,
            "user_id": m.user_id,
            "email": user.email if user else "",
            "name": user.name if user else "",
            # Acceso base derivado del rol macro del tenant ('admin'|'member'|'external').
            # La clave sigue siendo "role" para no romper el contrato con la UI.
            "role": m.base_access,
            "operational_role_ids": op_role_ids_by_membership.get(m.id, []),
        })
    return {"workspace_id": workspace_id, "members": out}


@router.get(
    "/{workspace_id}/members/{membership_id}/effective-access",
    dependencies=[Depends(require_process_ai_access)],
)
def get_member_effective_access(
    workspace_id: str,
    membership_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx=Depends(get_workspace_context),
):
    """
    Acceso EFECTIVO de un miembro, para el admin del workspace: qué puede
    hacer en cada carpeta y POR QUÉ (qué rol operativo se lo da, o de qué
    ancestro hereda la restricción).

    Es la herramienta de soporte del modelo de permisos: convierte "¿por qué
    Juan no puede aprobar acá?" en una consulta, en vez de un ticket. Solo
    admin/superadmin: expone la configuración de acceso de otra persona.
    """
    from process_ai_core.db.models import Folder, OperationalRole, UserOperationalRole
    from process_ai_core.db.permissions import build_permission_context

    platform_is_superadmin = "superadmin" in (ctx.platform_roles or [])
    if not is_workspace_admin(session, user_id, workspace_id, platform_is_superadmin):
        raise HTTPException(
            status_code=403,
            detail="Solo un administrador puede ver el acceso efectivo de otros usuarios",
        )

    membership = session.query(WorkspaceMembership).filter_by(
        id=membership_id, workspace_id=workspace_id
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membresía no encontrada")

    target = session.query(User).filter_by(id=membership.user_id).first()

    # Nota: el claim de plataforma del USUARIO OBJETIVO no se conoce acá (viaja
    # en SU sesión); si el objetivo fuera superadmin, esto muestra su acceso
    # como miembro común. Aceptable: los superadmin no se administran acá.
    perm_ctx = build_permission_context(session, membership.user_id, workspace_id)

    roles = (
        session.query(OperationalRole)
        .join(
            UserOperationalRole,
            UserOperationalRole.operational_role_id == OperationalRole.id,
        )
        .filter(UserOperationalRole.workspace_membership_id == membership.id)
        .order_by(OperationalRole.name)
        .all()
    )

    folders = (
        session.query(Folder)
        .filter_by(workspace_id=workspace_id)
        .order_by(Folder.path)
        .all()
    )
    folder_name_by_id = {f.id: f.name for f in folders}

    folder_rows = []
    for f in folders:
        allowed = perm_ctx.allowed_operational_role_ids(f.id)
        restricted = bool(allowed)
        source_id = None
        if restricted:
            # De qué carpeta sale la lista efectiva (la propia o un ancestro).
            _, source = resolve_folder_permissions_source(session, f)
            source_id = source.id if source else None
        folder_rows.append({
            "id": f.id,
            "name": f.name,
            "path": f.path,
            "parent_id": f.parent_id,
            "view": perm_ctx.can_view_folder(f.id),
            "create": perm_ctx.can_create_in_folder(f.id),
            "approve": perm_ctx.can_approve_in_folder(f.id),
            "restricted": restricted,
            "source_folder_id": source_id,
            "source_folder_name": folder_name_by_id.get(source_id),
            # Los roles del usuario que abren ESTA carpeta (vacío si entra por
            # el nivel base o si no entra).
            "granted_by_role_ids": sorted(
                perm_ctx.operational_role_ids & allowed
            ) if restricted else [],
        })

    return {
        "membership_id": membership.id,
        "user_id": membership.user_id,
        "email": target.email if target else "",
        "name": target.name if target else "",
        "base_access": perm_ctx.base_access,
        "is_admin": perm_ctx.base_access == "admin",
        "permissions": sorted(perm_ctx.permission_names),
        "operational_roles": [
            {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "access_level": r.access_level,
                "is_active": r.is_active,
            }
            for r in roles
        ],
        "folders": folder_rows,
    }


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
    return _serialize_workspace(
        workspace, role=get_membership_base_access(session, user_id, workspace_id)
    )


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

    from process_ai_core.db.permissions import _is_superadmin

    base_access = get_membership_base_access(session, user_id, workspace_id)
    if not base_access and not _is_superadmin(session, user_id):
        raise HTTPException(
            status_code=404,
            detail=f"Workspace {workspace_id} no encontrado"
        )

    return _serialize_workspace(workspace, role=base_access)


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

    _require_workspace_settings_access(session, user_id, workspace_id)

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

    _require_workspace_settings_access(session, user_id, workspace_id)

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

    _require_workspace_settings_access(session, user_id, workspace_id)

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
            return FileResponse(
                path=str(legacy), filename=filename, headers=_CABECERAS_ICONO
            )
        raise HTTPException(status_code=404, detail="Icono no encontrado")

    return Response(
        content=contents,
        media_type=_branding_icon_media_type(filename),
        headers=_CABECERAS_ICONO | {"Content-Disposition": f'inline; filename="{filename}"'},
    )

