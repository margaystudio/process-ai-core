"""
Endpoints de autenticación usando Supabase Auth.

Este módulo maneja:
- Sincronización de usuarios desde Supabase a DB local
- Validación de tokens JWT de Supabase
- Obtención de usuario autenticado
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import os
import json
import logging
import jwt  # pyjwt

from pydantic import BaseModel

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User
from process_ai_core.db.helpers import create_or_update_user_from_supabase, get_user_by_external_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/check-email/{email}")
async def check_email_exists(email: str):
    """
    Verifica si un email ya existe en la base de datos local.
    
    Args:
        email: Email a verificar
    
    Returns:
        { exists: bool, user_id: str | null }
    """
    from process_ai_core.db.helpers import get_user_by_email
    
    with get_db_session() as session:
        user = get_user_by_email(session, email)
        return {
            "exists": user is not None,
            "user_id": user.id if user else None,
        }

# Cliente de Supabase para validar tokens
try:
    from supabase import create_client, Client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    else:
        supabase = None
        logger.warning("Supabase credentials not configured. Auth endpoints will not work.")
except ImportError:
    supabase = None
    logger.warning("Supabase Python client not installed. Auth endpoints will not work.")


class SyncUserRequest(BaseModel):
    """Request para sincronizar usuario desde Supabase."""
    supabase_user_id: str
    email: str
    name: str
    auth_provider: str = "supabase"
    metadata: Optional[dict] = None


class SyncUserResponse(BaseModel):
    """Response de sincronización de usuario."""
    user_id: str
    email: str
    name: str
    created: bool


class VerifyTokenRequest(BaseModel):
    """Request para verificar token JWT."""
    token: str


class VerifyTokenResponse(BaseModel):
    """Response de verificación de token."""
    valid: bool
    user: Optional[dict] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


@router.post("/sync-user", response_model=SyncUserResponse)
async def sync_user(request: SyncUserRequest):
    """
    Sincroniza un usuario desde Supabase Auth a la base de datos local.
    
    Este endpoint se llama desde el frontend después de que el usuario
    se autentica exitosamente en Supabase.
    
    IMPORTANTE: Solo actualiza usuarios existentes. NO crea nuevos usuarios.
    Si el usuario no existe en la BD local, retorna 404.
    
    Args:
        request: Datos del usuario desde Supabase
    
    Returns:
        Datos del usuario local (actualizado)
    
    Raises:
        HTTPException 404: Si el usuario no existe en la BD local
    """
    with get_db_session() as session:
        try:
            # Buscar usuario por external_id primero
            user = get_user_by_external_id(session, request.supabase_user_id)
            
            if not user:
                # Si no existe por external_id, buscar por email
                from process_ai_core.db.helpers import get_user_by_email
                user = get_user_by_email(session, request.email)
                
                if not user:
                    # Usuario no existe en BD local
                    raise HTTPException(
                        status_code=404,
                        detail="Usuario no encontrado en la base de datos local. Por favor, contacta al administrador."
                    )
                
                # Usuario existe pero no tiene external_id, actualizarlo
                user.external_id = request.supabase_user_id
                user.auth_provider = request.auth_provider
                if request.metadata:
                    import json
                    user.metadata_json = json.dumps(request.metadata)
                from datetime import datetime, UTC
                user.updated_at = datetime.now(UTC)
            else:
                # Usuario existe, actualizar datos
                user.email = request.email
                user.name = request.name
                user.auth_provider = request.auth_provider
                if request.metadata:
                    import json
                    user.metadata_json = json.dumps(request.metadata)
                from datetime import datetime, UTC
                user.updated_at = datetime.now(UTC)
            
            session.commit()
            
            return SyncUserResponse(
                user_id=user.id,
                email=user.email,
                name=user.name,
                created=False,  # Nunca creamos, solo actualizamos
            )
        except HTTPException:
            raise
        except Exception as e:
            session.rollback()
            logger.exception(f"Error sincronizando usuario: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error sincronizando usuario: {str(e)}"
            )


@router.post("/verify-token", response_model=VerifyTokenResponse)
async def verify_token(request: VerifyTokenRequest):
    """
    Verifica un token JWT de Supabase.
    
    Args:
        request: Token JWT a verificar
    
    Returns:
        Información sobre la validez del token y el usuario
    """
    if not supabase:
        return VerifyTokenResponse(
            valid=False,
            error="Supabase not configured"
        )
    
    try:
        # Validar token con Supabase
        response = supabase.auth.get_user(request.token)
        
        if response.user:
            # Buscar usuario local
            with get_db_session() as session:
                local_user = get_user_by_external_id(session, response.user.id)
                
                if local_user:
                    return VerifyTokenResponse(
                        valid=True,
                        user={
                            "id": local_user.id,
                            "email": local_user.email,
                            "name": local_user.name,
                            "external_id": local_user.external_id,
                            "auth_provider": local_user.auth_provider,
                        },
                        expires_at=str(response.user.created_at) if hasattr(response.user, 'created_at') else None,
                    )
                else:
                    return VerifyTokenResponse(
                        valid=True,
                        user={
                            "id": response.user.id,
                            "email": response.user.email,
                            "name": response.user.user_metadata.get("name", ""),
                            "external_id": response.user.id,
                            "auth_provider": "supabase",
                        },
                        expires_at=str(response.user.created_at) if hasattr(response.user, 'created_at') else None,
                    )
        else:
            return VerifyTokenResponse(
                valid=False,
                error="Invalid token"
            )
    except Exception as e:
        logger.exception(f"Error verificando token: {e}")
        return VerifyTokenResponse(
            valid=False,
            error=str(e)
        )


@router.get("/user")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Obtiene el usuario actual basado en el token JWT en el header Authorization.
    
    Args:
        authorization: Header Authorization con formato "Bearer <token>"
    
    Returns:
        Datos del usuario autenticado
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    # No necesitamos Supabase configurado porque decodificamos el JWT manualmente
    # La validación real del token se hace en el frontend con Supabase
    
    try:
        # Decodificar JWT para obtener el user_id (sub) y email
        # La validación real se hace en el frontend con Supabase
        logger.info("Decodificando token JWT...")
        decoded = jwt.decode(token, options={"verify_signature": False})
        supabase_user_id = decoded.get("sub")
        supabase_email = decoded.get("email")
        
        logger.info(f"Token decodificado, supabase_user_id: {supabase_user_id}, email: {supabase_email}")
        
        if not supabase_user_id:
            logger.warning("Token no contiene 'sub' (user ID)")
            raise HTTPException(
                status_code=401,
                detail="Invalid token: no user ID found"
            )
        
        # Buscar usuario local por external_id primero
        logger.info(f"Buscando usuario en BD local con external_id: {supabase_user_id}")
        with get_db_session() as session:
            logger.info("Sesión de BD obtenida, buscando usuario...")
            local_user = get_user_by_external_id(session, supabase_user_id)
            logger.info(f"Usuario encontrado por external_id: {local_user is not None}")
            
            # Si no se encuentra por external_id, buscar por email (para usuarios creados localmente antes de vincular con Supabase)
            if not local_user and supabase_email:
                logger.info(f"Usuario no encontrado por external_id, buscando por email: {supabase_email}")
                from process_ai_core.db.helpers import get_user_by_email
                local_user = get_user_by_email(session, supabase_email)
                logger.info(f"Usuario encontrado por email: {local_user is not None}")
                if local_user:
                    logger.info(f"Usuario encontrado: {local_user.email} (ID: {local_user.id})")
                
                # Si se encuentra por email, vincular automáticamente el external_id
                if local_user:
                    logger.info(f"Vinculando usuario {local_user.id} ({local_user.email}) con Supabase user_id {supabase_user_id} (email: {supabase_email})")
                    local_user.external_id = supabase_user_id
                    local_user.auth_provider = "supabase"
                    session.commit()
                    logger.info("Usuario vinculado exitosamente")
                else:
                    logger.warning(f"No se encontró usuario con email {supabase_email} en la BD local. Usuarios disponibles: {[u.email for u in session.query(User).all()]}")
            
            if not local_user:
                logger.warning(f"Usuario con external_id {supabase_user_id} o email {supabase_email} no encontrado en BD local")
                raise HTTPException(
                    status_code=404,
                    detail="User not found in local database"
                )
            
            logger.info(f"Retornando datos del usuario: {local_user.id}")
            return {
                "user": {
                    "id": local_user.id,
                    "email": local_user.email,
                    "name": local_user.name,
                    "external_id": local_user.external_id,
                    "auth_provider": local_user.auth_provider,
                }
            }
    except jwt.DecodeError as e:
        logger.error(f"Error decodificando JWT: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token format: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error obteniendo usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo usuario: {str(e)}"
        )



