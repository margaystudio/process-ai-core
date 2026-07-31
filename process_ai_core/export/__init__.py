"""
Exportación a PDF. **Un solo motor de salida: WeasyPrint.**

Por qué un solo motor
---------------------
Antes había dos: HTML → WeasyPrint y Markdown → Pandoc + LaTeX. El camino
Markdown era el DEFAULT del producto (el pipeline crea versiones solo con
`content_markdown`), y la imagen de producción tiene `pandoc` pero ningún motor
PDF — ni xelatex ni wkhtmltopdf. Resultado: generar → revisar → aprobar sin
pasar por el editor manual dejaba la versión APPROVED sin PDF congelado, en
silencio, porque el freeze es best-effort.

Se descartó instalar LaTeX. Habría tapado el síntoma y consolidado el problema:
la portada, la marca de agua, el header corrido y el pie se construyen en CSS.
Sostener el camino LaTeX obligaría a reimplementar todo eso en un preámbulo y a
mantener dos plantillas que divergen — con lo cual el artefacto de auditoría se
vería distinto según por dónde pasó. Esa divergencia es justamente lo que este
trabajo elimina.

Ahora el Markdown se convierte a HTML antes de exportar (`markdown_html.py`) y
todo termina en WeasyPrint. Pandoc ya no participa de ninguna salida.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..config import apply_reproducible_render_env
from .asset_fetcher import ASSET_BASE_URL, StorageAssetFetcher
from .branding import PdfBranding
from .content_source import get_export_content
from .document_context import DocumentContext
from .integrity import IncompletePdfError, verify_pdf_images
from .markdown_html import markdown_to_html, strip_latex_artifacts
from .pdf_weasyprint import PdfWeasyprintExporter

__all__ = [
    "PdfBranding",
    "DocumentContext",
    "ASSET_BASE_URL",
    "StorageAssetFetcher",
    "IncompletePdfError",
    "verify_pdf_images",
    "get_export_content",
    "markdown_to_html",
    "strip_latex_artifacts",
    "export_pdf",
    "export_pdf_from_content",
]


def export_pdf(
    run_dir: Path,
    md_path: Path,
    pdf_name: str = "documento.pdf",
    branding: PdfBranding | None = None,
    document_context: DocumentContext | None = None,
) -> Path:
    """
    Genera PDF desde un archivo Markdown (artefacto `process.pdf` de un run).

    Mantiene la firma de siempre para no tocar sus ~6 call-sites, pero ya no usa
    Pandoc: convierte a HTML y delega en WeasyPrint. Efecto lateral querido —
    estos PDFs de run tampoco se generaban en producción por la falta de motor
    LaTeX, y ahora sí.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"No existe el markdown: {md_path}")

    # base_url = el directorio del run. El markdown del pipeline trae imágenes
    # relativas (`assets/step_1/...`) que existen ahí como archivos: Pandoc las
    # resolvía con `--resource-path=.` y WeasyPrint las resuelve con base_url.
    # Sin esto el PDF del run saldría sin las capturas de los pasos.
    return export_pdf_from_content(
        content=md_path.read_text(encoding="utf-8"),
        format="markdown",
        run_dir=run_dir,
        pdf_name=pdf_name,
        base_url=Path(run_dir).resolve().as_uri() + "/",
        branding=branding,
        document_context=document_context,
    )


def export_pdf_from_content(
    content: str,
    format: Literal["html", "markdown"],
    run_dir: Path,
    pdf_name: str = "documento.pdf",
    base_url: str | None = None,
    branding: PdfBranding | None = None,
    document_context: DocumentContext | None = None,
    url_fetcher=None,
) -> Path:
    """
    Genera PDF desde contenido en memoria.

    `format="markdown"` se normaliza a HTML acá y sigue por el mismo camino que
    el HTML nativo: un solo motor, una sola plantilla, un solo aspecto.

    Args:
        content: String con el contenido a exportar.
        format: "html" o "markdown". El markdown se convierte antes de renderizar.
        run_dir: Directorio donde se escribirá el PDF (y archivos temporales).
        pdf_name: Nombre del archivo PDF de salida.
        base_url: URL base para resolver imágenes remotas (ej. "http://localhost:8000").
                  Se aplica también al markdown convertido, que puede traer
                  imágenes relativas del run.
        document_context: Identidad de gobernanza del documento (versión, firmas,
                  tipo documental). Opcional.
        url_fetcher: Resolutor de recursos de WeasyPrint. El freeze pasa un
                  StorageAssetFetcher para leer las imágenes de object storage en
                  vez de bajarlas por HTTP. Ver asset_fetcher.py.
    """
    apply_reproducible_render_env()
    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    html = content if format == "html" else markdown_to_html(content)

    exporter = PdfWeasyprintExporter(
        base_url=base_url,
        branding=branding,
        document_context=document_context,
        url_fetcher=url_fetcher,
    )
    result = exporter.export_from_html_string(
        html_content=html,
        output_path=run_dir / pdf_name,
    )
    return result.resolve()
