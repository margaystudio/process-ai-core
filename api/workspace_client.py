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
from pydantic import BaseModel

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


class WorkspaceSessionContext(BaseModel):
    user: WorkspaceUser
    platform_roles: list[str]
    tenant_roles: list[str]
    tenant: WorkspaceTenant
    tenants: list[WorkspaceTenant]
    applications: list[WorkspaceApplication]


# ── Caché en memoria ─────────────────────────────────────────────────────────

_cache: dict[str, tuple["WorkspaceSessionContext", float]] = {}


def _get_workspace_url() -> str:
    return os.getenv("WORKSPACE_URL", DEFAULT_WORKSPACE_URL).rstrip("/")


def _cache_get(token: str) -> Optional[WorkspaceSessionContext]:
    entry = _cache.get(token)
    if entry is None:
        return None
    ctx, ts = entry
    if time.monotonic() - ts < _CACHE_TTL_SECONDS:
        return ctx
    del _cache[token]
    return None


def _cache_set(token: str, ctx: WorkspaceSessionContext) -> None:
    _cache[token] = (ctx, time.monotonic())


def _cache_clear() -> None:
    """Limpia toda la caché. Solo para tests."""
    _cache.clear()


# ── Cliente HTTP ─────────────────────────────────────────────────────────────

def fetch_workspace_context(token: str) -> WorkspaceSessionContext:
    """
    Llama a GET {WORKSPACE_URL}/api/session/context con el JWT del usuario.

    Propagación de errores:
      - 401 workspace → 401 aquí
      - 404 workspace → 401 aquí (usuario no registrado en workspace)
      - otros 4xx/5xx  → 503 aquí
    """
    cached = _cache_get(token)
    if cached is not None:
        logger.debug("workspace context: cache hit")
        return cached

    url = f"{_get_workspace_url()}/api/session/context"
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.RequestError as exc:
        logger.error("workspace unreachable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Workspace service unavailable")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if response.status_code == 404:
        logger.debug("workspace 404: user not registered in workspace")
        raise HTTPException(status_code=401, detail="User not registered in workspace")
    if response.status_code != 200:
        logger.error("workspace returned unexpected status %d", response.status_code)
        raise HTTPException(
            status_code=503, detail=f"Workspace error: {response.status_code}"
        )

    ctx = WorkspaceSessionContext.model_validate(response.json())
    _cache_set(token, ctx)
    logger.debug(
        "workspace context fetched: tenant_id=%s user_id=%s",
        ctx.tenant.id,
        ctx.user.id,
    )
    return ctx


# ── Dependencias FastAPI ─────────────────────────────────────────────────────

async def get_workspace_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
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
    return fetch_workspace_context(token)


def resolve_tenant_workspace_id(ctx: "WorkspaceSessionContext") -> str:
    """
    Devuelve el ID de workspace local (process_ai_core) para el tenant activo.

    TODO (1.4b): implementar get-or-create del Workspace local en la DB de
    process_ai_core, usando ctx.tenant.id/slug como clave de búsqueda.
    Por ahora asume que ctx.tenant.id coincide con el Workspace.id local.
    Punto único de resolución: sólo hay que cambiar este helper en 1.4b.
    """
    return ctx.tenant.id


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
    if required_key not in app_keys:
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
        "process_ai access granted: tenant=%s user=%s", ctx.tenant.id, ctx.user.id
    )
    return ctx
