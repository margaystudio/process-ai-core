from __future__ import annotations

from pathlib import Path
from typing import Literal

from .content_source import get_export_content
from .pdf_pandoc import PdfPandocExporter
from .pdf_weasyprint import PdfWeasyprintExporter


def export_pdf(run_dir: Path, md_path: Path, pdf_name: str = "documento.pdf") -> Path:
    """Genera PDF desde un archivo Markdown (flujo existente de runs)."""
    exporter = PdfPandocExporter()
    return exporter.export(run_dir=run_dir, md_path=md_path, pdf_name=pdf_name)


def export_pdf_from_content(
    content: str,
    format: Literal["html", "markdown"],
    run_dir: Path,
    pdf_name: str = "documento.pdf",
    base_url: str | None = None,
) -> Path:
    """
    Genera PDF desde contenido en memoria (HTML o Markdown).

    - HTML → WeasyPrint: renderiza tablas e imágenes como un browser,
      preservando el layout del editor Tiptap.
    - Markdown → Pandoc + XeLaTeX: flujo original para documentos generados por IA.

    Args:
        content: String con el contenido a exportar.
        format: "html" o "markdown".
        run_dir: Directorio donde se escribirá el PDF (y archivos temporales).
        pdf_name: Nombre del archivo PDF de salida.
        base_url: URL base para resolver imágenes remotas en WeasyPrint
                  (ej. "http://localhost:8000"). Opcional.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    if format == "html":
        # WeasyPrint: fidelidad visual total (tablas, imágenes, CSS)
        exporter = PdfWeasyprintExporter(base_url=base_url)
        output_path = run_dir / pdf_name
        return exporter.export_from_html_string(
            html_content=content,
            output_path=output_path,
        )
    else:
        # Pandoc + XeLaTeX: pipeline original para Markdown
        md_path = run_dir / "content.md"
        md_path.write_text(content, encoding="utf-8")
        exporter = PdfPandocExporter()
        return exporter.export(run_dir=run_dir, md_path=md_path, pdf_name=pdf_name)