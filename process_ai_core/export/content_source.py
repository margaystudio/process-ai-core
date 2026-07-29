"""
Fuente de verdad del contenido a imprimir de una DocumentVersion.

Devuelve SIEMPRE HTML, porque HTML es lo único que el motor de render entiende
desde que WeasyPrint quedó como único camino de salida.

Por qué normaliza acá y no en el exportador
-------------------------------------------
Todo lo que pasa entre "sacar el contenido" e "imprimirlo" solo sabe operar
sobre HTML: limpiar artefactos LaTeX y reescribir `src="assets/..."` a URLs
firmadas son sustituciones sobre etiquetas. Si el contenido saliera en markdown
y se convirtiera recién dentro del exportador, esos pasos correrían sobre
sintaxis markdown (`![alt](assets/...)`) y no harían nada: el PDF saldría con
las imágenes rotas.

Normalizando acá, el resto del pipeline tiene una sola forma que manejar y
desaparecen los `if fmt == "html"` desperdigados por los call-sites.

En la práctica la conversión casi nunca corre: desde Fase B `content_html` se
persiste al crear la versión (ver api/routes/documents/runs.py), justamente para
que la entrada del render quede congelada y no dependa de la versión de la
librería `markdown` en el momento de aprobar. La conversión queda como red para
filas viejas sin HTML.
"""

from __future__ import annotations

from .markdown_html import markdown_to_html


def get_export_content(version: "object") -> str:
    """
    Devuelve el HTML a imprimir de una versión.

    Args:
        version: Objeto con atributos `content_html` (str | None) y
                 `content_markdown` (str). Típicamente una DocumentVersion.

    Returns:
        El HTML a renderizar.

    Raises:
        ValueError: si la versión no tiene ni HTML ni markdown usable.
    """
    html = getattr(version, "content_html", None)
    if html is not None and str(html).strip():
        return str(html).strip()

    md = getattr(version, "content_markdown", None)
    if md is not None and str(md).strip():
        return markdown_to_html(str(md).strip())

    raise ValueError("La versión no tiene content_html ni content_markdown para exportar.")
