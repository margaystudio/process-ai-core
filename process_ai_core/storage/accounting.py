"""
Contabilidad de almacenamiento por tenant (Fase E2).

Gracias al esquema tenant-scoped (`workspaces/{ws}/...`), el uso de un workspace es
sumar el tamaño de todos los blobs bajo su prefijo.
"""

from __future__ import annotations

from .factory import get_storage
from .keys import workspace_prefix

_BYTES_PER_GB = 1_000_000_000  # GB decimal (10^9), consistente con facturación cloud


def workspace_usage_bytes(workspace_id: str) -> int:
    """Bytes ocupados por un workspace en el storage (suma por prefijo)."""
    return get_storage().usage_bytes(workspace_prefix(workspace_id))


def workspace_usage_gb(workspace_id: str) -> float:
    """Uso del workspace en GB (decimal)."""
    return workspace_usage_bytes(workspace_id) / _BYTES_PER_GB
