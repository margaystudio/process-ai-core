"""
process_ai_core.export.pdf_weasyprint
======================================

Exportador HTML → PDF usando WeasyPrint.

Se usa cuando la fuente de verdad es content_html (edición manual con Tiptap).
WeasyPrint renderiza HTML+CSS como un browser, preservando:
  - Tablas complejas con múltiples columnas y anchos relativos
  - Imágenes inline en el flujo del documento
  - Estilos tipográficos del editor

Requisitos
----------
- weasyprint instalado en el entorno: `pip install weasyprint`
- Para imágenes remotas (http://localhost:...), el servidor debe estar levantado.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# CSS base que se inyecta al documento HTML para una apariencia consistente
_BASE_CSS = """
@page {
    size: A4;
    margin: 2.5cm;
}

body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a1a1a;
}

h1 { font-size: 20pt; font-weight: bold; margin: 1.2em 0 0.4em; color: #111; border-bottom: 1px solid #ddd; padding-bottom: 0.2em; }
h2 { font-size: 16pt; font-weight: bold; margin: 1em 0 0.4em; color: #222; }
h3 { font-size: 13pt; font-weight: bold; margin: 0.8em 0 0.3em; color: #333; }
h4 { font-size: 11pt; font-weight: bold; margin: 0.6em 0 0.2em; color: #444; }

p { margin: 0.5em 0; }

/* Tablas */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 10pt;
    page-break-inside: avoid;
}
th {
    background-color: #f0f0f0;
    border: 1px solid #bbb;
    padding: 6px 10px;
    text-align: left;
    font-weight: bold;
}
td {
    border: 1px solid #ccc;
    padding: 5px 10px;
    vertical-align: top;
}
tr:nth-child(even) td {
    background-color: #fafafa;
}

/* Listas */
ul, ol {
    margin: 0.4em 0;
    padding-left: 1.5em;
}
li {
    margin: 0.2em 0;
}

/* Imágenes */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.8em auto;
    page-break-inside: avoid;
}

/* Código */
pre, code {
    font-family: 'Courier New', monospace;
    font-size: 9pt;
    background-color: #f5f5f5;
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

/* Citas */
blockquote {
    border-left: 3px solid #ccc;
    margin: 0.5em 0;
    padding: 0.3em 1em;
    color: #555;
}

/* Saltos de página */
h1, h2 {
    page-break-after: avoid;
}
"""


@dataclass
class PdfWeasyprintExporter:
    """
    Exportador PDF basado en WeasyPrint (HTML → PDF nativo).

    Atributos
    ---------
    name:
        Identificador del exportador.
    base_url:
        URL base para resolver recursos relativos (imágenes, etc.).
        Si es None, WeasyPrint usará el sistema de archivos local.
    """

    name: str = "pdf_weasyprint"
    base_url: str | None = None

    def export_from_html_string(
        self,
        html_content: str,
        output_path: Path,
    ) -> Path:
        """
        Genera PDF desde un string HTML.

        Parameters
        ----------
        html_content:
            HTML del documento. Puede ser HTML parcial (sin <html>/<head>) o completo.
            Se envuelve automáticamente en un documento HTML completo con el CSS base.
        output_path:
            Ruta donde se escribirá el PDF.

        Returns
        -------
        Path
            Ruta al PDF generado.

        Raises
        ------
        RuntimeError
            Si WeasyPrint falla al generar el PDF.
        ImportError
            Si WeasyPrint no está instalado.
        """
        try:
            from weasyprint import HTML, CSS
        except ImportError as e:
            raise ImportError(
                "WeasyPrint no está instalado. Ejecutá: pip install weasyprint"
            ) from e

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Envolver en documento HTML completo si hace falta
        full_html = _wrap_html(html_content)

        try:
            doc = HTML(string=full_html, base_url=self.base_url)
            css = CSS(string=_BASE_CSS)
            doc.write_pdf(str(output_path), stylesheets=[css])
        except Exception as e:
            raise RuntimeError(f"WeasyPrint falló al generar el PDF: {e}") from e

        return output_path

    def export_from_html_file(
        self,
        html_path: Path,
        output_path: Path,
    ) -> Path:
        """
        Genera PDF desde un archivo HTML.

        Parameters
        ----------
        html_path:
            Ruta al archivo HTML.
        output_path:
            Ruta donde se escribirá el PDF.
        """
        html_path = Path(html_path)
        if not html_path.exists():
            raise FileNotFoundError(f"No existe el HTML: {html_path}")
        html_content = html_path.read_text(encoding="utf-8")
        return self.export_from_html_string(html_content, output_path)


def _wrap_html(html_content: str) -> str:
    """
    Si el contenido no incluye <html>, lo envuelve en un documento completo.
    Esto garantiza que WeasyPrint tenga el contexto correcto para renderizar.
    """
    stripped = html_content.strip().lower()
    if stripped.startswith("<!doctype") or stripped.startswith("<html"):
        return html_content
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
{html_content}
</body>
</html>"""
