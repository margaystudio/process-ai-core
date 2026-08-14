"""Dominio de tipos documentales (entidad por-tenant).

Ver docs/PLAN_DOCUMENT_TYPES.md. `document_type` es una entidad de primera clase
por workspace; cada tenant arranca con el set de `defaults.DEFAULT_DOCUMENT_TYPES`.
"""

from .defaults import (
    BEHAVIOR_KEYS,
    DEFAULT_DOCUMENT_TYPES,
    build_default_rows,
    normalize_behaviors,
)
from .resolucion import (
    TIPO_POR_DEFECTO,
    TipoDocumentalInvalido,
    heredar_default_document_type,
    resolver_tipo_de_importacion,
)

__all__ = [
    "BEHAVIOR_KEYS",
    "DEFAULT_DOCUMENT_TYPES",
    "TIPO_POR_DEFECTO",
    "TipoDocumentalInvalido",
    "build_default_rows",
    "heredar_default_document_type",
    "normalize_behaviors",
    "resolver_tipo_de_importacion",
]
