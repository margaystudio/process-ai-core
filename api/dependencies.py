"""
Dependencias de FastAPI para autenticación y autorización.

Este módulo proporciona dependencias reutilizables para:
- Obtener el usuario actual desde el token JWT
- Verificar permisos de usuarios
- Verificar roles específicos (superadmin, owner, etc.)
"""

from typing import Optional
from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User, Role, WorkspaceMembership
from process_ai_core.db.helpers import get_user_by_external_id
from process_ai_core.db.permissions import has_permission

import os
import logging

logger = logging.getLogger(__name__)

# Cliente de Supabase para validar tokens
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    else:
        supabase = None
        logger.warning("Supabase credentials not configured. Auth dependencies will not work.")
except ImportError:
    supabase = None
    logger.warning("Supabase Python client not installed. Auth dependencies will not work.")


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_db_session),
) -> str:
    """
    Obtiene el ID del usuario actual desde el token JWT.
    
    Args:
        authorization: Header Authorization con formato "Bearer <token>"
        session: Sesión de base de datos
    
    Returns:
        ID del usuario local
    
    Raises:
        HTTPException: Si el token es inválido o el usuario no existe
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    if not supabase:
        # En desarrollo sin Supabase, usar el token como user_id directamente
        # El token puede ser un UUID o un user_id
        if token and len(token) == 36:  # UUID format
            user = session.query(User).filter_by(id=token).first()
            if user:
                return user.id
            # Si no existe el usuario, crear uno temporal para desarrollo
            logger.warning(f"User {token} not found in database, creating temporary user for development")
            import uuid
            new_user = User(
                id=token,
                email=f"dev-{token[:8]}@localhost",
                name="Development User",
                external_id=token,  # Usar el mismo ID como external_id
            )
            session.add(new_user)
            session.commit()
            return new_user.id
        raise HTTPException(
            status_code=401,
            detail="Supabase not configured. Please provide a valid user ID (UUID) in Authorization header"
        )
    
    try:
        # Validar token con Supabase
        response = supabase.auth.get_user(token)
        
        if not response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        
        # Buscar usuario local
        local_user = get_user_by_external_id(session, response.user.id, "supabase")
        
        if not local_user:
            raise HTTPException(
                status_code=404,
                detail="User not found in local database"
            )
        
        return local_user.id
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error obteniendo usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo usuario: {str(e)}"
        )


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> User:
    """
    Obtiene el objeto User completo del usuario actual.
    
    Args:
        user_id: ID del usuario (de get_current_user_id)
        session: Sesión de base de datos
    
    Returns:
        Objeto User
    """
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def is_superadmin(
    user_id: str,
    session: Session,
) -> bool:
    """
    Verifica si un usuario es superadmin.
    
    Un superadmin es un usuario que tiene el rol "superadmin" en algún workspace
    o que tiene un permiso especial del sistema.
    """
    # Buscar rol superadmin
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        return False
    
    # Verificar si el usuario tiene este rol en algún workspace
    # Para superadmin, podríamos usar un workspace especial o verificar directamente
    # Por ahora, verificamos si tiene el rol en cualquier workspace
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        role_id=superadmin_role.id,
    ).first()
    
    return membership is not None


async def require_superadmin(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> str:
    """
    Dependencia que requiere que el usuario sea superadmin.
    
    Raises:
        HTTPException: Si el usuario no es superadmin
    """
    if not is_superadmin(user_id, session):
        raise HTTPException(
            status_code=403,
            detail="Superadmin access required"
        )
    return user_id


async def require_permission(
    permission_name: str,
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> str:
    """
    Dependencia que requiere que el usuario tenga un permiso específico en un workspace.
    
    Args:
        permission_name: Nombre del permiso (ej: "workspaces.create")
        workspace_id: ID del workspace
        user_id: ID del usuario (de get_current_user_id)
        session: Sesión de base de datos
    
    Returns:
        ID del usuario si tiene el permiso
    
    Raises:
        HTTPException: Si el usuario no tiene el permiso
    """
    if not has_permission(session, user_id, workspace_id, permission_name):
        raise HTTPException(
            status_code=403,
            detail=f"Permission '{permission_name}' required"
        )
    return user_id


async def require_role(
    role_name: str,
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
) -> str:
    """
    Dependencia que requiere que el usuario tenga un rol específico en un workspace.
    
    Args:
        role_name: Nombre del rol (ej: "owner", "admin")
        workspace_id: ID del workspace
        user_id: ID del usuario (de get_current_user_id)
        session: Sesión de base de datos
    
    Returns:
        ID del usuario si tiene el rol
    
    Raises:
        HTTPException: Si el usuario no tiene el rol
    """
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=403,
            detail="User is not a member of this workspace"
        )
    
    role = session.query(Role).filter_by(id=membership.role_id).first() if membership.role_id else None
    if not role or role.name != role_name:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role_name}' required"
        )
    
    return user_id


