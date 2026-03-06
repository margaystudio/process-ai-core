# process_ai_core/pdf_pandoc.py
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys

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
- Pandoc instalado (en PATH o en rutas típicas de Windows):
  - macOS: `brew install pandoc`
  - Windows: `winget install -e --id JohnMacFarlane.Pandoc`
- Un motor PDF (se usa el primero disponible):
  - xelatex: mejor calidad (MacTeX, TeX Live, MiKTeX)
  - wkhtmltopdf: ligero, sin LaTeX (winget install wkhtmltopdf.wkhtmltox)

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


def _find_pandoc() -> str:
    """
    Devuelve la ruta al ejecutable pandoc.
    En Windows, si no está en PATH, busca en rutas de instalación típicas.
    """
    exe = shutil.which("pandoc")
    if exe:
        return exe
    if sys.platform == "win32":
        # Rutas típicas cuando pandoc se instala con winget o el MSI
        candidates = [
            Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe",
            Path(r"C:\Program Files\Pandoc\pandoc.exe"),
            Path(r"C:\Program Files (x86)\Pandoc\pandoc.exe"),
        ]
        for p in candidates:
            if p.exists():
                return str(p)
    raise FileNotFoundError("pandoc")


def _find_wkhtmltopdf() -> str | None:
    """
    Ruta a wkhtmltopdf si está disponible.
    En Windows busca en rutas típicas (el servidor puede no tener PATH actualizado).
    """
    exe = shutil.which("wkhtmltopdf")
    if exe:
        return exe
    if sys.platform == "win32":
        for p in [
            Path(r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"),
            Path(r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe"),
        ]:
            if p.exists():
                return str(p)
    return None


def _get_pdf_engine() -> str:
    """
    Devuelve el motor PDF disponible para Pandoc.
    Orden: xelatex (mejor calidad) → wkhtmltopdf (ligero, sin LaTeX).
    Puede devolver ruta absoluta a wkhtmltopdf en Windows.
    """
    if shutil.which("xelatex"):
        return "xelatex"
    wk = _find_wkhtmltopdf()
    if wk:
        return wk
    # Mensaje según plataforma
    if sys.platform == "win32":
        tip = (
            "Instalá wkhtmltopdf (ligero): winget install wkhtmltopdf.wkhtmltox\n"
            "O LaTeX completo: winget install MiKTeX.MiKTeX"
        )
    else:
        tip = "brew install --cask mactex  # o: brew install wkhtmltopdf"
    raise RuntimeError(
        f"No hay motor PDF disponible (xelatex ni wkhtmltopdf).\n{tip}"
    )


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

        run_dir = Path(run_dir).resolve()
        md_path = Path(md_path)

        if not md_path.exists():
            raise FileNotFoundError(f"No existe el markdown: {md_path}")

        out_pdf = (run_dir / pdf_name).resolve()

        try:
            pandoc_exe = _find_pandoc()
            engine = _get_pdf_engine()
            out_arg = str(out_pdf.as_posix()) if sys.platform == "win32" else str(out_pdf)
            cmd = [
                pandoc_exe,
                str(md_path.name),
                "-o",
                out_arg,
                "--standalone",
                "--from=markdown+raw_tex",
                "--pdf-engine=" + engine,
                "--wrap=none",
                "--resource-path=.",
            ]
            if engine == "xelatex":
                header_tex = run_dir / "pandoc_header.tex"
                header_tex.write_text(_PANDOC_HEADER_TEX, encoding="utf-8")
                cmd.extend([
                    "--include-in-header", str(header_tex.name),
                    "-V", "fontsize=11pt",
                    "-V", "geometry:margin=2.5cm",
                    "-V", "papersize=a4",
                    "-V", "colorlinks=true",
                ])
            # ✅ DEBUG (útil mientras estabilizás el pipeline)
            print("🚀 Pandoc cmd:", " ".join(cmd))
            print("📁 Pandoc cwd:", str(run_dir.resolve()))
            result = subprocess.run(
                cmd,
                cwd=str(run_dir.resolve()),
                check=True,
                capture_output=True,
                text=True,
            )
            for _ in range(5):
                if out_pdf.exists():
                    break
                time.sleep(0.2)
            if not out_pdf.exists():
                stderr = (result.stderr or "").strip()
                raise RuntimeError(
                    f"Pandoc terminó pero no creó {out_pdf}. Engine={engine}. STDERR: {stderr[:500] or '(vacío)'}"
                )
        except FileNotFoundError as e:
            # Este error suele ser porque `pandoc` no está instalado o no está en PATH.
            tip = "winget install -e --id JohnMacFarlane.Pandoc" if sys.platform == "win32" else "brew install pandoc"
            raise RuntimeError(
                f"No se encontró 'pandoc'. Instalalo ({tip}) y reintentá."
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
        run_dir = Path(run_dir).resolve()
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"No existe el HTML: {html_path}")
        out_pdf = (run_dir / pdf_name).resolve()

        try:
            pandoc_exe = _find_pandoc()
            engine = _get_pdf_engine()
            out_arg = str(out_pdf.as_posix()) if sys.platform == "win32" else str(out_pdf)
            cmd = [
                pandoc_exe,
                str(html_path.name),
                "-o",
                out_arg,
                "--standalone",
                "--from=html",
                "--pdf-engine=" + engine,
                "--wrap=none",
                "--resource-path=.",
            ]
            if engine == "xelatex":
                header_tex = run_dir / "pandoc_header.tex"
                header_tex.write_text(_PANDOC_HEADER_TEX, encoding="utf-8")
                cmd.extend([
                    "--include-in-header", str(header_tex.name),
                    "-V", "fontsize=11pt",
                    "-V", "geometry:margin=2.5cm",
                    "-V", "papersize=a4",
                    "-V", "colorlinks=true",
                ])
            result = subprocess.run(
                cmd,
                cwd=str(run_dir.resolve()),
                check=True,
                capture_output=True,
                text=True,
            )
            for _ in range(5):
                if out_pdf.exists():
                    break
                time.sleep(0.2)
            if not out_pdf.exists():
                stderr = (result.stderr or "").strip()
                raise RuntimeError(
                    f"Pandoc terminó pero no creó {out_pdf}. Engine={engine}. STDERR: {stderr[:500] or '(vacío)'}"
                )
        except FileNotFoundError as e:
            tip = "winget install -e --id JohnMacFarlane.Pandoc" if sys.platform == "win32" else "brew install pandoc"
            raise RuntimeError(
                f"No se encontró 'pandoc'. Instalalo ({tip}) y reintentá."
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