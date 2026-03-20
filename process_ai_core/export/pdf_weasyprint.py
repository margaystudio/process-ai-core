from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .branding import PdfBranding

_BASE_CSS = """
@page {
    size: A4;
    margin: 2.4cm 2.2cm 2.2cm 2.2cm;
    @top-center {
        content: element(pdf-page-header);
    }
    @bottom-right {
        content: counter(page);
        font-family: 'Helvetica Neue', Arial, sans-serif;
        font-size: 9pt;
        color: #111111;
    }
}

body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: #111111;
}

.pdf-page-header {
    position: running(pdf-page-header);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 0.6rem;
    margin-bottom: 1.4rem;
    border-bottom: 1px solid var(--pdf-border-color);
}

.pdf-brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.pdf-brand img {
    width: 44px;
    height: 44px;
    object-fit: contain;
    margin: 0;
}

.pdf-brand-copy {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
}

.pdf-brand-kicker {
    font-size: 8pt;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #111111;
}

.pdf-brand-title {
    font-size: 12pt;
    font-weight: 600;
    color: #111111;
}

.pdf-content {
    padding-top: 0.25rem;
}

h1 { font-size: 21pt; font-weight: 600; margin: 0 0 0.75em; color: #111111; line-height: 1.2; }
h2 { font-size: 15pt; font-weight: 600; margin: 1.4em 0 0.5em; color: #111111; line-height: 1.3; }
h3 { font-size: 12pt; font-weight: 600; margin: 1.1em 0 0.4em; color: #111111; line-height: 1.35; }
h4 { font-size: 10.5pt; font-weight: 600; margin: 0.9em 0 0.3em; color: #111111; }

p { margin: 0.55em 0; }

table {
    border-collapse: collapse;
    width: 100%;
    margin: 1.2em 0;
    font-size: 10pt;
    page-break-inside: avoid;
}

th {
    background-color: #f8fafc;
    border: 1px solid var(--pdf-border-color);
    padding: 7px 10px;
    text-align: left;
    font-weight: 600;
    color: #111111;
}

td {
    border: 1px solid var(--pdf-border-color);
    padding: 7px 10px;
    vertical-align: top;
}

tr:nth-child(even) td {
    background-color: #fcfcfd;
}

ul, ol {
    margin: 0.5em 0 0.9em;
    padding-left: 1.35em;
}

li {
    margin: 0.25em 0;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.8em auto;
    page-break-inside: avoid;
}

pre, code {
    font-family: 'Courier New', monospace;
    font-size: 9pt;
    background-color: #f8fafc;
    border-radius: 3px;
}

pre {
    padding: 0.8em;
    overflow-x: auto;
    page-break-inside: avoid;
}

code {
    padding: 0.1em 0.3em;
}

blockquote {
    border-left: 3px solid #111111;
    margin: 0.9em 0;
    padding: 0.2em 0 0.2em 1em;
    color: #4b5563;
}

h1, h2 {
    page-break-after: avoid;
}
"""


@dataclass
class PdfWeasyprintExporter:
    name: str = "pdf_weasyprint"
    base_url: str | None = None
    branding: PdfBranding | None = None

    def export_from_html_string(
        self,
        html_content: str,
        output_path: Path,
    ) -> Path:
        try:
            from weasyprint import CSS, HTML
        except ImportError as e:
            raise ImportError(
                "WeasyPrint no esta instalado. Ejecuta: pip install weasyprint"
            ) from e

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        full_html = _wrap_html(html_content, self.branding)

        try:
            doc = HTML(string=full_html, base_url=self.base_url)
            css = CSS(string=_BASE_CSS)
            doc.write_pdf(str(output_path), stylesheets=[css])
        except Exception as e:
            raise RuntimeError(f"WeasyPrint fallo al generar el PDF: {e}") from e

        return output_path

    def export_from_html_file(
        self,
        html_path: Path,
        output_path: Path,
    ) -> Path:
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"No existe el HTML: {html_path}")
        html_content = html_path.read_text(encoding="utf-8")
        return self.export_from_html_string(html_content, output_path)


def _wrap_html(html_content: str, branding: PdfBranding | None = None) -> str:
    stripped = html_content.strip().lower()
    if stripped.startswith("<!doctype") or stripped.startswith("<html"):
        return html_content

    logo_html = ""
    if branding and branding.logo_path:
        logo_html = f'<img src="{branding.logo_path}" alt="Logo del cliente">'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
    --pdf-border-color: #dbe2ea;
}}
</style>
</head>
<body>
<div class="pdf-page-header">
  <div class="pdf-brand">
    {logo_html}
  </div>
</div>
<main class="pdf-content">
{html_content}
</main>
</body>
</html>"""
