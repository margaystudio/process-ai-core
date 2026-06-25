"""
Cliente HTTP para el control plane margay-workspace.

Expone `get_workspace_context` como dependencia FastAPI que devuelve
el contexto de sesión del usuario (tenant, roles, aplicaciones).
El contexto se cachea en memoria por token con TTL corto.
"""
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_URL = "http://localhost:8001"
_CACHE_TTL_SECONDS = 30


# ── Schemas (espejo de margay-workspace/app/schemas/session.py) ──────────────

class WorkspaceUser(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class WorkspaceTenant(BaseModel):
    id: str
    name: str
    slug: str


class WorkspaceApplication(BaseModel):
    key: str
    name: str
    type: str
    entry_url: Optional[str] = None


class WorkspaceTenantModules(BaseModel):
    tenant: WorkspaceTenant
    applications: list[WorkspaceApplication] = []


class WorkspaceSessionContext(BaseModel):
    user: WorkspaceUser
    platform_roles: list[str]
    tenant_roles: list[str]
    tenant: WorkspaceTenant
    tenants: list[WorkspaceTenant]
    # DEPRECATED: derivado de tenant_modules (tenant activo). No leer de Workspace.
    applications: list[WorkspaceApplication] = []
    # Fuente de verdad: apps por cada tenant del usuario.
    tenant_modules: list[WorkspaceTenantModules] = []

    @model_validator(mode="after")
    def _derive_applications(self) -> "WorkspaceSessionContext":
        # Apps del tenant activo desde tenant_modules; ignora el campo deprecated.
        if self.tenant_modules:
            mod = next(
                (m for m in self.tenant_modules if m.tenant.id == self.tenant.id), None
            )
            self.applications = mod.applications if mod else []
        return self


# ── Caché en memoria ─────────────────────────────────────────────────────────

_cache: dict[str, tuple["WorkspaceSessionContext", float]] = {}


def _get_workspace_url() -> str:
    return os.getenv("WORKSPACE_URL", DEFAULT_WORKSPACE_URL).rstrip("/")


def _cache_key(token: str, active_tenant_id: Optional[str] = None) -> str:
    return f"{active_tenant_id or ''}:{token}"


def _cache_get(token: str, active_tenant_id: Optional[str] = None) -> Optional[WorkspaceSessionContext]:
    entry = _cache.get(_cache_key(token, active_tenant_id))
    if entry is None:
        return None
    ctx, ts = entry
    if time.monotonic() - ts < _CACHE_TTL_SECONDS:
        return ctx
    del _cache[_cache_key(token, active_tenant_id)]
    return None


def _cache_set(token: str, ctx: WorkspaceSessionContext, active_tenant_id: Optional[str] = None) -> None:
    _cache[_cache_key(token, active_tenant_id)] = (ctx, time.monotonic())


def _cache_clear() -> None:
    """Limpia toda la caché. Solo para tests."""
    _cache.clear()


# ── Cliente HTTP ─────────────────────────────────────────────────────────────

def _fetch_session_context_http(token: str, url: str) -> WorkspaceSessionContext:
    """GET /api/session/context y valida la respuesta."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.RequestError as exc:
        logger.error("workspace unreachable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Workspace service unavailable")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="Tenant not accessible")
    if response.status_code == 404:
        logger.debug("workspace 404: user not registered in workspace")
        raise HTTPException(status_code=401, detail="User not registered in workspace")
    if response.status_code != 200:
        logger.error("workspace returned unexpected status %d", response.status_code)
        raise HTTPException(
            status_code=503, detail=f"Workspace error: {response.status_code}"
        )

    return WorkspaceSessionContext.model_validate(response.json())


def _normalize_active_tenant_id(active_tenant_id: Optional[str]) -> Optional[str]:
    """Ignora valores no-string (p. ej. Header() cuando se llama la dependencia sin FastAPI)."""
    if not isinstance(active_tenant_id, str):
        return None
    value = active_tenant_id.strip()
    return value or None


def fetch_workspace_context(
    token: str,
    active_tenant_id: Optional[str] = None,
) -> WorkspaceSessionContext:
    """
    Llama a GET {WORKSPACE_URL}/api/session/context con el JWT del usuario.

    Si active_tenant_id está seteado:
      1. Intenta primero ?tenant_id= (un solo round-trip cuando el remoto lo soporta).
      2. Si el remoto ignora el param (API vieja), obtiene la lista completa sin param
         y hace override local de ctx.tenant.
    """
    active_tenant_id = _normalize_active_tenant_id(active_tenant_id)

    cached = _cache_get(token, active_tenant_id)
    if cached is not None:
        logger.debug("workspace context: cache hit")
        return cached

    base_url = f"{_get_workspace_url()}/api/session/context"

    if not active_tenant_id:
        ctx = _fetch_session_context_http(token, base_url)
        _cache_set(token, ctx, None)
        _log_context(ctx)
        return ctx

    hinted_url = f"{base_url}?tenant_id={active_tenant_id}"
    ctx_hinted = _fetch_session_context_http(token, hinted_url)
    if ctx_hinted.tenant.id == active_tenant_id:
        selected = next((t for t in ctx_hinted.tenants if t.id == active_tenant_id), None)
        if not selected:
            raise HTTPException(status_code=403, detail="Tenant not accessible")
        _cache_set(token, ctx_hinted, active_tenant_id)
        _log_context(ctx_hinted)
        return ctx_hinted

    # API remota sin soporte de ?tenant_id=: lista completa + override local
    ctx_base = _fetch_session_context_http(token, base_url)
    selected = next((t for t in ctx_base.tenants if t.id == active_tenant_id), None)
    if not selected:
        raise HTTPException(status_code=403, detail="Tenant not accessible")

    if ctx_base.tenant.id == active_tenant_id:
        ctx = ctx_base
    else:
        logger.info(
            "workspace context: override local de tenant activo "
            "(pedido=%s remoto=%s); desplegá margay-workspace con ?tenant_id= "
            "para roles/apps por tenant",
            active_tenant_id,
            ctx_hinted.tenant.id,
        )
        ctx = ctx_base.model_copy(
            update={
                "tenant": selected,
                "tenants": ctx_base.tenants,
            }
        )

    _cache_set(token, ctx, active_tenant_id)
    _log_context(ctx)
    return ctx


def _log_context(ctx: WorkspaceSessionContext) -> None:
    logger.info(
        "workspace context: tenant=%s user=%s tenant_roles=%s platform_roles=%s app_keys=%s",
        ctx.tenant.id,
        ctx.user.id,
        ctx.tenant_roles,
        ctx.platform_roles,
        [a.key for a in ctx.applications],
    )


# ── Dependencias FastAPI ─────────────────────────────────────────────────────

async def get_workspace_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    active_tenant_id: Optional[str] = Header(None, alias="X-Active-Tenant-Id"),
) -> WorkspaceSessionContext:
    """
    Dependencia FastAPI que devuelve el contexto de sesión del workspace.

    Inyectable en cualquier endpoint que necesite conocer tenant/usuario/roles
    sin depender de la base de datos local.

    Usage::

        @router.get("/items")
        def list_items(ctx: WorkspaceSessionContext = Depends(get_workspace_context)):
            tenant_id = ctx.tenant.id
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format"
        )
    token = authorization.removeprefix("Bearer ").strip()
    return fetch_workspace_context(
        token,
        active_tenant_id=_normalize_active_tenant_id(active_tenant_id),
    )


def resolve_tenant_workspace_id(ctx: "WorkspaceSessionContext") -> str:
    """
    Devuelve el ID local del Workspace que corresponde al tenant activo.

    Usa get-or-create: si el Workspace aún no existe en la DB local lo crea
    (con carpeta raíz). Maneja la condición de carrera reintentando una vez
    ante IntegrityError (dos requests simultáneos para el mismo tenant).

    Punto único de resolución: todo el mapeo tenant→Workspace pasa por aquí.
    """
    from sqlalchemy.exc import IntegrityError

    from api.request_cache import get_cached_workspace_id, remember_workspace_id
    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.helpers import get_or_create_workspace_for_tenant

    cached = get_cached_workspace_id(ctx.tenant.id)
    if cached:
        return cached

    for attempt in range(2):
        try:
            with get_db_session() as session:
                workspace_id = get_or_create_workspace_for_tenant(
                    session,
                    tenant_id=ctx.tenant.id,
                    tenant_name=ctx.tenant.name,
                    tenant_slug=ctx.tenant.slug,
                )
            remember_workspace_id(ctx.tenant.id, workspace_id)
            return workspace_id
        except IntegrityError:
            if attempt == 1:
                raise
            # Condición de carrera: otro proceso ya creó el workspace;
            # la segunda pasada lo encontrará vía SELECT.


async def sync_workspace_access(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    active_tenant_id: Optional[str] = Header(None, alias="X-Active-Tenant-Id"),
) -> None:
    """
    Dependencia de router (en dependencies=[]) que, por cada request:

      1. Decodifica el JWT para obtener el Supabase sub (external_id del usuario).
      2. Obtiene el contexto del workspace (con caché de 30 s).
      3. En una sola transacción DB:
           a. Crea/recupera el Workspace local para el tenant activo.
           b. Crea/recupera el User local vinculado al sub (get-or-create por
              external_id → email → nuevo).
           c. Crea/actualiza la WorkspaceMembership local (re-sync si cambia el rol).

    Al ejecutarse antes de que los endpoints resuelvan sus propios parámetros
    (Depends(get_current_user_id)), garantiza que el User local exista en la DB
    cuando get_current_user_id intente buscarlo.

    Es "best-effort": si el JWT o el workspace service fallan, retorna sin error
    y deja que las dependencias individuales (get_current_user_id,
    require_process_ai_access) propaguen el error apropiado.

    No retorna nada (solo produce efectos en la DB).
    """
    active_tenant_id = _normalize_active_tenant_id(active_tenant_id)

    if not authorization or not authorization.startswith("Bearer "):
        return

    token = authorization.removeprefix("Bearer ").strip()

    # Decodificar JWT → sub (external_id del usuario local)
    try:
        from api.dependencies import _decode_and_verify_supabase_jwt
        decoded = _decode_and_verify_supabase_jwt(token)
    except Exception:
        return

    supabase_sub = decoded.get("sub")
    if not supabase_sub:
        return

    # Obtener contexto del workspace (usa caché interna)
    try:
        ctx = fetch_workspace_context(token, active_tenant_id=active_tenant_id)
    except Exception:
        return

    # Sincronizar Workspace + User + Membership en una sola sesión
    try:
        from api.request_cache import remember_sync, should_skip_sync, sync_fingerprint
        from sqlalchemy.exc import IntegrityError

        from process_ai_core.db.database import get_db_session
        from process_ai_core.db.helpers import (
            get_or_create_workspace_for_tenant,
            get_or_create_local_user_from_workspace,
            sync_membership_from_context,
        )

        fp = sync_fingerprint(
            supabase_sub=supabase_sub,
            tenant_id=ctx.tenant.id,
            email=ctx.user.email,
            tenant_roles=ctx.tenant_roles,
            platform_roles=ctx.platform_roles,
        )
        if should_skip_sync(fp):
            return

        for attempt in range(2):
            try:
                with get_db_session() as session:
                    workspace_id = get_or_create_workspace_for_tenant(
                        session,
                        tenant_id=ctx.tenant.id,
                        tenant_name=ctx.tenant.name,
                        tenant_slug=ctx.tenant.slug,
                    )
                    local_user_id = get_or_create_local_user_from_workspace(
                        session,
                        supabase_sub=supabase_sub,
                        email=ctx.user.email,
                        first_name=ctx.user.first_name,
                        last_name=ctx.user.last_name,
                    )
                    sync_membership_from_context(
                        session,
                        local_user_id=local_user_id,
                        workspace_id=workspace_id,
                        tenant_roles=ctx.tenant_roles,
                        platform_roles=ctx.platform_roles,
                    )
                remember_sync(
                    fingerprint=fp,
                    supabase_sub=supabase_sub,
                    local_user_id=local_user_id,
                    tenant_id=ctx.tenant.id,
                    workspace_id=workspace_id,
                )
                break
            except IntegrityError:
                if attempt == 1:
                    raise
    except Exception:
        logger.warning(
            "sync_workspace_access: error al sincronizar estado local (best-effort); "
            "tenant=%s user_sub=%s",
            ctx.tenant.id if ctx else "?",
            supabase_sub,
            exc_info=True,
        )


def _get_required_app_key() -> str:
    return os.getenv("PROCESS_AI_APP_KEY", "process_ai")


async def require_process_ai_access(
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
) -> WorkspaceSessionContext:
    """
    Dependencia FastAPI que verifica que el usuario tenga acceso a la
    aplicación process_ai en su tenant activo.

    Si la clave no aparece en ctx.applications → HTTP 403.
    La clave requerida es configurable via PROCESS_AI_APP_KEY (default: "process_ai").

    Usage (a nivel de router)::

        router = APIRouter(dependencies=[Depends(require_process_ai_access)])

    Returns the context so it can be reused by endpoints that also declare it.
    """
    required_key = _get_required_app_key()
    app_keys = {app.key for app in ctx.applications}

    # tenant_admin y platform superadmin tienen acceso a todos los módulos
    # habilitados en su tenant sin necesidad de asignación explícita por usuario.
    is_tenant_admin = "tenant_admin" in ctx.tenant_roles
    is_platform_superadmin = "superadmin" in ctx.platform_roles

    if required_key not in app_keys and not is_tenant_admin and not is_platform_superadmin:
        logger.warning(
            "process_ai access denied: tenant=%s user=%s app_keys=%s",
            ctx.tenant.id,
            ctx.user.id,
            sorted(app_keys),
        )
        raise HTTPException(
            status_code=403,
            detail=f"Access to '{required_key}' not granted for this tenant",
        )
    logger.debug(
        "process_ai access granted: tenant=%s user=%s (tenant_admin=%s superadmin=%s)",
        ctx.tenant.id,
        ctx.user.id,
        is_tenant_admin,
        is_platform_superadmin,
    )
    return ctx
