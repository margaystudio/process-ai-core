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
from jwt import PyJWKClient, PyJWKClientError

logger = logging.getLogger(__name__)

DEFAULT_SUPABASE_JWKS_URL = (
    "https://zgujorkqulkdsnmjdxtj.supabase.co/auth/v1/.well-known/jwks.json"
)

_jwks_client: PyJWKClient | None = None


def _get_supabase_jwks_url() -> str:
    explicit = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if explicit:
        return explicit
    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}/auth/v1/.well-known/jwks.json"
    return DEFAULT_SUPABASE_JWKS_URL


def _get_jwks_client() -> PyJWKClient:
    """Lazy singleton — no network call until first JWT validation."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            _get_supabase_jwks_url(),
            cache_keys=True,
        )
    return _jwks_client


def _decode_and_verify_supabase_jwt(token: str) -> dict:
    """
    Valida firma del JWT contra JWKS de Supabase (ES256/RS256) y devuelve el payload.
    Si el proyecto usa firma simétrica (HS256), intenta como fallback con SUPABASE_JWT_SECRET.
    """
    # ── Intento 1: JWKS asimétrico (ES256 / RS256) ───────────────────────────
    jwks_error: Exception | None = None
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except PyJWKClientError as exc:
        # No se encontró la clave en JWKS — puede ser token HS256 (firma simétrica)
        logger.debug("JWKS key not found (%s), trying HS256 fallback", type(exc).__name__)
        jwks_error = exc
    except jwt.InvalidAudienceError as exc:
        logger.warning("JWT audience inválido: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT inválido (%s)", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error inesperado al validar JWT: %s", type(exc).__name__)
        raise HTTPException(status_code=401, detail="Invalid token")

    # ── Intento 2: HS256 con SUPABASE_JWT_SECRET (proyectos con firma simétrica) ─
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if jwt_secret:
        try:
            return jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWT expired (HS256)")
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT inválido en fallback HS256 (%s)", type(exc).__name__)
            raise HTTPException(status_code=401, detail="Invalid token")

    # ── Intento 3: Supabase SDK — verifica server-side (requiere SUPABASE_SERVICE_ROLE_KEY) ─
    # Útil cuando el proyecto usa HS256 pero no tenemos el JWT secret local.
    if supabase is not None:
        try:
            response = supabase.auth.get_user(token)
            if response and response.user:
                u = response.user
                payload: dict = {
                    "sub": u.id,
                    "email": getattr(u, "email", None),
                    "aud": "authenticated",
                }
                return payload
        except Exception as exc:
            logger.warning("Supabase SDK token validation failed: %s", type(exc).__name__)
            raise HTTPException(status_code=401, detail="Invalid token")

    logger.warning("Invalid JWT: JWKS key not found, SUPABASE_JWT_SECRET no configurado y Supabase SDK no disponible")
    raise HTTPException(status_code=401, detail="Invalid token")


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
    session: Session = Depends(get_db),
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
    logger.debug("get_current_user_id: authorization header present=%s", authorization is not None)

    if not authorization:
        logger.warning("Authorization header missing")
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        logger.warning("Authorization header is not Bearer format")
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization.replace("Bearer ", "").strip()
    logger.debug("Bearer token present=%s", bool(token))

    try:
        decoded = _decode_and_verify_supabase_jwt(token)
        logger.debug("JWT signature verified")

        supabase_user_id = decoded.get("sub")

        if not supabase_user_id:
            logger.warning("JWT missing subject claim")
            raise HTTPException(
                status_code=401,
                detail="Invalid token: no user ID found",
            )

        from api.request_cache import get_cached_user_id, remember_user_id

        cached_user_id = get_cached_user_id(supabase_user_id)
        if cached_user_id:
            logger.debug("Authenticated local user id=%s (cache)", cached_user_id)
            return cached_user_id

        local_user = get_user_by_external_id(session, supabase_user_id)

        if not local_user:
            supabase_email = decoded.get("email")
            if supabase_email:
                logger.debug("Local user lookup by external_id failed; trying email match")
                from process_ai_core.db.helpers import get_user_by_email

                local_user = get_user_by_email(session, supabase_email)
                if local_user:
                    local_user.external_id = supabase_user_id
                    local_user.auth_provider = "supabase"
                    session.commit()
                    logger.debug("Linked local user id=%s to auth provider", local_user.id)

        if local_user:
            logger.debug("Authenticated local user id=%s", local_user.id)
            remember_user_id(supabase_user_id, local_user.id)
            return local_user.id

            logger.warning("Authenticated subject not found in local database")
            raise HTTPException(
                status_code=404,
                detail=f"User not found in local database. Supabase ID: {supabase_user_id}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error obteniendo usuario: %s", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo usuario: {str(e)}",
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


