"""Tests para api.workspace_client (tarea 1.2).

Cubre:
  - Caso OK: respuesta válida del workspace → WorkspaceSessionContext
  - 401 del workspace → HTTPException 401
  - 404 del workspace → HTTPException 401 (usuario no registrado)
  - Workspace inalcanzable → HTTPException 503
  - Caché: segunda llamada con el mismo token no hace una segunda request HTTP
  - Header faltante / formato incorrecto → HTTPException 401
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.workspace_client import (
    WorkspaceSessionContext,
    _cache_clear,
    fetch_workspace_context,
    get_workspace_context,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

VALID_CONTEXT_PAYLOAD = {
    "user": {
        "id": "user-uuid-1",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Smith",
    },
    "platform_roles": [],
    "tenant_roles": ["member"],
    "tenant": {"id": "tenant-uuid-1", "name": "Acme", "slug": "acme"},
    "tenants": [{"id": "tenant-uuid-1", "name": "Acme", "slug": "acme"}],
    "applications": [
        {
            "key": "process_ai",
            "name": "Process AI",
            "type": "module",
            "entry_url": "http://localhost:3001",
        }
    ],
}


def _mock_response(status_code: int, json_body=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_body or {}
    return mock


@pytest.fixture(autouse=True)
def clear_cache():
    """Limpia la caché antes de cada test para evitar interferencias."""
    _cache_clear()
    yield
    _cache_clear()


# ── Tests de fetch_workspace_context ─────────────────────────────────────────


def test_ok_returns_typed_context():
    """Respuesta 200 válida → WorkspaceSessionContext correctamente parseado."""
    mock_resp = _mock_response(200, VALID_CONTEXT_PAYLOAD)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        ctx = fetch_workspace_context("valid-token")

    assert isinstance(ctx, WorkspaceSessionContext)
    assert ctx.user.id == "user-uuid-1"
    assert ctx.tenant.slug == "acme"
    assert ctx.tenant_roles == ["member"]
    assert any(a.key == "process_ai" for a in ctx.applications)


def test_workspace_401_raises_401():
    """Workspace devuelve 401 → HTTPException 401."""
    mock_resp = _mock_response(401)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            fetch_workspace_context("bad-token")

    assert exc_info.value.status_code == 401


def test_workspace_404_raises_401():
    """Workspace devuelve 404 (usuario no registrado) → HTTPException 401."""
    mock_resp = _mock_response(404)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            fetch_workspace_context("token-unknown-user")

    assert exc_info.value.status_code == 401


def test_workspace_500_raises_503():
    """Error inesperado del workspace → HTTPException 503."""
    mock_resp = _mock_response(500)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            fetch_workspace_context("any-token")

    assert exc_info.value.status_code == 503


def test_network_error_raises_503():
    """Workspace inalcanzable (RequestError) → HTTPException 503."""
    import httpx

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.ConnectError("connection refused")
        )

        with pytest.raises(HTTPException) as exc_info:
            fetch_workspace_context("any-token")

    assert exc_info.value.status_code == 503


def test_cache_avoids_second_http_call():
    """Segundo llamado con el mismo token usa caché, no hace otra request."""
    mock_resp = _mock_response(200, VALID_CONTEXT_PAYLOAD)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_get = mock_client_cls.return_value.__enter__.return_value.get
        mock_get.return_value = mock_resp

        fetch_workspace_context("cached-token")
        fetch_workspace_context("cached-token")

    assert mock_get.call_count == 1


def test_cache_miss_after_expiry(monkeypatch):
    """Cache expirada → nueva request HTTP."""
    import api.workspace_client as wc

    mock_resp = _mock_response(200, VALID_CONTEXT_PAYLOAD)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_get = mock_client_cls.return_value.__enter__.return_value.get
        mock_get.return_value = mock_resp

        fetch_workspace_context("expiring-token")

        # Simular que el tiempo avanzó más que el TTL
        monkeypatch.setattr(wc, "_CACHE_TTL_SECONDS", -1)

        fetch_workspace_context("expiring-token")

    assert mock_get.call_count == 2


# ── Tests de get_workspace_context (dependencia FastAPI) ────────────────────


def test_dependency_ok():
    """Dependencia FastAPI: header válido → contexto resuelto."""
    mock_resp = _mock_response(200, VALID_CONTEXT_PAYLOAD)

    with patch("api.workspace_client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        ctx = asyncio.run(get_workspace_context(authorization="Bearer valid-token"))

    assert ctx.user.email == "alice@example.com"


def test_dependency_missing_header_raises_401():
    """Sin Authorization header → HTTPException 401."""
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_workspace_context(authorization=None))

    assert exc_info.value.status_code == 401


def test_dependency_bad_format_raises_401():
    """Header sin prefijo Bearer → HTTPException 401."""
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_workspace_context(authorization="Token abc123"))

    assert exc_info.value.status_code == 401
