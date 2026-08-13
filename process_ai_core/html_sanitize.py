"""
Saneamiento del HTML de un documento, del lado del servidor.

POR QUÉ ACÁ Y NO SOLO EN LA UI
------------------------------
El cuerpo de un documento es HTML que escribe el usuario (editor manual) o que
sale de la generación por IA, y después se **persiste** y se le muestra a OTRA
persona — típicamente al aprobador, que es justo quien tiene el permiso que un
atacante querría. Sin saneo, `<img src=x onerror="...">` guardado por quien
edita ejecuta en la sesión de quien revisa.

La UI sanea al pintar, y esa es la barrera que corta el XSS en el navegador.
Esto es la otra mitad: el editor **no es el único camino de escritura** (el
endpoint acepta cualquier HTML de cualquier cliente), y el HTML guardado lo
consumen además el render del PDF y cualquier pantalla futura. Saneando al
guardar, el dato queda limpio en la base y no depende de que todos los
consumidores se acuerden de sanear.

QUÉ SE PERMITE
--------------
La allow-list es exactamente el markup que el sistema produce: lo de
`markdown_html.render_frozen_html` (extensiones `extra`, `nl2br`, `tables`,
`sane_lists`) y lo del editor Tiptap (StarterKit + Link + Image + Table
redimensionable). Se dejó a propósito `style` en los elementos de tabla, porque
las columnas redimensionables del editor guardan el ancho ahí y sacarlo
rompería tablas ya guardadas; se le filtran `url()` y `expression()`, que son
las dos formas por las que un `style` deja de ser cosmético.

Se apoya en `nh3` (bindings de ammonia, el sanitizador de Rust): escribir un
sanitizador de HTML a mano es un anti-patrón conocido — los bypasses viven en
los detalles del parser, no en la lista de tags.
"""

from __future__ import annotations

import logging

import nh3

logger = logging.getLogger(__name__)

#: Tags permitidos: encabezados, texto, listas, tablas, código, imágenes, links.
_TAGS: set[str] = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr", "div", "span",
    "strong", "b", "em", "i", "u", "s", "del", "ins", "sub", "sup", "mark", "small",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    "a", "img",
    "dl", "dt", "dd",
}

#: Atributos por tag. `class` va en casi todos porque el CSS del PDF y del
#: visor cuelga de ahí; `style` solo en tablas (ver docstring).
_ATTRS: dict[str, set[str]] = {
    "*": {"class", "id", "title", "lang", "dir"},
    # Sin `rel`: lo escribe `link_rel` más abajo, que lo fuerza en TODOS los
    # links (nh3 rechaza declararlo acá y a la vez usar link_rel).
    "a": {"href", "target", "name"},
    "img": {"src", "alt", "width", "height"},
    "table": {"style"},
    "col": {"style", "span", "width"},
    "colgroup": {"style", "span"},
    "th": {"colspan", "rowspan", "colwidth", "style", "scope"},
    "td": {"colspan", "rowspan", "colwidth", "style"},
    "ol": {"start", "type"},
    "code": {"data-language"},
}

#: Esquemas de URL admitidos en `href`/`src`. Sin `javascript:`, sin `vbscript:`,
#: sin `file:` (que en el render del PDF sería lectura de disco).
_URL_SCHEMES: set[str] = {"http", "https", "mailto", "data"}

#: Lo que convierte un `style` en algo más que cosmética: `url()` sale a la red
#: (o al disco, en el render del PDF) y `expression()` es JS en motores viejos.
_STYLE_PROHIBIDO = ("url(", "expression(", "javascript:", "@import")


def _filtrar_atributo(tag: str, attr: str, valor: str) -> str | None:
    """Descarta `style` peligroso; el resto pasa como viene.

    Devolver None borra el atributo (contrato de `nh3.clean`).
    """
    if attr == "style":
        plano = valor.lower().replace(" ", "")
        if any(p.replace(" ", "") in plano for p in _STYLE_PROHIBIDO):
            return None
    return valor


def sanitize_document_html(html: str | None) -> str:
    """
    Devuelve el HTML sin nada ejecutable, conservando el contenido legítimo.

    Elimina `<script>`, `<iframe>`, `<object>`, `<embed>`, `<style>`, cualquier
    atributo `on*` (onerror, onload, …) y las URLs con esquemas peligrosos.
    Entrada vacía o None → cadena vacía.
    """
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_TAGS,
        attributes={k: set(v) for k, v in _ATTRS.items()},
        url_schemes=_URL_SCHEMES,
        attribute_filter=_filtrar_atributo,
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
