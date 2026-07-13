"""Dominio de tipos documentales (entidad por-tenant).

Ver docs/PLAN_DOCUMENT_TYPES.md. `document_type` es una entidad de primera clase
por workspace; cada tenant arranca con el set de `defaults.DEFAULT_DOCUMENT_TYPES`.
"""

from .defaults import (
    BEHAVIOR_KEYS,
    DEFAULT_DOCUMENT_TYPES,
    normalize_behaviors,
)

__all__ = [
    "BEHAVIOR_KEYS",
    "DEFAULT_DOCUMENT_TYPES",
    "normalize_behaviors",
]
