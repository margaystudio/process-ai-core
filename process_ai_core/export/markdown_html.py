"""
Conversión Markdown → HTML: la puerta de entrada del único motor de render.

Por qué vive en el core y no en `api/`
--------------------------------------
Esta función dejó de ser un detalle de presentación del editor: ahora es el
primer paso de TODO PDF que sale del sistema, incluido el artefacto de auditoría.
Si viviera en `api/routes/documents/_helpers.py`, `process_ai_core.export`
tendría que importar de `api/` — el core dependiendo de la capa HTTP, y con eso
la CLI y los scripts de `tools/` quedarían fuera del contrato.

`api/routes/documents/_helpers.py` ahora delega acá, así que el HTML que se
precarga en el editor y el que se imprime en el PDF salen de la misma función
con las mismas extensiones. Que difirieran sería una divergencia silenciosa
entre lo que el usuario revisa y lo que se congela.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

#: Extensiones de `markdown`. Son parte del contrato del artefacto: cambiarlas
#: cambia el HTML y, por lo tanto, el PDF. No tocar sin entender que afecta el
#: aspecto de todo documento generado a partir de ese momento.
MARKDOWN_EXTENSIONS = ["extra", "nl2br", "tables", "sane_lists"]

_LATEX_ARTIFACT_RE = re.compile(
    r"\\(?:FloatBarrier|clearpage|newpage|pagebreak|vspace\{[^}]*\}|hspace\{[^}]*\}"
    r"|noindent|medskip|bigskip|smallskip)",
    re.IGNORECASE,
)


def strip_latex_artifacts(text: str) -> str:
    """
    Elimina comandos LaTeX que no tienen equivalente HTML.

    Quedaron en el markdown de documentos generados cuando la salida pasaba por
    Pandoc + LaTeX. Sin este filtro se imprimirían como texto literal.
    """
    return _LATEX_ARTIFACT_RE.sub("", text or "")


def markdown_to_html(md: str) -> str:
    """
    Convierte Markdown a HTML para renderizar el PDF.

    Lanza si la librería `markdown` no está disponible: es una dependencia dura
    declarada en pyproject.toml y el único camino de salida pasa por acá. Antes
    había un fallback que envolvía cada línea en `<p>` escapado; para el editor
    eso era una degradación tolerable, pero para el artefacto de auditoría
    significaría congelar un PDF ilegible sin que nadie se entere. Que falle
    ruidoso es lo correcto: el freeze loggea el error y la versión queda sin PDF,
    que es un estado detectable y reintentable.
    """
    import markdown as markdown_lib

    from process_ai_core.html_sanitize import sanitize_document_html

    html = markdown_lib.markdown(
        strip_latex_artifacts(md or ""), extensions=MARKDOWN_EXTENSIONS
    )
    # `markdown` deja pasar el HTML crudo que venga embebido en el markdown, y
    # ese markdown sale de la generación por IA sobre evidencia del usuario. Sin
    # este saneo, un `<img onerror=…>` escondido en una transcripción termina
    # persistido en `content_html` y ejecutándose en la pantalla del aprobador.
    return sanitize_document_html(html)


def render_frozen_html(md: str | None) -> str | None:
    """
    HTML a persistir en `DocumentVersion.content_html` al crear/actualizar una versión.

    Por qué se persiste y no se deriva al imprimir
    ----------------------------------------------
    Si el HTML se derivara en tiempo de render, el PDF congelado dependería de la
    versión de la librería `markdown` instalada en ese momento: una entrada
    invisible al SHA-256, igual que lo eran la versión del motor y el set de
    fuentes. Persistiéndolo, la entrada del render queda congelada junto con el
    resto y el hash vuelve a identificar algo reproducible.

    Esto NO contradice ADR-012 ("Markdown como formato portable"): el markdown
    sigue siendo lo que se almacena como fuente y lo que se exporta a Notion o
    GitHub. El HTML es la representación congelada de lo que efectivamente se
    imprimió — un artefacto derivado más, como el propio PDF.

    Best-effort a propósito: si la conversión falla, devuelve None y la versión
    se crea igual. `get_export_content` convierte como red al imprimir, así que
    el peor caso es volver al comportamiento anterior, no perder la versión.
    """
    if md is None or not str(md).strip():
        return None
    try:
        return markdown_to_html(str(md))
    except Exception as exc:
        logger.warning(
            "No se pudo pre-renderizar content_html desde markdown: %s. "
            "La versión se guarda sin HTML congelado.", exc,
        )
        return None
