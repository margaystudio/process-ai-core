# process_ai_core/pdf_pandoc.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

"""
process_ai_core.pdf_pandoc
==========================

Exportador de Markdown a PDF usando Pandoc + XeLaTeX.

Este módulo encapsula la llamada a `pandoc` para generar un PDF a partir de un
archivo Markdown, cuidando algunos detalles típicos en pipelines de documentación:

- **Resolución de rutas relativas** (por ejemplo `assets/...`): se ejecuta Pandoc
  con `cwd=run_dir` para que las rutas se resuelvan contra la carpeta de salida.
- **Header LaTeX regenerado**: se escribe siempre `pandoc_header.tex` para evitar
  usar un header viejo o incompleto.
- **Errores explicativos**: diferencia entre "pandoc no está instalado" y
  "pandoc falló al compilar" (con STDOUT/STDERR).

Requisitos
----------
- Pandoc instalado y en PATH:
  - macOS: `brew install pandoc`
- Un engine LaTeX disponible:
  - `xelatex` (provisto por MacTeX o TeX Live)

Notas sobre imágenes
--------------------
- Para que imágenes Markdown como `![caption](assets/img.png)` funcionen, Pandoc
  debe poder encontrar `assets/` desde el directorio de trabajo.
- Por eso el `cwd` se fija en `run_dir` (normalmente `output/`).

"""

# Header LaTeX compartido: imágenes, colores, tipografía y espaciado
_PANDOC_HEADER_TEX = r"""
\usepackage{graphicx}
\usepackage{float}
\usepackage{xcolor}
\graphicspath{{./}}
\setkeys{Gin}{width=0.9\textwidth,height=0.9\textheight,keepaspectratio}
\usepackage{placeins}
\FloatBarrier
% Mejorar legibilidad: espaciado entre párrafos y listas
\usepackage{parskip}
\usepackage{enumitem}
\setlist{leftmargin=*, itemsep=0.25em}
% Títulos más claros
\usepackage{titlesec}
\titleformat{\section}{\normalfont\Large\bfseries}{\thesection}{1em}{}
\titleformat{\subsection}{\normalfont\large\bfseries}{\thesubsection}{1em}{}
"""


@dataclass
class PdfPandocExporter:
    """
    Exportador PDF basado en Pandoc.

    Attributes
    ----------
    name:
        Identificador del exportador. Útil si más adelante querés soportar
        múltiples exporters (pandoc, weasyprint, etc.).
    """

    name: str = "pdf_pandoc"

    def export(self, run_dir: Path, md_path: Path, pdf_name: str = "documento.pdf") -> Path:
        """
        Genera un PDF desde un Markdown usando Pandoc.

        Parameters
        ----------
        run_dir:
            Directorio de ejecución/salida. Se usa para:
            - escribir el PDF resultante
            - escribir el header LaTeX (`pandoc_header.tex`)
            - establecer el `cwd` de Pandoc (para resolver rutas relativas)
        md_path:
            Ruta al archivo Markdown a convertir.
            Puede estar dentro o fuera de `run_dir`, pero Pandoc se invoca con
            el nombre del archivo (`md_path.name`) asumiendo que el Markdown está
            accesible desde `run_dir`. En el flujo típico, el Markdown vive en
            `run_dir`.
        pdf_name:
            Nombre del PDF a generar dentro de `run_dir`.

        Returns
        -------
        Path
            Ruta absoluta (o relativa según se use) al PDF generado.

        Raises
        ------
        FileNotFoundError
            Si `md_path` no existe.
        RuntimeError
            Si Pandoc no está disponible en PATH o si falla la conversión.

        Implementation details
        ----------------------
        - Regenera siempre un header LaTeX mínimo con `graphicx` y `float`
          para soportar imágenes y figuras no flotantes si el markdown incluye raw_tex.
        - Usa `--from=markdown+raw_tex` para permitir bloques LaTeX embebidos.
        - Usa `--pdf-engine=xelatex` por compatibilidad con Unicode/fuentes.
        """

        run_dir = Path(run_dir)
        md_path = Path(md_path)

        if not md_path.exists():
            raise FileNotFoundError(f"No existe el markdown: {md_path}")

        out_pdf = run_dir / pdf_name
        header_tex = run_dir / "pandoc_header.tex"
        header_tex.write_text(_PANDOC_HEADER_TEX, encoding="utf-8")

        # Variables para mejor tipografía y márgenes
        cmd = [
            "pandoc",
            str(md_path.name),
            "-o",
            str(out_pdf.name),
            "--standalone",
            "--from=markdown+raw_tex",
            "--pdf-engine=xelatex",
            "--include-in-header",
            str(header_tex.name),
            "-V", "fontsize=11pt",
            "-V", "geometry:margin=2.5cm",
            "-V", "papersize=a4",
            "-V", "colorlinks=true",
            "--wrap=none",
            "--resource-path=.",
        ]

        # ✅ DEBUG (útil mientras estabilizás el pipeline)
        print("🚀 Pandoc cmd:", " ".join(cmd))
        print("📁 Pandoc cwd:", str(run_dir.resolve()))

        try:
            subprocess.run(
                cmd,
                cwd=str(run_dir),
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            # Este error suele ser porque `pandoc` no está instalado o no está en PATH.
            raise RuntimeError(
                "No se encontró 'pandoc' en el PATH. Instalalo (brew install pandoc) y reintentá."
            ) from e
        except subprocess.CalledProcessError as e:
            # Pandoc encontró un error al convertir (markdown inválido, latex no instalado, imágenes faltantes, etc.)
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            msg = "Falló pandoc al generar el PDF."
            if stderr:
                msg += f"\nSTDERR:\n{stderr}"
            if stdout:
                msg += f"\nSTDOUT:\n{stdout}"
            raise RuntimeError(msg) from e

        return out_pdf

    def export_from_html(
        self, run_dir: Path, html_path: Path, pdf_name: str = "documento.pdf"
    ) -> Path:
        """
        Genera un PDF desde un archivo HTML usando Pandoc.

        Mismo header LaTeX y cwd que export() para consistencia.
        Usa --from=html para que Pandoc tome el HTML como entrada.
        """
        run_dir = Path(run_dir)
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"No existe el HTML: {html_path}")
        out_pdf = run_dir / pdf_name
        header_tex = run_dir / "pandoc_header.tex"
        header_tex.write_text(_PANDOC_HEADER_TEX, encoding="utf-8")
        cmd = [
            "pandoc",
            str(html_path.name),
            "-o",
            str(out_pdf.name),
            "--standalone",
            "--from=html",
            "--pdf-engine=xelatex",
            "--include-in-header",
            str(header_tex.name),
            "-V", "fontsize=11pt",
            "-V", "geometry:margin=2.5cm",
            "-V", "papersize=a4",
            "-V", "colorlinks=true",
            "--wrap=none",
            "--resource-path=.",
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
            msg = "Falló pandoc al generar el PDF desde HTML."
            if stderr:
                msg += f"\nSTDERR:\n{stderr}"
            if stdout:
                msg += f"\nSTDOUT:\n{stdout}"
            raise RuntimeError(msg) from e
        return out_pdf