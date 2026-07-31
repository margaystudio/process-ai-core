"""
Reproducibilidad del render de PDF.

El PDF de una versión aprobada es un artefacto de auditoría: sus bytes viven en
object storage y su SHA-256 queda persistido en `document_versions.pdf_sha256`.
Ese hash solo sirve como huella si el mismo contenido produce SIEMPRE los mismos
bytes — si el motor embebe la fecha de creación, el hash cambia por segundo.

Estos tests son la regresión que protege esa propiedad, y siguen siendo válidos
cuando cambie la plantilla del PDF: no afirman NADA sobre el contenido visual,
solo que dos renders del mismo input son idénticos.

Ver `process_ai_core.config.apply_reproducible_render_env`.
"""

import hashlib
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from process_ai_core.config import PDF_SOURCE_DATE_EPOCH, apply_reproducible_render_env
from process_ai_core.export import export_pdf_from_content

# Contenido con tabla, listas, énfasis y cita: fuerza subsetting de varias
# fuentes, que es donde un motor no determinístico suele delatarse.
HTML = """<h1>Procedimiento de recepción de combustible</h1>
<p>Contenido con <b>negrita</b>, <i>itálica</i> y <code>código</code>.</p>
<table>
  <tr><th>Paso</th><th>Responsable</th></tr>
  <tr><td>Medir varillado</td><td>Playero</td></tr>
  <tr><td>Registrar en planilla</td><td>Encargado de turno</td></tr>
</table>
<ul><li>Verificar precinto</li><li>Contrastar remito</li></ul>
<blockquote>Cita larga para forzar más glifos y subsetting de fuentes.</blockquote>"""

MARKDOWN = """# Procedimiento de recepción de combustible

Contenido con **negrita** e *itálica*.

- Verificar precinto
- Contrastar remito
"""

# Pausa real entre renders: la no-determinación por fecha se manifiesta al
# cruzar un segundo de reloj, así que un sleep corto no probaría nada.
PAUSA_SEGUNDOS = 2.2


def _render(content: str, fmt: str) -> bytes:
    tmp = Path(tempfile.mkdtemp())
    try:
        pdf = export_pdf_from_content(
            content=content, format=fmt, run_dir=tmp, pdf_name="salida.pdf"
        )
        return Path(pdf).read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _render_dos_veces(content: str, fmt: str) -> tuple[bytes, bytes]:
    primero = _render(content, fmt)
    time.sleep(PAUSA_SEGUNDOS)
    segundo = _render(content, fmt)
    return primero, segundo


def test_weasyprint_rinde_los_mismos_bytes_en_distinto_segundo():
    """Camino de producción (HTML → WeasyPrint)."""
    a, b = _render_dos_veces(HTML, "html")

    assert a[:5] == b"%PDF-"
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), (
        "Dos renders del mismo HTML dieron bytes distintos: el pdf_sha256 "
        "persistido dejaría de identificar al blob guardado en storage."
    )
    assert a == b


def test_markdown_rinde_los_mismos_bytes_en_distinto_segundo():
    """
    Camino de Markdown. Ya no requiere pandoc ni un motor LaTeX: desde Fase B el
    markdown se convierte a HTML y sale por WeasyPrint como todo lo demás.
    """
    a, b = _render_dos_veces(MARKDOWN, "markdown")

    assert a[:5] == b"%PDF-"
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), (
        "Dos renders del mismo Markdown dieron bytes distintos: revisá que "
        "apply_reproducible_render_env() siga corriendo antes del render."
    )


def test_export_aplica_el_entorno_reproducible_sin_depender_del_arranque():
    """
    Un script de tools/ o un worker que renderice sin pasar por el startup de la
    API tiene que producir los MISMOS bytes que la API. Por eso la aplica también
    `export_pdf_from_content`.
    """
    import os

    os.environ.pop("SOURCE_DATE_EPOCH", None)
    _render(HTML, "html")
    assert os.environ.get("SOURCE_DATE_EPOCH") == PDF_SOURCE_DATE_EPOCH


def test_el_epoch_es_constante_y_no_deriva_de_la_fecha_actual():
    """
    Guardarraíl contra "arreglar" la fecha poniendo la real: si el valor pasa a
    depender del reloj o de la versión, se rompe todo lo anterior.
    """
    import os

    apply_reproducible_render_env()
    primero = os.environ["SOURCE_DATE_EPOCH"]
    time.sleep(1.2)
    apply_reproducible_render_env()

    assert os.environ["SOURCE_DATE_EPOCH"] == primero == PDF_SOURCE_DATE_EPOCH
    assert PDF_SOURCE_DATE_EPOCH.isdigit()


def test_sobrescribe_un_source_date_epoch_externo():
    """
    Algunos CI exportan SOURCE_DATE_EPOCH con el timestamp del build: eso haría
    que un PDF recongelado después de un deploy no coincidiera con el anterior.
    """
    import os

    os.environ["SOURCE_DATE_EPOCH"] = "1234567890"
    apply_reproducible_render_env()
    assert os.environ["SOURCE_DATE_EPOCH"] == PDF_SOURCE_DATE_EPOCH
