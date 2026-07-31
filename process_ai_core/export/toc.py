"""
Índice de contenidos del PDF, derivado de los `<h2>` del documento.

El número de página NO se calcula acá: se resuelve en el motor de render con
`target-counter(attr(href), page)`, que es lo único que puede saberlo — depende
de la paginación final, que a su vez depende de la fuente, los saltos y las
imágenes. Calcularlo en Python sería adivinar.

Los anchors se inyectan sobre el HTML del documento. Son estables mientras el
contenido no cambie: se derivan del texto del título, no de un contador, así que
un `#alcance` sigue apuntando a "Alcance" aunque se agregue una sección antes.
"""

from __future__ import annotations

import html as html_mod
import re
import unicodedata

_H2_RE = re.compile(r"<h2(?P<attrs>[^>]*)>(?P<texto>.*?)</h2\s*>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_ID_RE = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_NO_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(texto: str) -> str:
    limpio = unicodedata.normalize("NFKD", texto)
    limpio = "".join(c for c in limpio if not unicodedata.combining(c))
    return _NO_SLUG.sub("-", limpio.lower()).strip("-") or "seccion"


def add_heading_anchors(html: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Pone `id` a cada `<h2>` que no lo tenga y devuelve (html, [(id, título)]).

    Respeta un `id` ya presente: si el contenido viene de un documento importado
    que ya trae anclas, se usan esas y los enlaces internos no se rompen.
    """
    entradas: list[tuple[str, str]] = []
    usados: set[str] = set()

    def repl(m: re.Match) -> str:
        attrs = m.group("attrs") or ""
        crudo = m.group("texto")
        titulo = html_mod.unescape(_TAG_RE.sub("", crudo)).strip()
        if not titulo:
            return m.group(0)

        existente = _ID_RE.search(attrs)
        if existente:
            anchor = existente.group(1)
        else:
            base = _slug(titulo)
            anchor = base
            n = 2
            while anchor in usados:
                anchor = f"{base}-{n}"
                n += 1
            attrs = f'{attrs} id="{anchor}"'

        usados.add(anchor)
        entradas.append((anchor, titulo))
        return f"<h2{attrs}>{crudo}</h2>"

    return _H2_RE.sub(repl, html), entradas


def toc_html(entradas: list[tuple[str, str]], *, titulo: str = "Contenido") -> str:
    """Marca del índice. Vacío si el documento no tiene secciones de nivel 2."""
    if not entradas:
        return ""
    filas = "".join(
        '<li class="pdf-toc-item">'
        f'<a class="pdf-toc-link" href="#{html_mod.escape(anchor)}">'
        f'<span class="pdf-toc-text">{html_mod.escape(texto)}</span>'
        "</a></li>"
        for anchor, texto in entradas
    )
    return (
        '<nav class="pdf-toc">'
        f'<h2 class="pdf-toc-title">{html_mod.escape(titulo)}</h2>'
        f'<ol class="pdf-toc-list">{filas}</ol>'
        "</nav>"
    )
