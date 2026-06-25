"""
Capa de almacenamiento de blobs (artefactos: PDF, imágenes, JSON/MD).

Uso típico:

    from process_ai_core.storage import get_storage, version_pdf_key

    storage = get_storage()
    key = version_pdf_key(workspace_id, document_id, version_id)
    storage.put(key, pdf_bytes, content_type="application/pdf")
"""

from .accounting import workspace_usage_bytes, workspace_usage_gb
from .base import BlobInfo, BlobStorage, StorageError, normalize_key
from .factory import get_storage
from .keys import (
    run_artifact_key,
    run_prefix,
    version_asset_key,
    version_pdf_key,
    version_prefix,
    workspace_prefix,
)
from .sync import sync_run_dir_to_storage

__all__ = [
    "BlobStorage",
    "BlobInfo",
    "StorageError",
    "normalize_key",
    "get_storage",
    "workspace_usage_bytes",
    "workspace_usage_gb",
    "workspace_prefix",
    "version_prefix",
    "version_pdf_key",
    "version_asset_key",
    "run_prefix",
    "run_artifact_key",
    "sync_run_dir_to_storage",
]
