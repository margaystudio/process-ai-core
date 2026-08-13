"""Regresión de los hallazgos de la auditoría de seguridad (agosto 2026).

Cada test fija el contrato de UN agujero cerrado y falla si alguien lo reabre:

  A1  XSS almacenado: el HTML del documento se sanea del lado servidor, tanto
      el que llega del editor como el que sale de markdown (que deja pasar
      HTML crudo).
  A2  SSRF / lectura de archivos locales: el render del PDF solo resuelve
      assets propios, `data:` y `file://` bajo el directorio de trabajo.
  B1  Permiso por carpeta en la capa semántica (cubierto en
      tests/test_semantic_permisos_carpeta.py, que necesita el árbol de
      carpetas y roles operativos).
  B2  El icono de branding no acepta SVG y se sirve con cabeceras inertes.
"""

from __future__ import annotations

import pytest

from process_ai_core.html_sanitize import sanitize_document_html


# ── A1 · Saneo del HTML del documento ────────────────────────────────────────

@pytest.mark.parametrize(
    "html_malicioso,fragmento_prohibido",
    [
        ('<p>ok</p><img src=x onerror="fetch(\'/api/auth/session\')">', "onerror"),
        ("<script>alert(1)</script><p>ok</p>", "<script"),
        ('<a href="javascript:alert(1)">click</a>', "javascript:"),
        ('<svg onload="alert(1)"></svg>', "onload"),
        ('<iframe src="https://evil.example"></iframe>', "iframe"),
        ('<object data="evil.swf"></object>', "object"),
        ('<embed src="evil.swf">', "embed"),
        ('<body onload="alert(1)">x</body>', "onload"),
        ('<img src="file:///etc/passwd">', "file:"),
        ('<td style="background:url(http://evil/)">c</td>', "url("),
        ('<div style="background:url(http://evil/)">c</div>', "url("),
        ('<style>@import url(http://evil/)</style>', "@import"),
    ],
)
def test_el_html_del_documento_no_deja_pasar_nada_ejecutable(
    html_malicioso: str, fragmento_prohibido: str
):
    """El vector real de la auditoría: quien edita ataca al que aprueba."""
    salida = sanitize_document_html(html_malicioso).lower()
    assert fragmento_prohibido not in salida, (
        f"{fragmento_prohibido!r} sobrevivió al saneo: {salida!r}"
    )


def test_el_contenido_legitimo_sobrevive_intacto():
    """Sanear no puede comerse el documento: es el contenido del cliente."""
    legitimo = (
        "<h2>Cierre de caja</h2>"
        "<p>Pasos <strong>obligatorios</strong> del <em>turno</em>:</p>"
        "<ul><li>Contar efectivo</li><li>Imprimir Z</li></ul>"
        '<table><colgroup><col style="width: 120px"></colgroup>'
        '<tbody><tr><td colspan="2">Total</td></tr></tbody></table>'
        '<img src="/api/v1/documents/d1/editor-images/foto.png" alt="POS">'
        '<a href="https://margaystudio.io">manual</a>'
        "<blockquote>Nota</blockquote><pre><code>salida</code></pre><hr>"
    )
    salida = sanitize_document_html(legitimo)
    for esperado in (
        "<h2>", "<strong>", "<em>", "<ul>", "<li>",
        "<table>", 'colspan="2"', 'style="width: 120px"',
        "editor-images/foto.png", 'alt="POS"',
        'href="https://margaystudio.io"', "<blockquote>", "<pre>", "<hr>",
    ):
        assert esperado in salida, f"se perdió {esperado!r} del contenido legítimo"


def test_los_links_salen_con_rel_seguro():
    salida = sanitize_document_html('<a href="https://x.io">y</a>')
    assert 'rel="noopener noreferrer"' in salida


def test_markdown_con_html_crudo_embebido_tambien_se_sanea():
    """`markdown` deja pasar el HTML que venga adentro, y ese markdown sale de
    la generación por IA sobre evidencia del usuario."""
    from process_ai_core.export.markdown_html import render_frozen_html

    salida = render_frozen_html(
        "# Título\n\nTexto normal.\n\n<img src=x onerror=\"alert(1)\">\n"
    )
    assert salida is not None
    assert "onerror" not in salida.lower()
    assert "<h1>" in salida  # el markdown legítimo sigue renderizando


def test_entrada_vacia_no_rompe():
    assert sanitize_document_html("") == ""
    assert sanitize_document_html(None) == ""


# ── A2 · El render del PDF no sale a la red ni lee disco arbitrario ──────────

@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",   # metadata de la nube
        "http://localhost:8000/api/v1/workspaces",     # servicio interno
        "https://evil.example/pixel.png",              # exfiltración
        "file:///etc/passwd",                          # lectura de disco
        "file:///root/.ssh/id_rsa",
        "ftp://evil.example/x",
    ],
)
def test_el_fetcher_del_pdf_bloquea_recursos_externos(url: str):
    """SSRF y LFI: el HTML del documento lo escribe el usuario y WeasyPrint
    resuelve todo lo que encuentre."""
    from process_ai_core.export.asset_fetcher import (
        RecursoExternoBloqueado,
        safe_url_fetcher,
    )

    with pytest.raises(RecursoExternoBloqueado):
        safe_url_fetcher(url)


def test_el_fetcher_permite_data_uri():
    """El QR de la portada viaja como data URI: no sale a ningún lado."""
    from process_ai_core.export.asset_fetcher import safe_url_fetcher

    # 1x1 gif transparente
    data = (
        "data:image/gif;base64,"
        "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    )
    # WeasyPrint 69 devuelve un URLFetcherResponse (antes era un dict): lo que
    # importa es que resuelva sin bloquearse y traiga los bytes.
    assert safe_url_fetcher(data).read().startswith(b"GIF")


def test_el_fetcher_permite_el_logo_bajo_el_directorio_de_trabajo(tmp_path, monkeypatch):
    """El único `file://` legítimo: el logo que materializa el servidor."""
    from process_ai_core.export.asset_fetcher import safe_url_fetcher
    from process_ai_core import config as config_mod

    logo = tmp_path / "workspace-branding" / "ws-1" / "logo.png"
    logo.parent.mkdir(parents=True)
    logo.write_bytes(b"\x89PNG\r\n\x1a\n")

    class _S:
        output_dir = str(tmp_path)

    monkeypatch.setattr(config_mod, "get_settings", lambda: _S())
    assert safe_url_fetcher(logo.as_uri()).read() == b"\x89PNG\r\n\x1a\n"


def test_el_fetcher_bloquea_el_escape_del_directorio_de_trabajo(tmp_path, monkeypatch):
    """`output/../../etc/passwd`: por eso se resuelve antes de comparar."""
    from process_ai_core.export.asset_fetcher import (
        RecursoExternoBloqueado,
        safe_url_fetcher,
    )
    from process_ai_core import config as config_mod

    afuera = tmp_path / "secreto.txt"
    afuera.write_text("credenciales")
    trabajo = tmp_path / "output"
    trabajo.mkdir()

    class _S:
        output_dir = str(trabajo)

    monkeypatch.setattr(config_mod, "get_settings", lambda: _S())
    escape = (trabajo / ".." / "secreto.txt").as_uri()
    with pytest.raises(RecursoExternoBloqueado):
        safe_url_fetcher(escape)


def test_el_render_sin_fetcher_explicito_usa_el_restrictivo():
    """El camino de generación no puede caer al fetcher por defecto de
    WeasyPrint, que baja http(s) y file:// arbitrarios."""
    import inspect

    from process_ai_core.export import pdf_weasyprint

    fuente = inspect.getsource(pdf_weasyprint)
    assert "self.url_fetcher or safe_url_fetcher" in fuente, (
        "el render debe pasar SIEMPRE un url_fetcher restrictivo"
    )


# ── B2 · El icono de branding ────────────────────────────────────────────────

def test_el_branding_no_acepta_svg():
    """Un SVG es XML con <script> adentro, y este icono se sirve sin auth."""
    from api.routes.workspaces import ALLOWED_BRANDING_EXTENSIONS

    assert ".svg" not in ALLOWED_BRANDING_EXTENSIONS
    assert ".png" in ALLOWED_BRANDING_EXTENSIONS


def test_el_icono_se_sirve_con_cabeceras_inertes():
    """Cubre además los SVG subidos antes de sacarlos de la allow-list."""
    from api.routes.workspaces import _CABECERAS_ICONO

    assert _CABECERAS_ICONO["X-Content-Type-Options"] == "nosniff"
    csp = _CABECERAS_ICONO["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "sandbox" in csp
