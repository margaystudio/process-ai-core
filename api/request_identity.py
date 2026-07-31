"""Deja la identidad del request al alcance del directorio de usuarios.

`/directory` de Workspace está gateado por `assert_app_member`: se llama con el
**JWT del usuario**, no con una service key. Pero el punto donde el módulo
resuelve nombres es `resolve_signatories`, que vive en el core y lo invocan tanto
una ruta HTTP como el congelado del PDF. Pasarle el token por parámetro
obligaría a enhebrarlo por toda la cadena de llamadas, así que viaja por
contextvar — el equivalente del `get_request_context()` de CRM y dashboards.

Es una dependencia **async** a propósito. FastAPI corre las dependencias `def`
en el threadpool, y un contextvar seteado ahí no vuelve al contexto del request;
una `async def` corre en el mismo contexto que el endpoint, así que lo que setea
sí lo ve todo lo que pasa después (incluido un endpoint `def`, que hereda una
copia del contexto al despacharse al threadpool).

Es best-effort, igual que `sync_workspace_access`: si no hay token o Workspace no
contesta, no setea nada y el directorio sirve lo que tenga guardado. Resolver
nombres nunca rompe una request.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Header

from process_ai_core.db.directory import set_request_identity

logger = logging.getLogger(__name__)


async def capture_request_identity(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    active_tenant_id: Optional[str] = Header(None, alias="X-Active-Tenant-Id"),
) -> None:
    """Registra (JWT, tenant activo) para el refresh del directorio."""
    from .workspace_client import _normalize_active_tenant_id, fetch_workspace_context

    set_request_identity(None, None)

    if not authorization or not authorization.startswith("Bearer "):
        return
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return

    tenant_id = _normalize_active_tenant_id(active_tenant_id)
    try:
        # Cache hit: `sync_workspace_access` ya lo trajo en este mismo request
        # (TTL 30 s, misma clave). No es un round-trip extra.
        ctx = fetch_workspace_context(token, active_tenant_id=tenant_id)
    except Exception:
        logger.debug("No se pudo resolver el tenant activo para el directorio")
        return

    set_request_identity(token, ctx.tenant.id)
