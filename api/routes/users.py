"""
Endpoint para gestionar usuarios.

Este endpoint maneja:
- POST /api/v1/users: Crear un nuevo usuario
- GET /api/v1/users: Listar usuarios
- GET /api/v1/users/{user_id}: Obtener un usuario
- POST /api/v1/users/{user_id}/workspaces/{workspace_id}/membership: Agregar usuario a workspace con rol
"""

import json
import re

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

E164_REGEX = re.compile(r"^\+[1-9]\d{6,14}$")

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User, Workspace, WorkspaceMembership, Role
from process_ai_core.db.permissions import has_permission
from process_ai_core.db.helpers import get_or_create_workspace_for_tenant
from ..dependencies import get_db, get_current_user_id
from ..workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    sync_workspace_access,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _get_workspace_branding_icon_url(workspace: Workspace) -> str | None:
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    branding = metadata.get("branding") or {}
    filename = branding.get("client_icon_filename")
    if not isinstance(filename, str) or not filename.strip():
        return None
    return f"/api/v1/workspaces/{workspace.id}/branding/icon/{filename}"


def _get_workspace_branding_color(workspace: Workspace, key: str) -> str | None:
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    branding = metadata.get("branding") or {}
    color = branding.get(key)
    if not isinstance(color, str):
        return None
    return color


@router.post("")
async def create_user(
    email: str,
    name: str,
):
    """
    Crea un nuevo usuario.
    
    Args:
        email: Email del usuario (único)
        name: Nombre del usuario
    
    Returns:
        Datos del usuario creado
    """
    with get_db_session() as session:
        try:
            # Verificar que el email no exista
            existing = session.query(User).filter_by(email=email).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un usuario con el email '{email}'"
                )
            
            user = User(
                email=email,
                name=name,
            )
            session.add(user)
            session.flush()
            
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
            }
        
        except HTTPException:
            raise
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Error al crear usuario: {str(e)}"
            ) from e
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error interno: {str(e)}"
            ) from e


@router.get("")
async def list_users():
    """
    Lista todos los usuarios.
    
    Returns:
        Lista de usuarios
    """
    with get_db_session() as session:
        users = session.query(User).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]


def _membership_role_name(session: Session, membership: WorkspaceMembership) -> str | None:
    if membership.role_id:
        role_obj = session.query(Role).filter_by(id=membership.role_id).first()
        if role_obj:
            return role_obj.name
    return getattr(membership, "role", None)


def _is_legacy_system_workspace(workspace: Workspace) -> bool:
    return workspace.slug == "sistema" or workspace.workspace_type == "system"


@router.get("/me")
async def get_current_user_me(
    _sync: None = Depends(sync_workspace_access),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
    authenticated_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Perfil + tenants/workspaces sincronizados con margay-workspace.

    La lista de tenants sale de ctx.tenants (control plane), no de memberships
    locales acumuladas. El tenant activo es ctx.tenant (header X-Active-Tenant-Id
    o el primero del usuario en workspace).
    """
    user = session.query(User).filter_by(id=authenticated_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    from api.request_cache import get_cached_workspace_id, remember_workspace_id

    active_workspace_id = get_cached_workspace_id(ctx.tenant.id)
    if not active_workspace_id:
        active_workspace_id = get_or_create_workspace_for_tenant(
            session,
            tenant_id=ctx.tenant.id,
            tenant_name=ctx.tenant.name,
            tenant_slug=ctx.tenant.slug,
        )
        remember_workspace_id(ctx.tenant.id, active_workspace_id)
    active_membership = (
        session.query(WorkspaceMembership)
        .filter_by(user_id=authenticated_user_id, workspace_id=active_workspace_id)
        .first()
    )
    active_role = _membership_role_name(session, active_membership) if active_membership else None

    workspaces = []
    for tenant in ctx.tenants:
        workspace_id = get_cached_workspace_id(tenant.id)
        if not workspace_id:
            workspace_id = get_or_create_workspace_for_tenant(
                session,
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                tenant_slug=tenant.slug,
            )
            remember_workspace_id(tenant.id, workspace_id)
        workspace = session.query(Workspace).filter_by(id=workspace_id).first()
        if not workspace or _is_legacy_system_workspace(workspace):
            continue

        is_active = tenant.id == ctx.tenant.id
        role_name = active_role if is_active else None

        workspaces.append({
            "id": workspace.id,
            "tenant_id": tenant.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "workspace_type": workspace.workspace_type,
            "role": role_name,
            "is_active": is_active,
            "country": workspace.country,
            "language_style": workspace.language_style,
            "branding_icon_url": _get_workspace_branding_icon_url(workspace),
            "branding_primary_color": _get_workspace_branding_color(workspace, "primary_color"),
            "branding_secondary_color": _get_workspace_branding_color(workspace, "secondary_color"),
            "created_at": workspace.created_at.isoformat(),
        })

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        },
        "active_tenant": {
            "id": ctx.tenant.id,
            "name": ctx.tenant.name,
            "slug": ctx.tenant.slug,
        },
        "platform_roles": ctx.platform_roles,
        "tenant_roles": ctx.tenant_roles,
        "workspaces": workspaces,
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    authenticated_user_id: str = Depends(get_current_user_id),
):
    """
    Obtiene un usuario por su ID.
    
    Args:
        user_id: ID del usuario
        authenticated_user_id: ID del usuario autenticado (del token JWT)
    
    Returns:
        Datos del usuario
    
    Raises:
        403: Si el user_id no coincide con el usuario autenticado
        404: Si el usuario no existe
    """
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own profile"
        )

    with get_db_session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no encontrado"
            )
        
        # Obtener memberships con roles
        memberships = session.query(WorkspaceMembership).filter_by(user_id=user_id).all()
        
        _phone_verified_at = getattr(user, "phone_verified_at", None)
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at.isoformat(),
            "phone_e164": getattr(user, "phone_e164", None),
            "phone_verified": getattr(user, "phone_verified", False),
            "phone_verified_at": _phone_verified_at.isoformat() if _phone_verified_at else None,
            "workspaces": [
                {
                    "workspace_id": m.workspace_id,
                    "role": m.role,
                    "created_at": m.created_at.isoformat(),
                }
                for m in memberships
            ],
        }


@router.post("/{user_id}/workspaces/{workspace_id}/membership")
async def add_user_to_workspace(
    user_id: str,
    workspace_id: str,
    role_name: str = Query(default="owner", description="Rol del usuario en el workspace"),  # "owner" | "admin" | "creator" | "viewer" | "approver"
):
    """
    Agrega un usuario a un workspace con un rol específico.
    
    Ahora usa role_id (FK a Role) en lugar de role (string).
    
    Args:
        user_id: ID del usuario
        workspace_id: ID del workspace
        role_name: Nombre del rol del usuario en el workspace
    
    Returns:
        Datos del membership creado
    """
    with get_db_session() as session:
        from process_ai_core.db.models import Role
        
        # Verificar que el usuario existe
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no encontrado"
            )
        
        # Verificar que el workspace existe
        workspace = session.query(Workspace).filter_by(id=workspace_id).first()
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace {workspace_id} no encontrado"
            )
        
        # Buscar el rol por nombre
        role = session.query(Role).filter_by(name=role_name).first()
        if not role:
            raise HTTPException(
                status_code=400,
                detail=f"Rol '{role_name}' no encontrado. Roles disponibles: owner, admin, approver, creator, viewer"
            )
        
        # Verificar que no exista ya el membership
        existing = session.query(WorkspaceMembership).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
        ).first()
        
        if existing:
            # Actualizar el role_id si ya existe
            existing.role_id = role.id
            # Mantener role como string para compatibilidad (deprecated)
            existing.role = role_name
        else:
            # Crear nuevo membership
            membership = WorkspaceMembership(
                user_id=user_id,
                workspace_id=workspace_id,
                role_id=role.id,
                role=role_name,  # Deprecated, mantener para compatibilidad
            )
            session.add(membership)
            session.flush()
            existing = membership
        
        session.commit()
        
        return {
            "id": existing.id,
            "user_id": existing.user_id,
            "workspace_id": existing.workspace_id,
            "role_id": existing.role_id,
            "role": role_name,  # Retornar nombre del rol para compatibilidad
            "created_at": existing.created_at.isoformat(),
        }


@router.get("/{user_id}/workspaces")
async def get_user_workspaces(user_id: str, session: Session = Depends(get_db)):
    """
    Obtiene todos los workspaces a los que pertenece un usuario.
    
    Args:
        user_id: ID del usuario
    
    Returns:
        Lista de workspaces con información de membresía
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Obteniendo workspaces para usuario: {user_id}")
    
    # Usar la sesión proporcionada por la dependencia en lugar de crear una nueva
    # Esto asegura que veamos los cambios recientes
    from process_ai_core.db.models import Workspace, Role, User
    
    # Verificar que el usuario existe
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        logger.warning(f"Usuario {user_id} no encontrado")
        return []
    
    logger.info(f"Usuario encontrado: {user.email}")
    
    # Obtener todas las membresías del usuario
    memberships = session.query(WorkspaceMembership).filter_by(user_id=user_id).all()
    logger.info(f"Membresías encontradas: {len(memberships)}")

    if not memberships:
        logger.warning(f"Usuario {user_id} no tiene membresías")
        return []

    # Batch-load de workspaces y roles para evitar N+1 (antes: 2 queries por
    # membresía contra el Postgres remoto). Ahora 3 queries fijas.
    workspace_ids = {m.workspace_id for m in memberships if m.workspace_id}
    role_ids = {m.role_id for m in memberships if m.role_id}
    workspaces_by_id = (
        {w.id: w for w in session.query(Workspace).filter(Workspace.id.in_(workspace_ids)).all()}
        if workspace_ids
        else {}
    )
    role_name_by_id = (
        {r.id: r.name for r in session.query(Role).filter(Role.id.in_(role_ids)).all()}
        if role_ids
        else {}
    )

    workspaces = []
    for membership in memberships:
        workspace = workspaces_by_id.get(membership.workspace_id)
        if not workspace:
            logger.warning(f"Workspace {membership.workspace_id} no encontrado para membresía {membership.id}")
            continue

        # Rol: por role_id, con fallback al string legacy `role`.
        role_name = (
            role_name_by_id.get(membership.role_id)
            if membership.role_id
            else membership.role
        )

        workspaces.append({
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "workspace_type": workspace.workspace_type,
            "role": role_name,
            "branding_icon_url": _get_workspace_branding_icon_url(workspace),
            "branding_primary_color": _get_workspace_branding_color(workspace, "primary_color"),
            "branding_secondary_color": _get_workspace_branding_color(workspace, "secondary_color"),
            "created_at": workspace.created_at.isoformat(),
        })

    logger.info(f"Total workspaces devueltos: {len(workspaces)}")
    return workspaces


@router.get("/{user_id}/role/{workspace_id}")
async def get_user_role_in_workspace(
    user_id: str,
    workspace_id: str,
):
    """
    Obtiene el rol de un usuario en un workspace específico.
    
    Args:
        user_id: ID del usuario
        workspace_id: ID del workspace
    
    Returns:
        Rol del usuario o None si no pertenece al workspace
    """
    with get_db_session() as session:
        membership = session.query(WorkspaceMembership).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
        ).first()
        
        if not membership:
            return {"role": None}
        
        # Obtener el nombre del rol desde role_id si existe
        role_name = None
        if membership.role_id:
            from process_ai_core.db.models import Role
            role = session.query(Role).filter_by(id=membership.role_id).first()
            if role:
                role_name = role.name
        else:
            # Compatibilidad: usar role string si role_id no existe
            role_name = membership.role
        
        return {"role": role_name}


@router.get("/{user_id}/permission/{workspace_id}/{permission_name}")
async def check_user_permission(
    user_id: str,
    workspace_id: str,
    permission_name: str,
    authenticated_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Verifica si un usuario tiene un permiso específico en un workspace.
    
    Args:
        user_id: ID del usuario (debe coincidir con el usuario autenticado)
        workspace_id: ID del workspace
        permission_name: Nombre del permiso (ej: "workspaces.edit", "documents.approve")
        authenticated_user_id: ID del usuario autenticado (del token JWT)
    
    Returns:
        { has_permission: bool }
    
    Raises:
        403: Si el user_id de la URL no coincide con el usuario autenticado
    """
    # Verificar que el usuario autenticado coincida con el user_id de la URL
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only check your own permissions"
        )
    
    has_perm = has_permission(session, user_id, workspace_id, permission_name)
    return {"has_permission": has_perm}


class UpdateUserProfileRequest(BaseModel):
    """Request para actualizar perfil de usuario."""
    name: str | None = None
    phone_e164: str | None = None


@router.put("/{user_id}")
async def update_user_profile(
    user_id: str,
    request: UpdateUserProfileRequest,
    authenticated_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Actualiza el perfil de un usuario (nombre, teléfono).
    
    Args:
        user_id: ID del usuario (debe coincidir con el usuario autenticado)
        request: Datos a actualizar (name, phone_e164 opcionales)
        authenticated_user_id: ID del usuario autenticado (del token JWT)
    
    Returns:
        Datos del usuario actualizado
    
    Raises:
        403: Si el user_id de la URL no coincide con el usuario autenticado
        404: Si el usuario no existe
    """
    if user_id != authenticated_user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only update your own profile"
        )
    
    if request.name is None and request.phone_e164 is None:
        raise HTTPException(
            status_code=400,
            detail="Debe enviar al menos un campo a actualizar (name o phone_e164)"
        )

    if request.phone_e164 is not None:
        cleaned = request.phone_e164.strip()
        if cleaned and not E164_REGEX.match(cleaned):
            raise HTTPException(
                status_code=400,
                detail="El número de teléfono no es válido. Verificá el código de país y que tenga entre 7 y 15 dígitos."
            )

    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"Usuario {user_id} no encontrado"
        )
    
    from datetime import datetime, UTC
    if request.name is not None:
        user.name = request.name
    if request.phone_e164 is not None:
        user.phone_e164 = request.phone_e164.strip() or None
    user.updated_at = datetime.now(UTC)
    
    session.commit()
    
    _pv_at = getattr(user, "phone_verified_at", None)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "updated_at": user.updated_at.isoformat(),
        "phone_e164": getattr(user, "phone_e164", None),
        "phone_verified": getattr(user, "phone_verified", False),
        "phone_verified_at": _pv_at.isoformat() if _pv_at else None,
    }

