"""
Selección del backend de almacenamiento según configuración.

`get_storage()` devuelve una instancia única (cacheada) de `BlobStorage`
según `STORAGE_BACKEND` (local | supabase).
"""

from __future__ import annotations

from functools import lru_cache

from .base import BlobStorage, StorageError


@lru_cache
def get_storage() -> BlobStorage:
    from process_ai_core.config import get_settings

    settings = get_settings()
    backend = (settings.storage_backend or "local").lower()

    if backend == "local":
        from .local import LocalDiskStorage

        return LocalDiskStorage(root=settings.output_dir)

    if backend == "supabase":
        from .supabase import SupabaseStorage

        return SupabaseStorage(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_storage_bucket,
        )

    raise StorageError(
        f"STORAGE_BACKEND desconocido: {backend!r}. Use 'local' o 'supabase'."
    )
