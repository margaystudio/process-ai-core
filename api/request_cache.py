"""Caché en memoria para evitar round-trips repetidos a Postgres remoto.

Cada query a Supabase (us-west-2) cuesta ~600–900 ms desde LATAM. En un request
típico sync + auth + handler abrían 3+ sesiones; esta caché acorta el camino
caliente a 0 ms cuando el usuario/tenant ya se sincronizó recientemente.
"""
from __future__ import annotations

import os
import time
from typing import Optional

_DEFAULT_TTL = 120.0


def _ttl_seconds() -> float:
    raw = os.getenv("REQUEST_CACHE_TTL_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_TTL
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _DEFAULT_TTL


def sync_fingerprint(
    *,
    supabase_sub: str,
    tenant_id: str,
    email: str,
    tenant_roles: list[str],
    platform_roles: list[str],
) -> str:
    return "|".join(
        [
            supabase_sub,
            tenant_id,
            email,
            ",".join(sorted(tenant_roles)),
            ",".join(sorted(platform_roles)),
        ]
    )


_sync_cache: dict[str, tuple[str, float]] = {}
_user_by_sub: dict[str, tuple[str, float]] = {}
_workspace_by_tenant: dict[str, tuple[str, float]] = {}


def get_cached_user_id(supabase_sub: str) -> Optional[str]:
    entry = _user_by_sub.get(supabase_sub)
    if entry is None:
        return None
    user_id, ts = entry
    if time.monotonic() - ts > _ttl_seconds():
        del _user_by_sub[supabase_sub]
        return None
    return user_id


def get_cached_workspace_id(tenant_id: str) -> Optional[str]:
    entry = _workspace_by_tenant.get(tenant_id)
    if entry is None:
        return None
    workspace_id, ts = entry
    if time.monotonic() - ts > _ttl_seconds():
        del _workspace_by_tenant[tenant_id]
        return None
    return workspace_id


def should_skip_sync(fingerprint: str) -> bool:
    entry = _sync_cache.get(fingerprint)
    if entry is None:
        return False
    _, ts = entry
    if time.monotonic() - ts > _ttl_seconds():
        del _sync_cache[fingerprint]
        return False
    return True


def remember_user_id(supabase_sub: str, local_user_id: str) -> None:
    _user_by_sub[supabase_sub] = (local_user_id, time.monotonic())


def remember_workspace_id(tenant_id: str, workspace_id: str) -> None:
    _workspace_by_tenant[tenant_id] = (workspace_id, time.monotonic())


def remember_sync(
    *,
    fingerprint: str,
    supabase_sub: str,
    local_user_id: str,
    tenant_id: str,
    workspace_id: str,
) -> None:
    now = time.monotonic()
    _sync_cache[fingerprint] = (fingerprint, now)
    remember_user_id(supabase_sub, local_user_id)
    remember_workspace_id(tenant_id, workspace_id)


def clear_request_cache() -> None:
    """Solo para tests."""
    _sync_cache.clear()
    _user_by_sub.clear()
    _workspace_by_tenant.clear()
