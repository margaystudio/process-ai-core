from __future__ import annotations

from pathlib import Path
from typing import Literal

from .content_source import get_export_content
from .pdf_pandoc import PdfPandocExporter


def export_pdf(run_dir: Path, md_path: Path, pdf_name: str = "documento.pdf") -> Path:
    """Genera PDF desde un archivo Markdown (flujo existente de runs)."""
    exporter = PdfPandocExporter()
    return exporter.export(run_dir=run_dir, md_path=md_path, pdf_name=pdf_name)


def export_pdf_from_content(
    content: str,
    format: Literal["html", "markdown"],
    run_dir: Path,
    pdf_name: str = "documento.pdf",
) -> Path:
    """
    Genera PDF desde contenido en memoria (HTML o Markdown).
    Escribe el contenido en run_dir y llama al exportador correspondiente.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    exporter = PdfPandocExporter()
    if format == "html":
        html_path = run_dir / "content.html"
        html_path.write_text(content, encoding="utf-8")
        return exporter.export_from_html(
            run_dir=run_dir, html_path=html_path, pdf_name=pdf_name
        )
    else:
        md_path = run_dir / "content.md"
        md_path.write_text(content, encoding="utf-8")
        return exporter.export(run_dir=run_dir, md_path=md_path, pdf_name=pdf_name)