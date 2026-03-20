from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .branding import PdfBranding


def _find_pandoc() -> str:
    exe = shutil.which("pandoc")
    if exe:
        return exe
    if sys.platform == "win32":
        candidates = [
            Path.home() / "AppData" / "Local" / "Pandoc" / "pandoc.exe",
            Path(r"C:\Program Files\Pandoc\pandoc.exe"),
            Path(r"C:\Program Files (x86)\Pandoc\pandoc.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    raise FileNotFoundError("pandoc")


def _find_wkhtmltopdf() -> str | None:
    exe = shutil.which("wkhtmltopdf")
    if exe:
        return exe
    if sys.platform == "win32":
        for candidate in [
            Path(r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"),
            Path(r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe"),
        ]:
            if candidate.exists():
                return str(candidate)
    return None


def _get_pdf_engine() -> str:
    if shutil.which("xelatex"):
        return "xelatex"
    wkhtml = _find_wkhtmltopdf()
    if wkhtml:
        return wkhtml
    if sys.platform == "win32":
        tip = (
            "Instala wkhtmltopdf: winget install wkhtmltopdf.wkhtmltox\n"
            "O un motor LaTeX: winget install MiKTeX.MiKTeX"
        )
    else:
        tip = "Instala un motor PDF: xelatex o wkhtmltopdf"
    raise RuntimeError(f"No hay motor PDF disponible.\n{tip}")


def _build_header_tex(branding: PdfBranding | None) -> str:
    logo_block = ""
    if branding and branding.logo_path:
        logo_path = branding.logo_path.replace("\\", "/")
        logo_block = r"\includegraphics[height=1.0cm]{" + logo_path + "}"

    return rf"""
\usepackage{{graphicx}}
\usepackage{{float}}
\usepackage{{xcolor}}
\usepackage{{placeins}}
\usepackage{{parskip}}
\usepackage{{enumitem}}
\usepackage{{titlesec}}
\usepackage{{fancyhdr}}
\usepackage{{helvet}}
\renewcommand{{\familydefault}}{{\sfdefault}}
\graphicspath{{{{./}}}}
\setkeys{{Gin}}{{width=0.9\textwidth,height=0.9\textheight,keepaspectratio}}
\setlist{{leftmargin=*, itemsep=0.3em, topsep=0.4em}}
\titleformat{{\section}}{{\normalfont\Large\bfseries}}{{\thesection}}{{0.75em}}{{}}
\titleformat{{\subsection}}{{\normalfont\large\bfseries}}{{\thesubsection}}{{0.75em}}{{}}
\titleformat{{\subsubsection}}{{\normalfont\normalsize\bfseries}}{{\thesubsubsection}}{{0.75em}}{{}}
\pagestyle{{fancy}}
\fancyhf{{}}
\renewcommand{{\headrulewidth}}{{0.4pt}}
\renewcommand{{\footrulewidth}}{{0pt}}
\fancyhead[L]{{{logo_block}}}
\fancyhead[R]{{}}
\fancyfoot[C]{{\small\thepage}}
\setlength{{\headheight}}{{24pt}}
\FloatBarrier
"""


def _build_wkhtml_css(branding: PdfBranding | None) -> str:
    return f"""
body {{
  font-family: Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.65;
  color: #111111;
  margin: 0;
}}
h1, h2, h3, h4 {{
  color: #111111;
  font-weight: 600;
}}
h1 {{
  font-size: 22pt;
  margin: 0 0 0.8em;
}}
h2 {{
  font-size: 16pt;
  margin-top: 1.4em;
}}
h3 {{
  font-size: 12pt;
  margin-top: 1.1em;
}}
p, li {{
  color: #111111;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 10pt;
}}
th, td {{
  border: 1px solid #dbe2ea;
  padding: 7px 10px;
  text-align: left;
}}
th {{
  background: #f8fafc;
  color: #111111;
}}
blockquote {{
  border-left: 3px solid #111111;
  margin: 1em 0;
  padding-left: 1em;
  color: #4b5563;
}}
.pdf-brand-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 10px;
  margin-bottom: 24px;
  border-bottom: 1px solid #dbe2ea;
}}
.pdf-brand-header img {{
  width: 42px;
  height: 42px;
  object-fit: contain;
}}
.pdf-brand-kicker {{
  font-size: 8pt;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.18em;
}}
.pdf-brand-title {{
  font-size: 12pt;
  color: #111111;
  font-weight: 600;
}}
"""


def _build_wkhtml_header_html(branding: PdfBranding | None) -> str:
    if not branding or not branding.logo_path:
        return ""
    logo_path = branding.logo_path.replace("\\", "/")
    return f"""<div class="pdf-brand-header">
  <img src="{logo_path}" alt="Logo del cliente" />
</div>"""


@dataclass
class PdfPandocExporter:
    name: str = "pdf_pandoc"
    branding: PdfBranding | None = None

    def export(self, run_dir: Path, md_path: Path, pdf_name: str = "documento.pdf") -> Path:
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
                header_tex.write_text(_build_header_tex(self.branding), encoding="utf-8")
                cmd.extend([
                    "--include-in-header", str(header_tex.name),
                    "-V", "fontsize=10.5pt",
                    "-V", "geometry:margin=2.4cm",
                    "-V", "papersize=a4",
                    "-V", "colorlinks=true",
                ])
            else:
                css_path = run_dir / "pandoc_pdf.css"
                css_path.write_text(_build_wkhtml_css(self.branding), encoding="utf-8")
                cmd.extend(["-c", str(css_path.name)])
                header_html = _build_wkhtml_header_html(self.branding)
                if header_html:
                    header_path = run_dir / "pandoc_before_body.html"
                    header_path.write_text(header_html, encoding="utf-8")
                    cmd.extend(["--include-before-body", str(header_path.name)])

            result = subprocess.run(
                cmd,
                cwd=str(run_dir),
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
                    f"Pandoc termino pero no creo {out_pdf}. Engine={engine}. STDERR: {stderr[:500] or '(vacio)'}"
                )
        except FileNotFoundError as e:
            tip = "winget install -e --id JohnMacFarlane.Pandoc" if sys.platform == "win32" else "brew install pandoc"
            raise RuntimeError(f"No se encontro pandoc. Instalar ({tip}) y reintentar.") from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            msg = "Fallo pandoc al generar el PDF."
            if stderr:
                msg += f"\nSTDERR:\n{stderr}"
            if stdout:
                msg += f"\nSTDOUT:\n{stdout}"
            raise RuntimeError(msg) from e

        return out_pdf

    def export_from_html(
        self, run_dir: Path, html_path: Path, pdf_name: str = "documento.pdf"
    ) -> Path:
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
                header_tex.write_text(_build_header_tex(self.branding), encoding="utf-8")
                cmd.extend([
                    "--include-in-header", str(header_tex.name),
                    "-V", "fontsize=10.5pt",
                    "-V", "geometry:margin=2.4cm",
                    "-V", "papersize=a4",
                    "-V", "colorlinks=true",
                ])
            result = subprocess.run(
                cmd,
                cwd=str(run_dir),
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
                    f"Pandoc termino pero no creo {out_pdf}. Engine={engine}. STDERR: {stderr[:500] or '(vacio)'}"
                )
        except FileNotFoundError as e:
            tip = "winget install -e --id JohnMacFarlane.Pandoc" if sys.platform == "win32" else "brew install pandoc"
            raise RuntimeError(f"No se encontro pandoc. Instalar ({tip}) y reintentar.") from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            msg = "Fallo pandoc al generar el PDF desde HTML."
            if stderr:
                msg += f"\nSTDERR:\n{stderr}"
            if stdout:
                msg += f"\nSTDOUT:\n{stdout}"
            raise RuntimeError(msg) from e
        return out_pdf
