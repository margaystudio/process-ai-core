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
from process_ai_core.db.helpers import get_user_by_external_id

import os
import logging
import jwt  # pyjwt
from jwt import PyJWKClient, PyJWKClientError

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def _get_supabase_jwks_url() -> str:
    """URL del JWKS contra el que se validan los JWT. Sin default: falla.

    Antes había un default hardcodeado al proyecto `zgujorkqulkdsnmjdxtj`, que es
    **Margay Platform Test**. Si faltaba la config en un entorno productivo, el
    módulo no fallaba: validaba tokens contra el proyecto equivocado y seguía
    andando. Una config faltante tiene que romper fuerte y temprano, no elegir
    silenciosamente el emisor de otro entorno.
    """
    explicit = os.getenv("SUPABASE_JWKS_URL", "").strip()
    if explicit:
        return explicit
    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}/auth/v1/.well-known/jwks.json"
    raise RuntimeError(
        "Falta configurar SUPABASE_JWKS_URL o SUPABASE_URL: sin eso no se puede "
        "validar la firma de los JWT. No hay default a propósito — un default "
        "apuntaría al proyecto de otro entorno."
    )


def _expected_issuer() -> str | None:
    """Emisor esperado: el Auth de ESTE proyecto Supabase.

    None si no hay `SUPABASE_URL` (entornos donde el JWKS se configura a mano).
    No se inventa un default — apuntar al emisor de otro entorno es justo lo que
    `_get_supabase_jwks_url` evita.
    """
    base = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    return f"{base}/auth/v1" if base else None


def _assert_issuer_valido(payload: dict) -> None:
    """Rechaza un token cuyo `iss` no sea el de este proyecto.

    Se valida SI VIENE, y no se exige. Es defensa en profundidad: la firma ya
    ata el token al proyecto (JWKS distinto ⇒ no valida), así que el aporte real
    es cerrar el caso de una clave compartida entre proyectos. Volverlo
    obligatorio sería otra cosa: cualquier token legítimo sin ese claim dejaría
    de autenticar, y eso es apagar el login por un endurecimiento menor.
    """
    esperado = _expected_issuer()
    emisor = payload.get("iss")
    if esperado and emisor and emisor.rstrip("/") != esperado:
        logger.warning("JWT con emisor inesperado: %s", emisor)
        raise HTTPException(status_code=401, detail="Invalid token")


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
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
        _assert_issuer_valido(payload)
        return payload
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
    #
    # Solo fuera de producción. Ese secreto simétrico es una llave maestra: con
    # él se firma un JWT con cualquier `sub` y se suplanta a cualquiera. Prod
    # usa firma asimétrica (JWKS) y no lo configura, así que este camino ya era
    # inerte ahí; el guard hace que no se pueda "activar" por una env var
    # puesta de más.
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if jwt_secret and os.getenv("ENVIRONMENT", "local").lower() in ("prod", "production"):
        logger.error(
            "SUPABASE_JWT_SECRET está configurado en producción y se IGNORA: "
            "prod valida por JWKS. Sacalo de la config."
        )
        jwt_secret = ""
    if jwt_secret:
        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["sub", "exp"]},
            )
            _assert_issuer_valido(payload)
            return payload
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


def get_current_user_id(
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
            # Vinculación por email: SOLO con el email verificado por Supabase.
            #
            # Sin esa condición, quien pueda registrarse con el email de otro
            # (si el proyecto no exige confirmación) hereda su usuario local
            # con solo presentar un JWT válido: el `sub` es nuevo, no matchea
            # por external_id, y este camino se lo entrega. El claim
            # `email_verified` es lo que distingue "este es su email" de
            # "escribió su email en un formulario".
            #
            # El puente correcto de identidad es `sync_workspace_access`, que
            # crea/vincula contra lo que dice el control plane. Esto queda como
            # red para usuarios locales previos a esa sincronización.
            supabase_email = decoded.get("email")
            email_verificado = bool(
                decoded.get("email_verified") or decoded.get("email_confirmed_at")
            )
            if supabase_email and email_verificado:
                logger.debug("Local user lookup by external_id failed; trying email match")
                from process_ai_core.db.helpers import get_user_by_email

                local_user = get_user_by_email(session, supabase_email)
                if local_user:
                    local_user.external_id = supabase_user_id
                    local_user.auth_provider = "supabase"
                    session.commit()
                    logger.debug("Linked local user id=%s to auth provider", local_user.id)
            elif supabase_email:
                logger.warning(
                    "No se vincula por email sin verificar (sub=%s): el usuario "
                    "local, si existe, queda intacto.",
                    supabase_user_id,
                )

        if local_user:
            logger.debug("Authenticated local user id=%s", local_user.id)
            remember_user_id(supabase_user_id, local_user.id)
            return local_user.id

        # Sin usuario local: antes este raise era inalcanzable (estaba detrás
        # del return) y la función devolvía None, que se filtraba como user_id
        # a los checks de permisos. JWT válido pero sin User local = el sync
        # contra workspace todavía no corrió o falló: 401 para que el cliente
        # reintente con sesión fresca.
        logger.warning("Authenticated subject not found in local database")
        raise HTTPException(
            status_code=401,
            detail="User not found in local database",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error obteniendo usuario: %s", type(e).__name__)
        # Sin el detalle de la excepción: el mensaje interno (nombres de
        # tabla, rutas, fragmentos de query) se le estaba entregando al
        # cliente. Queda en el log, que es donde sirve.
        raise HTTPException(
            status_code=500,
            detail="Error obteniendo usuario",
        )


# get_current_user / is_superadmin / require_superadmin / require_permission /
# require_role: eliminados. Eran dependencias sin ningún call-site (las dos
# últimas además con firma inusable como Depends), y el chequeo de superadmin
# canónico vive en process_ai_core.db.permissions (_is_superadmin, con el
# claim de plataforma que este módulo no conocía).


