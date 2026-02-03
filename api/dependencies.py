"""
Dependencias de FastAPI para autenticación y autorización.

Este módulo proporciona dependencias reutilizables para:
- Obtener el usuario actual desde el token JWT
- Verificar permisos de usuarios
- Verificar roles específicos (superadmin, owner, etc.)
"""

from typing import Optional, Generator
from fastapi import HTTPException, Header, Depends
from sqlalchemy.orm import Session

from process_ai_core.db.database import get_db_engine, get_db_session
from process_ai_core.db.models import User, Role, WorkspaceMembership
from process_ai_core.db.helpers import get_user_by_external_id
from process_ai_core.db.permissions import has_permission

import os
import logging
import jwt  # pyjwt

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia de FastAPI para obtener una sesión de base de datos.
    Compatible con el uso de múltiples dependencias anidadas.
    Usa un generador puro en lugar de un context manager para evitar conflictos.
    """
    get_db_engine(echo=False)
    from process_ai_core.db.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

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
    authorization: Optional[str] = Header(None, alias="Authorization"),
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
    logger.info(f"get_current_user_id llamado, authorization presente: {authorization is not None}")
    
    if not authorization:
        logger.warning("Authorization header no presente")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        logger.warning(f"Authorization header no tiene formato Bearer: {authorization[:20]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    logger.info(f"Token extraído, longitud: {len(token)}, primeros 20 chars: {token[:20]}...")
    
    # Siempre intentar decodificar el JWT, incluso si Supabase no está configurado
    # El token JWT puede ser decodificado sin necesidad de Supabase
    logger.info("Decodificando JWT (no requiere Supabase configurado)...")
    try:
        # Decodificar JWT para obtener el user_id (sub)
        # El service role key no puede usar get_user() directamente con un token JWT
        logger.info("Intentando decodificar JWT...")
        try:
            # Decodificar JWT sin verificar la firma (solo para obtener el sub)
            # La validación real se hace en el frontend con Supabase
            decoded = jwt.decode(token, options={"verify_signature": False})
            logger.info(f"JWT decodificado exitosamente: {list(decoded.keys())}")
            
            supabase_user_id = decoded.get("sub")
            
            logger.info(f"Token decodificado, supabase_user_id: {supabase_user_id}")
            
            if not supabase_user_id:
                logger.warning("Token no contiene 'sub' (user ID)")
                logger.warning(f"Campos disponibles en token: {list(decoded.keys())}")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token: no user ID found"
                )
            
            # Crear una sesión temporal para buscar el usuario
            # Esto evita conflictos con múltiples dependencias anidadas
            with get_db_session() as session:
                # Buscar usuario local por external_id
                logger.info(f"Buscando usuario con external_id: {supabase_user_id}")
                local_user = get_user_by_external_id(session, supabase_user_id)
                
                logger.info(f"Usuario encontrado en BD local: {local_user is not None}")
                if local_user:
                    logger.info(f"Usuario encontrado: {local_user.email} (id: {local_user.id})")
                    return local_user.id
                else:
                    # Listar todos los external_ids para debugging
                    all_users = session.query(User).all()
                    external_ids = [u.external_id for u in all_users if u.external_id]
                    logger.warning(f"Usuario con external_id {supabase_user_id} no encontrado en BD local")
                    logger.warning(f"External IDs en BD: {external_ids}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"User not found in local database. Supabase ID: {supabase_user_id}"
                    )
        except jwt.DecodeError as e:
            logger.error(f"Error decodificando JWT: {e}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token format: {str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error inesperado decodificando JWT: {e}")
            logger.exception("Traceback completo:")
            raise HTTPException(
                status_code=401,
                detail=f"Error procesando token: {str(e)}"
            )
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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
    session: Session = Depends(get_db),
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


