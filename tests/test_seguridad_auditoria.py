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


# ── C1 · El estado de aprobación no se edita a mano ──────────────────────────

@pytest.mark.parametrize("nuevo", ["approved", "rejected", "pending_validation"])
def test_el_status_del_flujo_no_se_puede_setear_por_el_put(nuevo: str):
    """Marcar "aprobado" por el PUT salteaba validación, segregación y acta."""
    from fastapi import HTTPException

    from api.routes.documents.crud import _assert_transicion_de_status_permitida

    with pytest.raises(HTTPException) as exc:
        _assert_transicion_de_status_permitida("draft", nuevo)
    assert exc.value.status_code == 400


def test_archivar_y_desarchivar_si_estan_permitidos():
    """Es la única gestión manual de estado: no toca versiones ni aprobaciones."""
    from api.routes.documents.crud import _assert_transicion_de_status_permitida

    _assert_transicion_de_status_permitida("approved", "archived")
    _assert_transicion_de_status_permitida("draft", "archived")
    _assert_transicion_de_status_permitida("archived", "draft")


# ── C2/C4 · Endpoints eliminados ─────────────────────────────────────────────

def test_no_existe_escritura_del_catalogo_por_http():
    """Era global (no scopeado por tenant) y su prompt_text entra a los prompts
    de generación de todos los tenants."""
    from api.routes import catalog

    rutas = {(r.path, tuple(sorted(r.methods))) for r in catalog.router.routes}
    assert not any("POST" in metodos for _, metodos in rutas)


def test_no_existe_auto_provision_de_suscripcion():
    """El plan es una decisión comercial, no una preferencia del workspace."""
    from api.routes import subscriptions

    for r in subscriptions.router.routes:
        if "subscription" in r.path and "POST" in r.methods:
            pytest.fail(f"volvió el endpoint de auto-provisión: {r.path}")


# ── C5 · Vinculación por email ───────────────────────────────────────────────

def test_no_se_vincula_por_email_sin_verificar(monkeypatch):
    """Con registro sin confirmación, vincular por email es robo de identidad."""
    import api.dependencies as deps

    llamadas = []
    monkeypatch.setattr(
        deps, "get_user_by_external_id", lambda *a, **k: None
    )
    import process_ai_core.db.helpers as helpers_mod
    monkeypatch.setattr(
        helpers_mod, "get_user_by_email",
        lambda *a, **k: llamadas.append(a) or None,
    )
    monkeypatch.setattr(
        deps, "_decode_and_verify_supabase_jwt",
        lambda t: {"sub": "sub-nuevo", "email": "victima@cliente.com"},
    )

    from fastapi import HTTPException

    class _S:
        def query(self, *a, **k):
            raise AssertionError("no debería consultar")

    with pytest.raises(HTTPException):
        deps.get_current_user_id(authorization="Bearer x", session=_S())
    assert not llamadas, "se buscó por email sin que estuviera verificado"


# ── Bajas: emisor del JWT y HS256 ────────────────────────────────────────────

def test_se_rechaza_un_token_de_otro_emisor(monkeypatch):
    from fastapi import HTTPException

    import api.dependencies as deps

    monkeypatch.setenv("SUPABASE_URL", "https://proyecto-a.supabase.co")
    with pytest.raises(HTTPException) as exc:
        deps._assert_issuer_valido({"iss": "https://proyecto-b.supabase.co/auth/v1"})
    assert exc.value.status_code == 401


def test_un_token_sin_iss_sigue_siendo_valido(monkeypatch):
    """Validar `iss` es defensa en profundidad; exigirlo apagaría el login."""
    import api.dependencies as deps

    monkeypatch.setenv("SUPABASE_URL", "https://proyecto-a.supabase.co")
    deps._assert_issuer_valido({"sub": "x"})  # no lanza


# ── Bajas: validación de imágenes por contenido ──────────────────────────────

@pytest.mark.parametrize(
    "contenido,ext",
    [
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', ".png"),
        (b"<!DOCTYPE html><script>alert(1)</script>", ".png"),
        (b"GIF89a" + b"x" * 10, ".png"),  # firma real distinta de la declarada
        (b"", ".png"),
    ],
)
def test_no_pasa_un_archivo_que_no_es_la_imagen_que_dice_ser(contenido, ext):
    from process_ai_core.image_validation import es_imagen_valida

    assert es_imagen_valida(contenido, ext) is False


@pytest.mark.parametrize(
    "contenido,ext",
    [
        (b"\x89PNG\r\n\x1a\n" + b"x" * 10, ".png"),
        (b"\xff\xd8\xff\xe0" + b"x" * 10, ".jpg"),
        (b"\xff\xd8\xff\xe0" + b"x" * 10, ".jpeg"),
        (b"GIF89a" + b"x" * 10, ".gif"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", ".webp"),
    ],
)
def test_las_imagenes_reales_pasan(contenido, ext):
    from process_ai_core.image_validation import es_imagen_valida

    assert es_imagen_valida(contenido, ext) is True
