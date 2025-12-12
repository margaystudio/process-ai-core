from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


@dataclass
class PdfPandocExporter:
    """
    Exporta Markdown a PDF con Pandoc.
    Asume que las imágenes están referenciadas como assets/<archivo>
    y que el PDF se genera dentro del mismo run_dir.
    """
    name: str = "pdf_pandoc"

    def export(self, run_dir: Path, md_path: Path, pdf_name: str = "documento.pdf") -> Path:
        run_dir = Path(run_dir)
        md_path = Path(md_path)

        if not md_path.exists():
            raise FileNotFoundError(f"No existe el markdown: {md_path}")

        out_pdf = run_dir / pdf_name

        # Importante: correr pandoc con cwd=run_dir para que resuelva assets/...
        cmd = [
            "pandoc",
            str(md_path.name),
            "-o",
            str(out_pdf.name),
            "--pdf-engine=xelatex",
        ]

        try:
            subprocess.run(
                cmd,
                cwd=str(run_dir),
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "No se encontró 'pandoc' en el PATH. Instalalo (brew install pandoc) y reintentá."
            ) from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            msg = "Falló pandoc al generar el PDF."
            if stderr:
                msg += f"\nSTDERR:\n{stderr}"
            if stdout:
                msg += f"\nSTDOUT:\n{stdout}"
            raise RuntimeError(msg) from e

        return out_pdf