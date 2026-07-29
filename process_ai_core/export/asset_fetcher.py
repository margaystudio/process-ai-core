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
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

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


class AssetResolutionError(RuntimeError):
    """Un asset referenciado por el documento no se pudo resolver."""


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
            # Recurso externo (file:// del logo, data:, http de otro dominio):
            # se delega al fetcher por defecto. No se registra porque no es un
            # asset del documento.
            from weasyprint import default_url_fetcher

            return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)

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
