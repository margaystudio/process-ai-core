"""
Sincronización del directorio de un run hacia BlobStorage.

El engine escribe los artefactos de un run (process.json/md/pdf + assets/...) a un
directorio local `output_dir/{run_id}/` porque necesita archivos locales para ffmpeg,
weasyprint, etc. Esta función sube ese directorio a object storage bajo la clave
`{run_id}/...`, de modo que el endpoint de artefactos (que lee vía BlobStorage) los
sirva también en producción (backend supabase).

Con el backend `local`, los archivos ya viven en la raíz del storage (output_dir),
así que es un no-op.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Tipos de archivo que se suben a storage (artefactos servibles).
_CONTENT_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def sync_run_dir_to_storage(run_id: str, run_dir: str | Path) -> int:
    """
    Sube todos los archivos servibles de `run_dir` a storage bajo `{run_id}/...`.

    Devuelve la cantidad de archivos subidos. Best-effort por archivo: loggea y sigue
    si alguno falla. No-op si el backend es `local` (ya están en la raíz del storage).
    """
    from process_ai_core.config import get_settings
    from .factory import get_storage

    if (get_settings().storage_backend or "local").lower() == "local":
        return 0

    run_dir = Path(run_dir)
    if not run_dir.exists():
        return 0

    storage = get_storage()
    uploaded = 0
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        # Subir SOLO artefactos servibles (json/md/pdf/imágenes). Los originales
        # pesados (video/audio fuente) y cualquier intermedio NO se persisten: el
        # diseño descarta los originales y guarda solo manifiesto + transcripción.
        content_type = _CONTENT_TYPES.get(path.suffix.lower())
        if content_type is None:
            continue
        rel = path.relative_to(run_dir).as_posix()
        key = f"{run_id}/{rel}"
        try:
            storage.put(key, path.read_bytes(), content_type=content_type)
            uploaded += 1
        except Exception as exc:
            logger.warning("sync_run_dir_to_storage: falló subir %s: %s", key, exc)
    logger.info("sync_run_dir_to_storage: %d archivos subidos para run %s", uploaded, run_id)
    return uploaded
