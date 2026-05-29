"""Tests para la dependencia require_process_ai_access (tarea 1.3).

Cubre:
  - Usuario con aplicación process_ai → acceso concedido (retorna contexto)
  - Usuario sin ninguna aplicación → HTTPException 403
  - Usuario con otras aplicaciones pero sin process_ai → HTTPException 403
  - PROCESS_AI_APP_KEY configurable via env var
"""

import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.workspace_client import (
    WorkspaceApplication,
    WorkspaceSessionContext,
    WorkspaceTenant,
    WorkspaceUser,
    require_process_ai_access,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_context(app_keys: list[str]) -> WorkspaceSessionContext:
    return WorkspaceSessionContext(
        user=WorkspaceUser(id="user-1", email="alice@example.com"),
        platform_roles=[],
        tenant_roles=["member"],
        tenant=WorkspaceTenant(id="tenant-1", name="Acme", slug="acme"),
        tenants=[WorkspaceTenant(id="tenant-1", name="Acme", slug="acme")],
        applications=[
            WorkspaceApplication(key=k, name=k, type="module") for k in app_keys
        ],
    )


async def _run_gate(ctx: WorkspaceSessionContext) -> WorkspaceSessionContext:
    """Invoca require_process_ai_access inyectando el contexto directamente."""
    with patch(
        "api.workspace_client.get_workspace_context",
        return_value=ctx,
    ):
        return await require_process_ai_access(ctx=ctx)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_user_with_process_ai_passes():
    """Usuario con process_ai en applications → gate pasa y retorna contexto."""
    ctx = _make_context(["process_ai", "other_app"])
    result = asyncio.run(_run_gate(ctx))
    assert result is ctx


def test_user_without_any_app_raises_403():
    """Sin applications → HTTPException 403."""
    ctx = _make_context([])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run_gate(ctx))
    assert exc_info.value.status_code == 403


def test_user_with_other_apps_but_not_process_ai_raises_403():
    """Con otras apps pero sin process_ai → HTTPException 403."""
    ctx = _make_context(["analytics", "crm"])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run_gate(ctx))
    assert exc_info.value.status_code == 403
    assert "process_ai" in exc_info.value.detail


def test_custom_app_key_via_env(monkeypatch):
    """PROCESS_AI_APP_KEY configurable: cambia la clave requerida."""
    monkeypatch.setenv("PROCESS_AI_APP_KEY", "custom_module")

    ctx_without_custom = _make_context(["process_ai"])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run_gate(ctx_without_custom))
    assert exc_info.value.status_code == 403

    ctx_with_custom = _make_context(["custom_module"])
    result = asyncio.run(_run_gate(ctx_with_custom))
    assert result is ctx_with_custom


def test_403_detail_mentions_app_key():
    """El mensaje de 403 incluye el nombre de la app requerida."""
    ctx = _make_context([])
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(_run_gate(ctx))
    assert "process_ai" in exc_info.value.detail
