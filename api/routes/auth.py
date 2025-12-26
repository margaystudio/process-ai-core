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

from pydantic import BaseModel

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User
from process_ai_core.db.helpers import create_or_update_user_from_supabase, get_user_by_external_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

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
    
    Args:
        request: Datos del usuario desde Supabase
    
    Returns:
        Datos del usuario local (creado o actualizado)
    """
    with get_db_session() as session:
        try:
            user, created = create_or_update_user_from_supabase(
                session=session,
                supabase_user_id=request.supabase_user_id,
                email=request.email,
                name=request.name,
                auth_provider=request.auth_provider,
                metadata=request.metadata,
            )
            session.commit()
            
            return SyncUserResponse(
                user_id=user.id,
                email=user.email,
                name=user.name,
                created=created,
            )
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
    
    token = authorization.replace("Bearer ", "")
    
    if not supabase:
        raise HTTPException(
            status_code=500,
            detail="Supabase not configured"
        )
    
    try:
        # Validar token
        response = supabase.auth.get_user(token)
        
        if not response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        
        # Buscar usuario local
        with get_db_session() as session:
            local_user = get_user_by_external_id(session, response.user.id)
            
            if not local_user:
                raise HTTPException(
                    status_code=404,
                    detail="User not found in local database"
                )
            
            return {
                "user": {
                    "id": local_user.id,
                    "email": local_user.email,
                    "name": local_user.name,
                    "external_id": local_user.external_id,
                    "auth_provider": local_user.auth_provider,
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error obteniendo usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo usuario: {str(e)}"
        )


