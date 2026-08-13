"""
Resolución de imágenes del documento SIN salir a la red.

El problema
-----------
Hasta ahora las imágenes del documento (`src="assets/..."`) se reescribían a URLs
firmadas de la propia API y WeasyPrint las bajaba por HTTP mientras renderizaba.
Eso tiene tres fallas, todas silenciosas:

1. **WeasyPrint no lanza si una imagen no se puede bajar**: la omite y sigue.
   Verificado. El PDF sale sin la imagen, se le calcula el SHA-256 y queda
   registrado como el documento oficial.
2. Durante el freeze, la API se llama **a sí misma** mientras está atendiendo la
   request de aprobación que disparó ese mismo freeze.
3. Depende de la red y de que la firma no haya vencido — en un cold start de
   Cloud Run, las dos cosas pueden fallar.

En un documento de proceso las imágenes SON la evidencia: capturas del
procedimiento, remitos, pantallas. Un artefacto al que le faltan evidencias, con
hash calculado y registrado, no es detectable después.

La solución
-----------
Un `url_fetcher` propio que lee los blobs directo de object storage. Sin HTTP,
sin firma, sin red. Y que además REGISTRA cada fallo, para que el freeze pueda
abortar en vez de congelar un documento mutilado (ver `verify_pdf_images`).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

logger = logging.getLogger(__name__)

# Host centinela. No existe ni se resuelve por DNS: es solo un prefijo estable
# para que WeasyPrint componga URLs absolutas bien formadas a partir de las rutas
# relativas del documento, y para que este fetcher las reconozca.
#
# Se usa un http(s) y no un esquema propio (`pai-asset://`) porque con un esquema
# desconocido WeasyPrint NO resuelve la ruta relativa contra el base_url y el
# fetcher recibe el string crudo — comportamiento frágil del que no conviene
# depender. Verificado.
ASSET_BASE_URL = "https://assets.process-ai.internal/"

_RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}
_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".svg": "image/svg+xml",
}

# Imágenes que el editor manual sube: se sirven por este path y viven en storage
# bajo workspaces/{ws}/editor-uploads/{document_id}/{archivo}.
_EDITOR_IMAGE_RE = re.compile(
    r"^/?api/v1/documents/(?P<document_id>[^/]+)/editor-images/(?P<filename>[^/]+)$"
)

# Imágenes que son assets de UNA VERSIÓN: hoy, las que trae adentro un PDF
# importado. Viven bajo la clave canónica de la versión
# (workspaces/{ws}/documents/{doc}/versions/{ver}/assets/{archivo}), que es
# inmutable como la versión misma — a diferencia de editor-uploads, que es del
# documento y cambia.
_VERSION_ASSET_RE = re.compile(
    r"^/?api/v1/documents/(?P<document_id>[^/]+)/versions/(?P<version_id>[^/]+)"
    r"/assets/(?P<filename>[^/]+)$"
)


class AssetResolutionError(RuntimeError):
    """Un asset referenciado por el documento no se pudo resolver."""


class RecursoExternoBloqueado(RuntimeError):
    """El documento apuntaba a un recurso fuera de lo permitido y se bloqueó."""


def _ruta_local_permitida(url: str) -> bool:
    """
    True si el `file://` cae DENTRO del directorio de trabajo del módulo.

    Es el único `file://` legítimo, y cubre los dos casos reales: el logo del
    cliente que el servidor materializa en cache (`_branding.py`) y los assets
    del run cuando el render usa el directorio del run como `base_url`
    (`export_pdf`). Los dos cuelgan de `output_dir`.

    `resolve()` antes de comparar: sin eso, `output/../../etc/passwd` pasaría.
    """
    from process_ai_core.config import get_settings

    try:
        raiz = Path(get_settings().output_dir).resolve()
        destino = Path(url2pathname(unquote(urlparse(url).path))).resolve()
    except (OSError, ValueError):
        return False
    return destino == raiz or raiz in destino.parents


def safe_url_fetcher(url: str, timeout: int = 10, ssl_context=None) -> dict:
    """
    `url_fetcher` restrictivo: allow-list de lo que el render puede resolver.

    POR QUÉ EXISTE
    --------------
    El HTML del documento lo escribe el usuario (editor manual, o generación a
    partir de evidencia suya) y WeasyPrint resuelve TODO lo que encuentre:
    `<img src>`, `url()` de CSS, `<image>` de SVG. Con el fetcher por defecto
    eso incluye `http(s)://` y `file://` arbitrarios, es decir:

      - **SSRF**: `<img src="http://169.254.169.254/...">` hace que el servidor
        pida el metadata de la nube, o barra puertos de la red interna. La
        respuesta no se ve, pero los tiempos y los errores filtran igual.
      - **Lectura de archivos locales**: `<img src="file:///...">` embebe un
        archivo del servidor en el PDF, que después el mismo usuario descarga.

    Se dispara sin interacción de nadie más: alcanza con guardar el documento y
    pedir el preview (o aprobarlo, que congela el PDF).

    QUÉ PERMITE
    -----------
    - `data:` — inerte, no sale a ningún lado (lo usa el QR de la portada).
    - `file://` **bajo `output_dir`** — logo del cliente y assets del run.
    Todo lo demás se bloquea. Bloquear significa que la imagen no se dibuja:
    WeasyPrint se traga el error del fetcher y sigue. Se loguea a nivel warning
    porque un documento que apunta afuera es, como mínimo, algo para mirar.
    """
    from weasyprint import default_url_fetcher

    if url.startswith("data:"):
        return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)

    if url.startswith("file://"):
        if _ruta_local_permitida(url):
            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
        logger.warning("Render de PDF: bloqueado file:// fuera del directorio de trabajo: %s", url)
        raise RecursoExternoBloqueado(f"ruta local no permitida: {url}")

    logger.warning("Render de PDF: bloqueado recurso externo: %s", url)
    raise RecursoExternoBloqueado(f"recurso externo no permitido: {url}")


@dataclass
class StorageAssetFetcher:
    """
    `url_fetcher` de WeasyPrint que resuelve los assets del documento desde
    object storage, y lleva registro de qué se pidió y qué falló.

    El registro es la parte importante: WeasyPrint se traga los errores del
    fetcher, así que sin esto un fallo de resolución sería invisible.
    """

    workspace_id: str | None = None
    run_id: str | None = None
    document_id: str | None = None

    #: URLs que se resolvieron bien, con el flag de si son imagen ráster (las
    #: vectoriales, SVG, no producen un XObject de imagen en el PDF).
    resolved: dict[str, bool] = field(default_factory=dict)
    #: URL → motivo, para cada asset que NO se pudo resolver.
    failures: dict[str, str] = field(default_factory=dict)

    # ── API de WeasyPrint ────────────────────────────────────────────────────

    def __call__(self, url: str, timeout: int = 10, ssl_context=None) -> dict:
        if not url.startswith(ASSET_BASE_URL):
            # No es un asset del documento (logo, data: del QR). Pasa por la
            # allow-list, NO por el fetcher por defecto: delegar en él era un
            # SSRF y una lectura de archivos locales. Ver `safe_url_fetcher`.
            # No se registra en `failures` porque no es un asset del documento
            # y no debe abortar el freeze.
            return safe_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)

        rel = unquote(urlparse(url).path).lstrip("/")
        try:
            data = self._read(rel)
        except Exception as exc:
            self.failures[url] = f"{type(exc).__name__}: {exc}"
            logger.warning("No se pudo resolver el asset %s del documento: %s", rel, exc)
            # Se lanza igual: WeasyPrint la omite y sigue, pero el registro de
            # arriba es lo que después permite abortar el freeze.
            raise AssertionError(f"asset no resuelto: {rel}") from exc

        suffix = PurePosixPath(rel).suffix.lower()
        self.resolved[url] = suffix in _RASTER_SUFFIXES
        return {
            "string": data,
            "mime_type": _MIME_BY_SUFFIX.get(suffix, "application/octet-stream"),
        }

    # ── Resolución ───────────────────────────────────────────────────────────

    def _read(self, rel: str) -> bytes:
        from process_ai_core.storage import get_storage, run_artifact_key, workspace_prefix

        if not self.workspace_id:
            raise AssetResolutionError("sin workspace_id no se puede resolver el asset")

        version_asset = _VERSION_ASSET_RE.match(rel)
        if version_asset:
            from process_ai_core.storage.keys import version_prefix

            prefijo = version_prefix(
                self.workspace_id, version_asset["document_id"], version_asset["version_id"]
            )
            return get_storage().get(f"{prefijo}/assets/{version_asset['filename']}")

        editor = _EDITOR_IMAGE_RE.match(rel)
        if editor:
            key = (
                f"{workspace_prefix(self.workspace_id)}/editor-uploads/"
                f"{editor['document_id']}/{editor['filename']}"
            )
            return get_storage().get(key)

        if rel.startswith("assets/"):
            if not self.run_id:
                raise AssetResolutionError(
                    f"la versión no tiene run_id: no se puede ubicar {rel}"
                )
            return get_storage().get(run_artifact_key(self.workspace_id, self.run_id, rel))

        raise AssetResolutionError(f"ruta de asset no reconocida: {rel}")

    # ── Reporte ──────────────────────────────────────────────────────────────

    @property
    def expected_raster_count(self) -> int:
        """Cuántos XObjects de imagen debería tener el PDF por estos assets."""
        return sum(1 for es_raster in self.resolved.values() if es_raster)
