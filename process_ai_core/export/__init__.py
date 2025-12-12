from __future__ import annotations

from pathlib import Path
from typing import Optional

from .pdf_pandoc import PdfPandocExporter


def export_pdf(run_dir: Path, md_path: Path, pdf_name: str = "documento.pdf") -> Path:
    exporter = PdfPandocExporter()
    return exporter.export(run_dir=run_dir, md_path=md_path, pdf_name=pdf_name)