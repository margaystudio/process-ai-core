"""Normalización de nombres de entidades semánticas.

`canonical_name` es lo que ve el usuario ("SAP ERP"); `normalized_name` es la
clave de matching ("sap erp"): minúsculas, sin acentos, espacios colapsados y
sin signos de puntuación en los bordes.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_EDGE_PUNCT_RE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


def normalize_name(name: str) -> str:
    """Convierte un nombre canónico en su forma normalizada para matching.

    >>> normalize_name("  SAP  ERP ")
    'sap erp'
    >>> normalize_name("Recepción de Mercadería")
    'recepcion de mercaderia'
    """
    if not name:
        return ""
    # Descomponer acentos y descartar marcas diacríticas
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = without_accents.lower()
    collapsed = _WHITESPACE_RE.sub(" ", lowered).strip()
    return _EDGE_PUNCT_RE.sub("", collapsed)
