"""
Capa de almacenamiento de blobs (artefactos: PDF, imágenes, JSON/MD).

Uso típico:

    from process_ai_core.storage import get_storage, version_pdf_key

    storage = get_storage()
    key = version_pdf_key(workspace_id, document_id, version_id)
    storage.put(key, pdf_bytes, content_type="application/pdf")
"""

from .base import BlobStorage, StorageError, normalize_key
from .factory import get_storage
from .keys import version_asset_key, version_pdf_key, version_prefix
from .sync import sync_run_dir_to_storage

__all__ = [
    "BlobStorage",
    "StorageError",
    "normalize_key",
    "get_storage",
    "version_prefix",
    "version_pdf_key",
    "version_asset_key",
    "sync_run_dir_to_storage",
]
