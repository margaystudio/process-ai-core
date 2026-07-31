"""
Helpers compartidos entre los sub-routers de documentos.

Se extrajeron del módulo monolítico original (documents.py) para que crud,
runs, content y versions puedan reutilizarlos sin duplicar lógica.
"""

import hashlib
import logging
import re
from pathlib import PurePosixPath
from typing import Optional
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import Response

from process_ai_core.export.markdown_html import markdown_to_html, strip_latex_artifacts

logger = logging.getLogger(__name__)


def _assert_doc_in_active_workspace(doc_workspace_id: str, active_workspace_id: str, document_id: str) -> None:
    """Lanza 404 si el documento no pertenece al workspace activo del contexto."""
    if doc_workspace_id != active_workspace_id:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado")


# Alias del core: la conversión markdown→HTML es ahora la puerta de entrada del
# único motor de PDF, así que la implementación vive en process_ai_core.export
# para que el core no dependa de api/. Ver process_ai_core/export/markdown_html.py.
_strip_latex_artifacts = strip_latex_artifacts


def _markdown_to_html(md: str) -> str:
    """
    Convierte Markdown a HTML para precarga del editor manual.

    Tolera un fallo de la librería devolviendo texto escapado: acá el HTML es
    solo lo que se precarga en el editor, y dejar al usuario sin pantalla es peor
    que mostrarle el markdown plano. El camino del PDF NO usa este fallback
    (`markdown_to_html` lanza), porque ahí un HTML degradado se congelaría como
    artefacto de auditoría.
    """
    try:
        return markdown_to_html(md)
    except Exception:
        logger.warning("Falló la conversión markdown→HTML para el editor; se usa texto plano")
        import html as html_mod
        return "".join(f"<p>{html_mod.escape(line)}</p>" for line in (md or "").splitlines())


def editor_image_path(document_id: str, filename: str) -> str:
    """
    Ruta canónica de una imagen subida por el editor manual.

    Definición única: la usan el endpoint que la sirve, el que la sube, el proxy
    del front y `StorageAssetFetcher` para resolverla al congelar el PDF.
    """
    return f"/api/v1/documents/{document_id}/editor-images/{filename}"


# ═══════════════════════════════════════════════════════════════════════════════
# PRINCIPIO: nada que el navegador pida por su cuenta lleva una credencial en la
# dirección.
#
# Una URL con un token adentro es un PORTADOR: el servidor valida la firma pero
# NO sabe quién la presenta. Con eso no se puede aplicar el permiso por carpeta —
# cualquiera con el enlace (una captura de pantalla, el historial, "copiar
# dirección de la imagen") ve contenido de una carpeta que tiene denegada. Y la
# revocación no existe: al que le sacan el acceso se queda con el enlace.
#
# Cómo se cumple depende del caso, y son dos:
#
#   1. **Un archivo suelto que el usuario abre a propósito** (el PDF de una
#      versión, un artefacto de run): lo pide la PANTALLA con `fetch` +
#      Authorization y lo muestra desde un blob URL. La credencial va en el
#      header, donde no queda escrita en ningún lado.
#
#   2. **Una imagen embebida en contenido que se edita y se guarda** (esto): el
#      `<img>` lo dispara el navegador solo, sin que ningún JavaScript pueda
#      ponerle un header. Va por el PROXY del front (ui/app/api/doc-assets/),
#      que sí es del mismo origen que el navegador, tiene la sesión en cookie, y
#      llama a la API con Bearer. La API verifica ahí el permiso de carpeta.
#
# Lo que se GUARDA en el contenido es siempre la ruta pelada: un identificador,
# no una autorización (ver `strip_image_url_tokens`).
#
# Si aparece una superficie nueva que tiene que mostrar un archivo, entra en uno
# de esos dos casos. Ninguno es "firmar la URL".
# ═══════════════════════════════════════════════════════════════════════════════

#: Prefijo del proxy del front. El navegador pide ACÁ (mismo origen que la
#: página, así que viaja la cookie de sesión) y el route handler reenvía a la API
#: con Authorization. Ver ui/app/api/doc-assets/[...ruta]/route.ts.
PROXY_PREFIX = "/api/doc-assets"

#: Imágenes de documento servidas por la API: assets de una versión (las que trae
#: adentro un PDF importado) e imágenes subidas por el editor manual.
_DOCUMENT_IMAGE_PATH_RE = re.compile(
    r"^/api/v1/documents/[^/?#]+/(?:versions/[^/?#]+/assets|editor-images)/[^/?#]+$"
)

#: La misma ruta, con host y/o token, para poder volver a la forma canónica antes
#: de PERSISTIRLA. Cubre también la ruta del proxy, que es lo que el editor
#: devuelve ahora.
_DOCUMENT_IMAGE_ANY_RE = re.compile(
    r"^(?:https?://[^/]+)?(?:" + re.escape(PROXY_PREFIX) + r")?"
    r"(?P<path>/api/v1/documents/[^/?#]+/"
    r"(?:versions/[^/?#]+/assets|editor-images)/[^/?#]+)(?:\?[^\"#]*)?$"
)

#: Artefacto de run, con host, token y/o prefijo del proxy. Al persistir se
#: vuelve a la ruta relativa `assets/...`, que es la forma portable del contenido.
_RUN_ASSET_ANY_RE = re.compile(
    r"^(?:https?://[^/]+)?(?:" + re.escape(PROXY_PREFIX) + r")?"
    r"/api/v1/artifacts/[^/?#]+/(?P<rel>assets/[^\"?#]+)(?:\?[^\"#]*)?$"
)


def rewrite_img_src_to_proxy(
    html_content: str,
    run_id: Optional[str],
    tenant_id: Optional[str] = None,
) -> str:
    """
    Apunta las imágenes del contenido al proxy del front.

    - src="assets/..."                        → {PROXY}/api/v1/artifacts/{run_id}/assets/...
    - src="/api/v1/documents/.../assets/..."  → {PROXY}/api/v1/documents/...
    - src="http..." o cualquier otra cosa     → sin cambios

    Rutas RELATIVAS al origen de la página, no absolutas a la API: el proxy vive
    en el front, que es de donde el navegador ya está cargando el HTML.

    `tenant_id` viaja como query param `t`. NO es una credencial: es el selector
    de tenant activo, que un `<img>` no puede mandar por header (el resto de la
    app lo manda en `X-Active-Tenant-Id`). Sin él, un usuario con varios tenants
    resolvería el workspace equivocado y su propia imagen le daría 404. El
    permiso se sigue verificando contra el usuario autenticado del request.

    Solo se usa para HTML que va al NAVEGADOR. Los renders del servidor (el
    preview y el freeze del PDF) resuelven los assets con `StorageAssetFetcher`,
    leyendo los blobs directo de object storage: sin HTTP, sin sesión y sin
    token. Un artefacto de auditoría no puede depender de que alguien esté
    logueado para poder congelarse.
    """
    if not html_content:
        return html_content

    sufijo = f"?t={quote(tenant_id, safe='')}" if tenant_id else ""

    def replace_src(m: re.Match) -> str:
        src = m.group(1)
        if _DOCUMENT_IMAGE_PATH_RE.match(src):
            return f'src="{PROXY_PREFIX}{src}{sufijo}"'
        if src.startswith("http") or src.startswith("/"):
            return m.group(0)
        if run_id and (src.startswith("assets/") or src.startswith("./assets/")):
            clean = src.lstrip("./")
            return f'src="{PROXY_PREFIX}/api/v1/artifacts/{run_id}/{clean}{sufijo}"'
        return m.group(0)

    return re.sub(r'src="([^"]+)"', replace_src, html_content)


_MEDIA_TYPE_POR_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
}


def media_type_for(filename: str) -> str:
    return _MEDIA_TYPE_POR_EXTENSION.get(
        PurePosixPath(filename).suffix.lower(), "application/octet-stream"
    )


def authorized_file_response(
    content: bytes,
    filename: str,
    request: Request,
    *,
    media_type: Optional[str] = None,
    download: bool = False,
) -> Response:
    """
    Respuesta de un archivo cuyo acceso se acaba de autorizar.

    `private, no-cache` con ETag, la misma decisión que se tomó para el PDF
    congelado y por el mismo motivo: el archivo es inmutable, pero el DERECHO A
    VERLO no lo es. Ahora que cada pedido verifica el permiso de carpeta, dejar
    que el navegador sirva de su cache sin revalidar le devolvería contenido a
    alguien a quien ya le sacaron el acceso — que es exactamente el agujero que
    esto vino a cerrar, reabierto del lado del cliente.

    `no-cache` NO significa "no guardes": significa "guardá, pero revalidá". Se
    conserva casi todo el beneficio, porque la revalidación termina en un 304 sin
    cuerpo — ni lectura de storage ni transferencia de la imagen.
    """
    etag = f'"{hashlib.sha256(content).hexdigest()[:32]}"'
    disposicion = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": f'{disposicion}; filename="{filename}"',
        "Cache-Control": "private, no-cache",
        "ETag": etag,
        # El navegador respeta el Content-Type declarado en vez de adivinarlo por
        # el contenido. Estos bytes vienen de un archivo que subió un usuario:
        # sin esto, un archivo con bytes que parecen HTML podría ejecutarse como
        # tal en el origen de la API.
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(
        content=content, media_type=media_type or media_type_for(filename), headers=headers
    )


def strip_image_url_tokens(html_content: str) -> str:
    """
    Devuelve el HTML con las imágenes en su forma CANÓNICA: sin host, sin prefijo
    del proxy y sin token.

    Se aplica antes de persistir contenido que viene del editor. El editor recibe
    el HTML con las imágenes apuntando al proxy (para poder mostrarlas) y devuelve
    tal cual lo que tiene, así que sin esto el contenido de la versión quedaría
    con una ruta del front adentro. Y antes, cuando las URLs se firmaban, quedaba
    directamente un token guardado.

    Lo que se guarda es un IDENTIFICADOR de la imagen, no una forma de llegar a
    ella: quién puede verla se resuelve en cada request. Por eso el mismo
    `content_html` sirve para el navegador (vía proxy), para el PDF (vía object
    storage) y para cualquier consumidor futuro.

    Sigue cubriendo el caso viejo —URLs absolutas y firmadas guardadas antes de
    esta normalización— porque hay contenido en la base con esa forma.

    Cubre también los artefactos de run (`/api/v1/artifacts/{run}/assets/...` →
    `assets/...`), que tenían el mismo problema desde antes: una versión editada
    a mano guardaba la URL firmada, y al congelar el PDF esa ruta no la resolvía
    ningún esquema del fetcher.
    """
    if not html_content:
        return html_content

    def replace_src(m: re.Match) -> str:
        src = m.group(1)
        documento = _DOCUMENT_IMAGE_ANY_RE.match(src)
        if documento:
            return f'src="{documento["path"]}"'
        run_asset = _RUN_ASSET_ANY_RE.match(src)
        if run_asset:
            return f'src="{run_asset["rel"]}"'
        return m.group(0)

    return re.sub(r'src="([^"]+)"', replace_src, html_content)


_HTML_BLOCK_RE = re.compile(
    r"<(?:h[1-6]|p|ul|ol|li|strong|em|b|i|table|img|div|span|a|br|hr|blockquote|pre|code)\b",
    re.IGNORECASE,
)


def _is_valid_html(text: str) -> bool:
    """
    Devuelve True si el texto contiene etiquetas HTML de bloque o inline.
    HTML generado por python-markdown o Tiptap siempre las tiene.
    Markdown crudo nunca las tiene.
    """
    return bool(_HTML_BLOCK_RE.search(text or ""))


def _looks_like_markdown(text: str) -> bool:
    """
    Devuelve True si el texto NO contiene etiquetas HTML válidas
    (es decir, probablemente es markdown crudo o texto plano).
    Se mantiene por compatibilidad; internamente usa _is_valid_html.
    """
    return not _is_valid_html(text)
