from __future__ import annotations

import html as html_mod
import re
from dataclasses import dataclass
from pathlib import Path

from .branding import PdfBranding
from .color import resolve_palette
from .document_context import DocumentContext
from .qr import qr_data_uri
from .toc import add_heading_anchors, toc_html

# Familia tipográfica del PDF.
#
# Antes acá decía 'Helvetica Neue', Arial: ninguna de las dos está instalada en
# Dockerfile.api, así que en producción WeasyPrint caía a DejaVu Sans y el PDF no
# se parecía al de desarrollo (DejaVu es más ancha ⇒ distinta paginación).
#
# Se eligió **Liberation Sans**, instalada explícitamente vía `fonts-liberation`
# en la imagen. Es métricamente compatible con Arial/Helvetica: mismos anchos de
# glifo, misma paginación. Por eso se deja Arial/Helvetica como fallback — una
# Mac de desarrollo sin Liberation renderiza con Arial y produce EL MISMO
# layout, no solo uno parecido.
#
# Se descartó embeber Inter/Source Sans 3 en la imagen: hubiera obligado a
# versionar binarios de fuente en el repo y a rehacer la paginación, y esta fase
# no toca el diseño. Cuando la Fase C defina la identidad visual, cambiar esta
# constante + el paquete apt es el único punto a tocar.
_FONT_STACK = "'Liberation Sans', Arial, Helvetica, sans-serif"
_MONO_FONT_STACK = "'Liberation Mono', 'Courier New', monospace"


def root_variables_css(branding: PdfBranding | None) -> str:
    """
    Bloque `:root` con la paleta resuelta del cliente.

    Se inyecta en el `<head>` y NO se declara en `_BASE_CSS`, que solo consume
    las variables. Así hay una sola fuente de verdad y no depende del orden de
    cascada entre la hoja del documento y la que se pasa a `write_pdf`.
    """
    paleta = resolve_palette(
        getattr(branding, "primary_color", None),
        getattr(branding, "secondary_color", None),
    )
    declaraciones = "\n".join(f"    --{nombre}: {valor};" for nombre, valor in paleta.items())
    return f":root {{\n{declaraciones}\n}}"


_BASE_CSS = f"""
/* ── Página del cuerpo ─────────────────────────────────────────────────────
   El header corrido y el pie de tres campos viven acá. La portada usa su propia
   @page (más abajo) sin ninguna de las dos cosas. */
@page {{
    size: A4;
    margin: 2.6cm 2.2cm 2.1cm 2.2cm;

    @top-center {{
        content: element(pdf-page-header);
        /* El ancho va también acá: la margin-box se dimensiona por su contenido
           y recortaba el extremo derecho del header (la versión desaparecía).
           16.6cm = A4 menos los márgenes laterales. */
        width: 16.6cm;
        vertical-align: bottom;
    }}
}}

body {{
    font-family: {_FONT_STACK};
    font-size: 10.5pt;
    /* 1.62 da una mancha tipográfica pareja a 10.5pt sobre A4 con estos
       márgenes: suficiente aire para leer sin desperdiciar página. */
    line-height: 1.62;
    color: var(--pdf-ink);
}}

pre, code {{
    font-family: {_MONO_FONT_STACK};
}}
""" + """
/* ── Header corrido ────────────────────────────────────────────────────────
   Ocupa el ancho completo del área de contenido. Logo + identidad del
   documento a la izquierda, versión a la derecha. Sin estado: el estado cambia
   sin que cambie el documento, así que no va impreso. */
.pdf-page-header {
    position: running(pdf-page-header);
    /* El elemento corrido se dimensiona dentro de la margin-box @top-center, que
       NO ocupa el ancho de la página: sin un ancho explícito el header quedaba
       apretado en una columna angosta y el título se partía en dos líneas.
       16.6cm = 21cm de A4 menos los 2.2cm de margen de cada lado. */
    width: 16.6cm;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 0.45rem;
    border-bottom: 0.75pt solid var(--pdf-border-color);
}

.pdf-brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    min-width: 0;
}

.pdf-brand img {
    width: 26px;
    height: 26px;
    object-fit: contain;
    margin: 0;
    flex: none;
}

.pdf-brand-copy {
    display: flex;
    flex-direction: column;
    gap: 0.05rem;
    min-width: 0;
}

.pdf-brand-kicker {
    font-size: 6.5pt;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--pdf-ink-faint);
}

.pdf-brand-title {
    font-size: 9pt;
    font-weight: 700;
    color: var(--pdf-ink);
}

.pdf-header-version {
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--pdf-primary-text);
    white-space: nowrap;
    flex: none;
}

.pdf-content {
    padding-top: 0.1rem;
}

/* ── Jerarquía tipográfica ─────────────────────────────────────────────────
   Antes los cuatro niveles eran weight 600 y el mismo #111111: la jerarquía se
   apoyaba SOLO en el tamaño, que a 21/15/12/10.5pt son saltos chicos. Ahora
   cada nivel cambia además de color, peso y aire, así que se distinguen incluso
   en una fotocopia en escala de grises. */
h1 {
    font-size: 18pt;
    font-weight: 700;
    line-height: 1.18;
    letter-spacing: -0.01em;
    color: var(--pdf-primary-text);
    margin: 0 0 0.7em;
}

h2 {
    font-size: 13pt;
    font-weight: 700;
    line-height: 1.25;
    color: var(--pdf-primary-text);
    margin: 1.7em 0 0.55em;
    padding-bottom: 0.28em;
    /* Regla de acento en el color secundario: separa secciones sin necesidad de
       más espacio en blanco. */
    border-bottom: 2pt solid var(--pdf-secondary);
}

h3 {
    font-size: 11pt;
    font-weight: 700;
    line-height: 1.3;
    color: var(--pdf-ink);
    margin: 1.3em 0 0.35em;
}

h4 {
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--pdf-ink-soft);
    margin: 1.1em 0 0.3em;
}

h1, h2, h3, h4 {
    page-break-after: avoid;
}

p { margin: 0.5em 0; }

/* ── Tablas ────────────────────────────────────────────────────────────────*/
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.1em 0;
    font-size: 9.5pt;
}

/* El encabezado se repite cuando la tabla corta de página. */
thead {
    display: table-header-group;
}

/* Antes era `table { page-break-inside: avoid }`: una tabla más larga que una
   página no tenía dónde caber y rompía el flujo. El corte va POR FILA — ninguna
   fila queda partida al medio, pero la tabla sí puede continuar en la hoja
   siguiente. */
tr {
    page-break-inside: avoid;
}

th {
    background-color: var(--pdf-primary);
    color: var(--pdf-on-primary);
    border: 0.75pt solid var(--pdf-primary);
    padding: 6px 9px;
    text-align: left;
    font-weight: 700;
    font-size: 9pt;
    letter-spacing: 0.02em;
}

td {
    border: 0.75pt solid var(--pdf-border-color);
    padding: 6px 9px;
    vertical-align: top;
}

tbody tr:nth-child(even) td {
    background-color: var(--pdf-primary-tint);
}

ul, ol {
    margin: 0.45em 0 0.85em;
    padding-left: 1.3em;
}

li { margin: 0.22em 0; }

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.8em auto;
    page-break-inside: avoid;
}

pre, code {
    font-size: 8.5pt;
    background-color: var(--pdf-surface-color);
    border-radius: 3px;
}

pre {
    padding: 0.7em;
    border: 0.75pt solid var(--pdf-border-color);
    page-break-inside: avoid;
}

code { padding: 0.1em 0.3em; }

blockquote {
    border-left: 2.5pt solid var(--pdf-secondary);
    margin: 0.85em 0;
    padding: 0.15em 0 0.15em 0.9em;
    color: var(--pdf-ink-soft);
}


/* ── Índice de contenidos ──────────────────────────────────────────────────
   El número de página lo resuelve el motor con target-counter(): depende de la
   paginación final, así que no se puede calcular antes de renderizar. */
.pdf-toc {
    margin: 0 0 2em;
    page-break-after: avoid;
}

.pdf-toc-list {
    list-style: none;
    margin: 0;
    padding: 0;
    counter-reset: pdf-toc;
}

.pdf-toc-item {
    counter-increment: pdf-toc;
    margin: 0;
    border-bottom: 0.5pt solid var(--pdf-border-color);
}

.pdf-toc-link {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.42em 0;
    text-decoration: none;
    color: var(--pdf-ink);
    font-size: 10pt;
}

.pdf-toc-link::before {
    content: counter(pdf-toc);
    flex: none;
    min-width: 1.2rem;
    font-weight: 700;
    color: var(--pdf-ink-faint);
}

.pdf-toc-text { flex: 1; }

.pdf-toc-link::after {
    content: target-counter(attr(href), page);
    flex: none;
    color: var(--pdf-ink-faint);
    font-variant-numeric: tabular-nums;
}

/* ── Historial de versiones ────────────────────────────────────────────────
   SIN columna de estado: el estado es mutable y este PDF no se puede reescribir.
   Las versiones figuran por haber sido aprobadas y superadas, que es permanente. */
.pdf-version-history {
    margin: 0 0 2em;
}

.pdf-version-history td:first-child {
    font-weight: 700;
    text-align: center;
    width: 3.2rem;
}

.pdf-version-history .pdf-vh-sin-datos {
    color: var(--pdf-ink-faint);
    font-style: italic;
}

/* ── Portada ───────────────────────────────────────────────────────────────
   Página propia sin header ni pie corridos: es una carátula, no una hoja más
   del documento. */
@page cover {
    margin: 0;
    @top-center { content: none; }
    @bottom-left { content: none; }
    @bottom-center { content: none; }
    @bottom-right { content: none; }
}

.pdf-cover {
    page: cover;
    break-after: page;
    height: 297mm;
    display: flex;
    flex-direction: column;
}

/* Filete superior con los dos colores de marca. */
.pdf-cover-rule {
    flex: none;
    height: 7mm;
    background-color: var(--pdf-primary);
    border-bottom: 2.5mm solid var(--pdf-secondary);
}

.pdf-cover-body {
    flex: 1;
    padding: 16mm 20mm 0;
    display: flex;
    flex-direction: column;
}

.pdf-cover-client {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding-bottom: 0.7rem;
    border-bottom: 0.75pt solid var(--pdf-border-color);
}

.pdf-cover-client img {
    width: 42px;
    height: 42px;
    object-fit: contain;
    margin: 0;
    flex: none;
}

.pdf-cover-client-name {
    font-size: 12pt;
    font-weight: 700;
    color: var(--pdf-ink);
    line-height: 1.2;
}

.pdf-cover-controlled {
    font-size: 7.5pt;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--pdf-ink-faint);
    margin-top: 0.15rem;
}

/* Bloque de título. El tipo documental va como ANTETÍTULO: es parte del título,
   no una fila de metadata. */
.pdf-cover-titleblock {
    /* Empuja el bloque de título y el acta hacia el tercio inferior: deja
       respirar arriba y los agrupa con el bloque de verificación del pie. */
    margin-top: auto;
}

.pdf-cover-kicker {
    font-size: 9.5pt;
    font-weight: 700;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--pdf-secondary-text);
    margin: 0 0 0.5rem;
}

.pdf-cover-title {
    font-size: 27pt;
    font-weight: 700;
    line-height: 1.12;
    letter-spacing: -0.015em;
    color: var(--pdf-primary-text);
    margin: 0;
    padding: 0;
    border: 0;
}

.pdf-cover-ids {
    margin: 0.9rem 0 0;
    font-size: 10pt;
    color: var(--pdf-ink-soft);
}

.pdf-cover-ids .sep {
    color: var(--pdf-border-strong);
    padding: 0 0.4rem;
}

.pdf-cover-code {
    font-family: var(--pdf-mono, monospace);
    font-weight: 700;
    color: var(--pdf-ink);
}

/* Acta de aprobación / Responsables. */
.pdf-cover-record {
    margin-top: 18mm;
    margin-bottom: 8mm;
    border-top: 0.75pt solid var(--pdf-border-color);
    padding-top: 0.9rem;
}

.pdf-cover-record-title {
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--pdf-primary-text);
    margin: 0 0 0.6rem;
}

.pdf-cover-record-grid {
    display: flex;
    flex-wrap: wrap;
    margin: 0;
}

.pdf-cover-record-item {
    width: 50%;
    padding: 0.32rem 1rem 0.32rem 0;
    box-sizing: border-box;
}

.pdf-cover-record-label {
    font-size: 7.5pt;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--pdf-ink-faint);
}

.pdf-cover-record-value {
    font-size: 10pt;
    color: var(--pdf-ink);
    line-height: 1.35;
}

/* Bloque de verificación, al pie de la portada. */
.pdf-cover-verify {
    flex: none;
    display: flex;
    align-items: center;
    gap: 0.9rem;
    margin: 0 20mm 14mm;
    padding: 0.7rem 0.9rem;
    background-color: var(--pdf-surface-color);
    border: 0.75pt solid var(--pdf-border-color);
    border-left: 3pt solid var(--pdf-primary);
}

.pdf-cover-verify img {
    width: 74px;
    height: 74px;
    margin: 0;
    flex: none;
    image-rendering: pixelated;
}

.pdf-cover-verify-copy {
    min-width: 0;
}

.pdf-cover-verify-title {
    font-size: 8.5pt;
    font-weight: 700;
    color: var(--pdf-ink);
    margin: 0 0 0.15rem;
}

.pdf-cover-verify-body {
    font-size: 8pt;
    line-height: 1.45;
    color: var(--pdf-ink-soft);
    margin: 0;
}

.pdf-cover-verify-id {
    font-family: var(--pdf-mono, monospace);
    font-size: 7.5pt;
    color: var(--pdf-ink-faint);
    margin: 0.3rem 0 0;
    word-break: break-all;
}
"""
# ── Marca de invalidación ─────────────────────────────────────────────────────
#
# La lleva TODO PDF que no sea el artefacto congelado de una versión aprobada:
# previews de DRAFT/IN_REVIEW/REJECTED, el PDF posterior a un patch por IA y el
# process.pdf de un run.
#
# No es una marca de ESTADO ("estado: borrador"), es una marca de INVALIDACIÓN:
# no describe un atributo del documento, invalida el papel. La diferencia
# importa porque el riesgo real no es que alguien no sepa en qué estado está el
# documento, sino que imprima un borrador, lo haga circular y termine operando
# con él. Por eso el texto dice qué NO se puede hacer, no en qué estado está.
#
# El PDF aprobado NO lleva contramarca ("APROBADO", banda verde): solo nace de
# versiones aprobadas, así que decirlo sería redundante — y envejecería mal,
# porque el estado cambia cuando se aprueba una versión posterior mientras que
# el PDF congelado no se puede reescribir (criterio de ADR-018 y ADR-020).
#
# El color vive en una variable para que la Fase C, que define la identidad
# visual, lo retoque en un solo lugar sin tocar esta lógica.
_INVALIDATION_TEXT = "BORRADOR"
_INVALIDATION_TITLE = "BORRADOR — SIN VALOR OPERATIVO"
_INVALIDATION_BODY = (
    "Este documento no debe usarse para operar, capacitar ni auditar, "
    "ni distribuirse fuera del circuito de revisión."
)
_INVALIDATION_FOOTER = "BORRADOR — sin valor operativo"

# Repeticiones por fila y cantidad de filas: lo justo para cubrir un A4 entero.
# Las filas que sobran las recorta el `overflow: hidden` del contenedor.
_WATERMARK_COLUMNS = 5
_WATERMARK_ROWS = 11

_INVALIDATION_CSS = f"""
:root {{
    --pdf-invalid-color: #b42318;
    --pdf-invalid-tint: #fef3f2;
}}

/* `position: fixed` en WeasyPrint ancla el elemento a la caja de página y lo
   REPITE en todas: es lo que hace que la marca de agua no sea solo de la
   primera hoja. `overflow: hidden` recorta las filas que sobran de la
   rotación. */
.pdf-invalidation-watermark {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    z-index: 1000;
}}

.pdf-invalidation-watermark-inner {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}}

/* Se rota cada FILA por separado en vez de rotar el bloque entero. Rotar el
   bloque desplaza las filas progresivamente hacia un costado y deja esquinas
   vacías; rotando fila por fila el patrón queda parejo en toda la hoja.
   Verificado comparando ambas variantes renderizadas.

   Va POR ENCIMA del contenido, no por detrás: las tablas tienen fondo sólido y
   una marca de agua detrás desaparecería justo en las páginas más densas. La
   opacidad baja es lo que evita que compita con la lectura. */
.pdf-invalidation-watermark-row {{
    font-family: {_FONT_STACK};
    font-size: 26pt;
    font-weight: 700;
    letter-spacing: 0.3em;
    line-height: 3.1;
    white-space: nowrap;
    text-align: center;
    color: var(--pdf-invalid-color);
    opacity: 0.09;
    transform: rotate(-35deg);
}}

/* Bloque de la primera página: en flujo normal, antes del contenido. */
.pdf-invalidation-notice {{
    border: 1px solid var(--pdf-invalid-color);
    border-left-width: 4px;
    background-color: var(--pdf-invalid-tint);
    padding: 0.7rem 0.9rem;
    margin: 0 0 1.4rem;
    page-break-inside: avoid;
    page-break-after: avoid;
}}

.pdf-invalidation-notice-title {{
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--pdf-invalid-color);
    margin: 0 0 0.25rem;
}}

.pdf-invalidation-notice-body {{
    font-size: 9pt;
    line-height: 1.5;
    color: var(--pdf-invalid-color);
    margin: 0;
}}

/* El campo central del pie lo pinta `_footer_css`; acá solo se le da el color de
   alarma cuando el documento está invalidado. */
@page {{
    @bottom-center {{
        color: var(--pdf-invalid-color);
        font-weight: 700;
    }}
}}
"""


def _css_string(value: str) -> str:
    """Escapa un string para usarlo como `content: "..."` en CSS."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _footer_css(context: DocumentContext | None) -> str:
    """
    Pie de tres campos, generado por render porque lleva datos del documento.

    - Izquierda: identidad del documento (código · título · versión).
    - Centro: la advertencia sobre el papel.
    - Derecha: "Página X de Y".

    El campo central dice "Copia no controlada — verificá la vigencia en línea"
    y no "documento vigente", porque una hoja impresa no puede afirmar eso: el
    documento pudo reemplazarse un minuto después de imprimirla. Remite al QR de
    la portada, que sí puede responderlo.

    Si el documento está invalidado, ese campo lo dice en cambio: un borrador es
    algo más fuerte que una copia no controlada, y es el mensaje que importa.
    """
    partes = []
    if context:
        if context.code:
            partes.append(context.code)
        if context.title:
            partes.append(context.title)
        if context.version_number is not None:
            partes.append(f"v{context.version_number}")
    izquierda = " · ".join(partes)

    centro = (
        _INVALIDATION_FOOTER
        if _marks_as_invalid(context)
        else "Copia no controlada — verificá la vigencia en línea"
    )

    # Las tres margin-boxes se reparten el ancho por su contenido, y con textos
    # largos cada una se partía en dos líneas. Los anchos explícitos (sobre los
    # 16.6cm de área de contenido) las mantienen en una sola línea; el campo
    # izquierdo recorta con elipsis si el título es muy largo, porque es el único
    # de los tres que puede crecer sin límite.
    return f"""
@page {{
    @bottom-left {{
        content: "{_css_string(izquierda)}";
        font-family: {_FONT_STACK};
        font-size: 7pt;
        color: var(--pdf-ink-faint);
        vertical-align: middle;
        width: 6.2cm;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    @bottom-center {{
        content: "{_css_string(centro)}";
        font-family: {_FONT_STACK};
        font-size: 7pt;
        color: var(--pdf-ink-faint);
        vertical-align: middle;
        width: 7.4cm;
        text-align: center;
        white-space: nowrap;
    }}
    @bottom-right {{
        content: "Página " counter(page) " de " counter(pages);
        font-family: {_FONT_STACK};
        font-size: 7pt;
        color: var(--pdf-ink-faint);
        vertical-align: middle;
        width: 3cm;
        text-align: right;
        white-space: nowrap;
    }}
}}
"""


def _marks_as_invalid(context: DocumentContext | None) -> bool:
    """
    True si a este PDF le corresponde la marca de invalidación.

    `context is None` ⇒ marcar. Es el default seguro: un PDF sin identidad de
    gobernanza no puede demostrar que sale de una versión aprobada, y el error
    caro es el falso negativo (un borrador que pasa por documento válido), no el
    falso positivo (un aprobado marcado de más, que se nota enseguida).
    """
    return context is None or not context.is_approved


def _invalidation_watermark_html() -> str:
    fila = f'<div class="pdf-invalidation-watermark-row">{
        ("&nbsp;" * 6).join([_INVALIDATION_TEXT] * _WATERMARK_COLUMNS)
    }</div>'
    return (
        '<div class="pdf-invalidation-watermark" aria-hidden="true">'
        '<div class="pdf-invalidation-watermark-inner">'
        + fila * _WATERMARK_ROWS
        + "</div></div>"
    )


def _invalidation_notice_html() -> str:
    return (
        '<div class="pdf-invalidation-notice" role="note">'
        f'<p class="pdf-invalidation-notice-title">{_INVALIDATION_TITLE}</p>'
        f'<p class="pdf-invalidation-notice-body">{_INVALIDATION_BODY}</p>'
        "</div>"
    )


@dataclass
class PdfWeasyprintExporter:
    name: str = "pdf_weasyprint"
    base_url: str | None = None
    branding: PdfBranding | None = None
    #: Identidad de gobernanza del documento. En esta fase solo alimenta la
    #: metadata del archivo (/Title, /Author); la portada y el pie con versión
    #: son Fase C y van a leer de acá sin cambiar la firma del exportador.
    document_context: DocumentContext | None = None
    #: Resolutor de recursos. El freeze pasa un StorageAssetFetcher para leer las
    #: imágenes de object storage en vez de bajarlas por HTTP (asset_fetcher.py).
    url_fetcher: object | None = None

    def export_from_html_string(
        self,
        html_content: str,
        output_path: Path,
    ) -> Path:
        try:
            from weasyprint import CSS, HTML
        except ImportError as e:
            raise ImportError(
                "WeasyPrint no esta instalado. Ejecuta: pip install weasyprint"
            ) from e

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        full_html = _wrap_html(html_content, self.branding, self.document_context)

        # La hoja de invalidación se agrega SOLO cuando corresponde. Va aparte y
        # no dentro de _BASE_CSS porque redefine el @bottom-left de @page, que no
        # se puede condicionar desde el HTML.
        # El pie va después de _BASE_CSS porque lleva datos del documento; el de
        # invalidación va último para poder pisarle el color al campo central.
        stylesheets = [_BASE_CSS, _footer_css(self.document_context)]
        if _marks_as_invalid(self.document_context):
            stylesheets.append(_INVALIDATION_CSS)

        try:
            kwargs = {"url_fetcher": self.url_fetcher} if self.url_fetcher else {}
            doc = HTML(string=full_html, base_url=self.base_url, **kwargs)
            doc.write_pdf(
                str(output_path), stylesheets=[CSS(string=s) for s in stylesheets]
            )
        except Exception as e:
            raise RuntimeError(f"WeasyPrint fallo al generar el PDF: {e}") from e

        return output_path

    def export_from_html_file(
        self,
        html_path: Path,
        output_path: Path,
    ) -> Path:
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"No existe el HTML: {html_path}")
        html_content = html_path.read_text(encoding="utf-8")
        return self.export_from_html_string(html_content, output_path)


_BODY_RE = re.compile(r"<body\b[^>]*>(.*)</body\s*>", re.IGNORECASE | re.DOTALL)
_HEAD_RE = re.compile(r"<head\b[^>]*>(.*?)</head\s*>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.IGNORECASE | re.DOTALL)


def _is_full_document(html_content: str) -> bool:
    stripped = html_content.strip().lower()
    return stripped.startswith("<!doctype") or stripped.startswith("<html")


def _split_full_html(html_content: str) -> tuple[str, str]:
    """
    Parte un HTML completo en (estilos del <head>, contenido del <body>).

    Antes, un HTML completo se devolvía tal cual y NUNCA pasaba por el wrapper:
    quedaba sin header de marca, sin logo y —peor— sin el `:root` que definía
    `--pdf-border-color`, así que las tablas salían sin borde. Es el caso de los
    documentos importados.

    Los `<style>` propios del documento se conservan y se re-emiten DESPUÉS de
    los nuestros, para que un documento que trae su propia hoja de estilos siga
    ganando sobre el wrapper.
    """
    head_match = _HEAD_RE.search(html_content)
    own_styles = ""
    if head_match:
        own_styles = "\n".join(_STYLE_RE.findall(head_match.group(1)))

    body_match = _BODY_RE.search(html_content)
    if body_match:
        body_inner = body_match.group(1)
    else:
        # <html> sin <body> explícito: se saca el <head> y se usa el resto.
        body_inner = _HEAD_RE.sub("", html_content)
        body_inner = re.sub(
            r"</?(?:html|!doctype)[^>]*>", "", body_inner, flags=re.IGNORECASE
        )

    return own_styles, body_inner


def _document_meta_tags(context: DocumentContext | None) -> str:
    """
    Metadata del archivo PDF (/Title, /Author) a partir del contexto.

    WeasyPrint la toma del <title> y de <meta name="author">. No tiene efecto
    visual —el PDF impreso no muestra el título del documento HTML—, así que no
    invade la plantilla: es solo lo que se ve en "Propiedades" del visor.
    """
    if context is None:
        return ""

    tags = []
    titulo = " — ".join(
        p for p in (context.code, context.title) if p and str(p).strip()
    )
    if titulo:
        tags.append(f"<title>{html_mod.escape(titulo)}</title>")
    if context.elaborated_by:
        tags.append(f'<meta name="author" content="{html_mod.escape(context.elaborated_by)}">')
    if context.client_name:
        tags.append(
            f'<meta name="dcterms.publisher" content="{html_mod.escape(context.client_name)}">'
        )
    return "\n".join(tags)


def _esc(value) -> str:
    return html_mod.escape(str(value))


def _logo_img_html(branding: PdfBranding | None, css_class: str = "") -> str:
    """
    `<img>` del logo, con la ruta local convertida a URI `file://`.

    Sin el esquema explícito, una ruta absoluta se resolvería contra el base_url
    del render — que durante el freeze es el host centinela de assets — y el
    fetcher la buscaría en object storage, donde no está.
    """
    if not branding or not branding.logo_path:
        return ""
    ruta = str(branding.logo_path)
    if not ruta.startswith(("http://", "https://", "file://", "data:")):
        try:
            ruta = Path(ruta).resolve().as_uri()
        except (OSError, ValueError):
            return ""
    clase = f' class="{css_class}"' if css_class else ""
    return f'<img src="{_esc(ruta)}"{clase} alt="Logo del cliente">'


_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _fecha(valor) -> str | None:
    """Fecha corta (dd/mm/aaaa). Para el cuerpo y el pie."""
    if valor is None:
        return None
    try:
        return valor.strftime("%d/%m/%Y")
    except AttributeError:
        return str(valor)


def _fecha_larga(valor) -> str | None:
    """
    Fecha en letras: "15 de enero de 2028". Solo para el ACTA.

    dd/mm/aaaa es ambiguo para quien lee mm/dd, y este documento puede terminar
    ante un auditor externo o una contraparte de otro país. En el cuerpo y en el
    pie la fecha corta está bien; en el acta, donde el dato es probatorio, no se
    deja lugar a la interpretación.

    Se arma a mano y no con locale: `strftime("%B")` depende del locale del
    proceso, que en un contenedor suele ser C y devolvería "January".
    """
    if valor is None:
        return None
    try:
        return f"{valor.day} de {_MESES[valor.month - 1]} de {valor.year}"
    except (AttributeError, IndexError):
        return str(valor)


def _meses_entre(desde, hasta) -> int | None:
    """
    Meses enteros entre dos fechas, o None si no son un número redondo.

    Sirve para reconstruir la política que se aplicó al aprobar ("24 meses")
    sin guardar un campo más: si la vigencia cae exactamente a N meses de la
    aprobación, hubo una política; si cae en cualquier otro día, la fecha se
    eligió a mano y decir "23 meses" sería inventar una regla que no existió.
    """
    if desde is None or hasta is None:
        return None
    try:
        d = desde.date() if hasattr(desde, "date") else desde
        h = hasta.date() if hasattr(hasta, "date") else hasta
    except AttributeError:
        return None

    meses = (h.year - d.year) * 12 + (h.month - d.month)
    if meses <= 0:
        return None
    # Se verifica sumando: el día tiene que coincidir (o ser el último del mes,
    # como cuando se suma un mes al 31 de enero).
    import calendar

    ultimo = calendar.monthrange(h.year, h.month)[1]
    if h.day == d.day or (h.day == ultimo and d.day > ultimo):
        return meses
    return None


def _firma(nombre: str | None, rol: str | None) -> str | None:
    """
    "Diego Sosa — Encargado de turno".

    El rol importa para gobernanza: el acta registra bajo qué autoridad se
    aprobó, no solo quién lo hizo. Sin rol va solo el nombre, sin guion suelto.
    """
    if not nombre:
        return None
    return f"{nombre} — {rol}" if rol else nombre


def _record_item(label: str, value: str | None) -> str:
    """
    Una entrada del acta. Devuelve "" si no hay dato.

    Omitir es deliberado: una fila "Revisado por: —" afirma que nadie revisó,
    cuando lo cierto es que el sistema no lo sabe. El acta solo dice lo que puede
    sostener.
    """
    if not value:
        return ""
    return (
        '<div class="pdf-cover-record-item">'
        f'<div class="pdf-cover-record-label">{_esc(label)}</div>'
        f'<div class="pdf-cover-record-value">{_esc(value)}</div>'
        "</div>"
    )


def _cover_record_html(context: DocumentContext) -> str:
    """Acta de aprobación (o Responsables, si todavía no hay acta)."""
    aprobado = context.is_approved
    titulo = "Acta de aprobación" if aprobado else "Responsables"

    items = [
        _record_item("Elaborado por", _firma(context.elaborated_by, context.elaborated_by_role)),
        _record_item("Revisado por", _firma(context.reviewed_by, context.reviewed_by_role)),
    ]
    if aprobado:
        items.append(
            _record_item("Aprobado por", _firma(context.approved_by, context.approved_by_role))
        )
        items.append(_record_item("Fecha de aprobación", _fecha_larga(context.approved_at)))
        if context.supersedes_version_number is not None:
            reemplaza = f"Versión {context.supersedes_version_number}"
            fecha_previa = _fecha_larga(context.supersedes_approved_at)
            if fecha_previa:
                reemplaza += f" — aprobada el {fecha_previa}"
            items.append(_record_item("Reemplaza a", reemplaza))

        # "24 meses — hasta el 15 de enero de 2028". La duración comunica que se
        # aplicó una política y no que alguien puso una fecha a dedo.
        vigencia = _fecha_larga(context.validity_until)
        if vigencia:
            meses = _meses_entre(context.approved_at, context.validity_until)
            if meses:
                vigencia = f"{meses} meses — hasta el {vigencia}"
            else:
                vigencia = f"hasta el {vigencia}"
        items.append(_record_item("Vigencia de la aprobación", vigencia))

    cuerpo = "".join(i for i in items if i)
    if not cuerpo:
        return ""
    return (
        '<section class="pdf-cover-record">'
        f'<p class="pdf-cover-record-title">{_esc(titulo)}</p>'
        f'<div class="pdf-cover-record-grid">{cuerpo}</div>'
        "</section>"
    )


def _cover_verify_html(context: DocumentContext) -> str:
    """Bloque de verificación: QR + identificador de la versión."""
    if not context.version_id:
        return ""

    qr_html = ""
    if context.verification_url:
        data_uri = qr_data_uri(context.verification_url)
        if data_uri:
            qr_html = f'<img src="{data_uri}" alt="QR de verificación">'

    return (
        '<footer class="pdf-cover-verify">'
        f"{qr_html}"
        '<div class="pdf-cover-verify-copy">'
        '<p class="pdf-cover-verify-title">Verificación de vigencia</p>'
        '<p class="pdf-cover-verify-body">Esta copia impresa no puede acreditar que el '
        "documento siga vigente. Escaneá el código para comprobar en línea si esta "
        "es la versión en uso.</p>"
        f'<p class="pdf-cover-verify-id">{_esc(context.version_id)}</p>'
        "</div>"
        "</footer>"
    )


def _cover_html(
    branding: PdfBranding | None,
    context: DocumentContext | None,
    notice_html: str,
) -> str:
    """
    Portada del documento.

    Qué NO va acá, y por qué: estado, carpeta y referencia al run son datos
    MUTABLES — cambian sin que cambie el documento. Si se imprimieran, el PDF
    empezaría a mentir apenas alguien mueve el documento de carpeta o aprueba una
    versión posterior. El criterio (ADR-018) es si el dato queda congelado en el
    acto de aprobación. El tipo documental sí queda, y por eso va — pero como
    antetítulo del título, no como fila de una tabla de metadata.

    Se degrada con elegancia: sin código, sin vigencia, sin logo o sin firmas, la
    portada se arma igual con lo que haya.
    """
    if context is None:
        return ""

    cliente = _esc(context.client_name) if context.client_name else ""
    logo = _logo_img_html(branding)

    identidad = ""
    if cliente or logo:
        identidad = (
            '<header class="pdf-cover-client">'
            f"{logo}"
            "<div>"
            + (f'<div class="pdf-cover-client-name">{cliente}</div>' if cliente else "")
            + '<div class="pdf-cover-controlled">Documento controlado</div>'
            "</div>"
            "</header>"
        )

    kicker = (
        f'<p class="pdf-cover-kicker">{_esc(context.document_type_label)}</p>'
        if context.document_type_label
        else ""
    )
    titulo = _esc(context.title) if context.title else "Documento"

    ids = []
    if context.code:
        ids.append(f'<span class="pdf-cover-code">{_esc(context.code)}</span>')
    if context.version_number is not None:
        ids.append(f"Versión {_esc(context.version_number)}")
    ids_html = (
        f'<p class="pdf-cover-ids">{"<span class=\'sep\'>·</span>".join(ids)}</p>'
        if ids
        else ""
    )

    return (
        '<section class="pdf-cover">'
        '<div class="pdf-cover-rule"></div>'
        '<div class="pdf-cover-body">'
        f"{identidad}"
        f"{notice_html}"
        '<div class="pdf-cover-titleblock">'
        f"{kicker}"
        f'<h1 class="pdf-cover-title">{titulo}</h1>'
        f"{ids_html}"
        "</div>"
        f"{_cover_record_html(context)}"
        "</div>"
        f"{_cover_verify_html(context)}"
        "</section>"
    )


def _running_header_html(branding: PdfBranding | None, context: DocumentContext | None) -> str:
    """
    Header corrido: logo + identidad del documento + versión.

    Las clases `.pdf-brand-kicker` y `.pdf-brand-title` existían en el CSS desde
    siempre pero nunca se emitían: el header era solo un logo suelto.
    """
    logo = _logo_img_html(branding)

    kicker = ""
    titulo = ""
    version = ""
    if context:
        if context.document_type_label:
            kicker = f'<div class="pdf-brand-kicker">{_esc(context.document_type_label)}</div>'
        if context.title:
            titulo = f'<div class="pdf-brand-title">{_esc(context.title)}</div>'
        if context.version_number is not None:
            version = f'<div class="pdf-header-version">Versión {_esc(context.version_number)}</div>'

    copy = f'<div class="pdf-brand-copy">{kicker}{titulo}</div>' if (kicker or titulo) else ""

    return (
        '<div class="pdf-page-header">'
        f'<div class="pdf-brand">{logo}{copy}</div>'
        f"{version}"
        "</div>"
    )


def _version_history_html(context: DocumentContext | None) -> str:
    """
    Tabla del historial de versiones aprobadas.

    Solo en documentos aprobados: en un borrador el historial todavía no incluye
    a esta versión, y mostrar el de las anteriores induce a leerlo como si el
    borrador ya fuera parte de la cadena.
    """
    if context is None or not context.is_approved or not context.version_history:
        return ""

    filas = []
    for entrada in context.version_history:
        resumen = (
            _esc(entrada.change_summary)
            if entrada.change_summary
            else '<span class="pdf-vh-sin-datos">Sin detalle registrado</span>'
        )
        filas.append(
            "<tr>"
            f"<td>{_esc(entrada.version_number)}</td>"
            f"<td>{_esc(_fecha(entrada.approved_at) or '')}</td>"
            f"<td>{_esc(entrada.approved_by or '')}</td>"
            f"<td>{resumen}</td>"
            "</tr>"
        )

    return (
        '<section class="pdf-version-history">'
        "<h2>Historial de versiones</h2>"
        "<table><thead><tr>"
        "<th>Versión</th><th>Aprobada el</th><th>Aprobada por</th>"
        "<th>Cambios principales</th>"
        "</tr></thead>"
        f"<tbody>{''.join(filas)}</tbody></table>"
        "</section>"
    )


def _wrap_html(
    html_content: str,
    branding: PdfBranding | None = None,
    document_context: DocumentContext | None = None,
) -> str:
    """Envuelve SIEMPRE: un documento ya completo se desarma y se re-arma."""
    own_styles = ""
    if _is_full_document(html_content):
        own_styles, html_content = _split_full_html(html_content)

    meta_tags = _document_meta_tags(document_context)

    # La marca de agua va fuera del flujo (position: fixed) y se ancla a la
    # página. El bloque de invalidación ahora vive en la PORTADA: es lo primero
    # que se ve, junto a la identidad del documento que está invalidando.
    watermark_html = ""
    notice_html = ""
    if _marks_as_invalid(document_context):
        watermark_html = _invalidation_watermark_html()
        notice_html = _invalidation_notice_html()

    # Índice: se derivan de los h2 del contenido y se les inyecta el ancla. Va
    # antes del historial, que a su vez va antes del cuerpo.
    toc = ""
    if document_context is not None and document_context.show_toc:
        html_content, entradas = add_heading_anchors(html_content)
        toc = toc_html(entradas)

    historial = _version_history_html(document_context)

    cover_html = _cover_html(branding, document_context, notice_html)
    # Sin portada (sin contexto) el aviso vuelve al cuerpo, para que un PDF
    # invalidado nunca se quede sin él.
    inline_notice = "" if cover_html else notice_html

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{meta_tags}
<style>
{root_variables_css(branding)}
</style>
{own_styles}
</head>
<body>
{watermark_html}
{cover_html}
{_running_header_html(branding, document_context)}
<main class="pdf-content">
{inline_notice}
{toc}
{historial}
{html_content}
</main>
</body>
</html>"""
