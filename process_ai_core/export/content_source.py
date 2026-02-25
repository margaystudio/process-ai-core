"""
Fuente de verdad para export/PDF de una DocumentVersion.

Regla: si content_html existe y no está vacío → es la fuente de verdad.
       Si no → usar content_markdown.
"""

from __future__ import annotations

from typing import Literal, Tuple


def get_export_content(version: "object") -> Tuple[str, Literal["html", "markdown"]]:
    """
    Devuelve el contenido a usar para generar PDF y su formato.

    Args:
        version: Objeto con atributos content_html (str | None) y content_markdown (str).
                 Típicamente una DocumentVersion de SQLAlchemy.

    Returns:
        (content, format): content es el string a exportar; format es "html" o "markdown".

    Raises:
        ValueError: Si no hay contenido (ni html ni markdown usable).
    """
    html = getattr(version, "content_html", None)
    if html is not None and str(html).strip():
        return (html.strip(), "html")
    md = getattr(version, "content_markdown", None)
    if md is not None and str(md).strip():
        return (md.strip(), "markdown")
    raise ValueError("La versión no tiene content_html ni content_markdown para exportar.")
