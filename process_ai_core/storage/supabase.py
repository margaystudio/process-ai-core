"""
Implementación de `BlobStorage` sobre Supabase Storage.

Usa el cliente `supabase` (ya es dependencia) con la service-role key, de modo
que el backend tiene acceso completo al bucket (la autorización por tenant la
hace la app vía las claves canónicas que incluyen `workspace_id` + la firma
HMAC del endpoint de artefactos, no las RLS del bucket).

Config requerida (process_ai_core/config.py):
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_STORAGE_BUCKET
"""

from __future__ import annotations

from .base import BlobInfo, BlobStorage, StorageError, normalize_key


class SupabaseStorage(BlobStorage):
    def __init__(self, url: str, service_role_key: str, bucket: str):
        if not url or not service_role_key:
            raise StorageError(
                "SupabaseStorage requiere SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY."
            )
        if not bucket:
            raise StorageError("SupabaseStorage requiere SUPABASE_STORAGE_BUCKET.")
        # Import tardío para no pagar el costo si el backend no se usa.
        from supabase import create_client

        self._client = create_client(url, service_role_key)
        self._bucket = bucket

    @property
    def _store(self):
        return self._client.storage.from_(self._bucket)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        norm = normalize_key(key)
        # upsert=True para que re-subir la misma clave no falle (idempotente).
        self._store.upload(
            path=norm,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return norm

    def get(self, key: str) -> bytes:
        norm = normalize_key(key)
        try:
            return self._store.download(norm)
        except Exception as exc:  # el SDK lanza errores propios al no existir
            raise FileNotFoundError(f"Blob no encontrado: {key!r}") from exc

    def exists(self, key: str) -> bool:
        norm = normalize_key(key)
        # list() del directorio padre y buscar el nombre del archivo.
        if "/" in norm:
            parent, name = norm.rsplit("/", 1)
        else:
            parent, name = "", norm
        try:
            entries = self._store.list(path=parent)
        except Exception:
            return False
        return any(e.get("name") == name for e in (entries or []))

    def delete(self, key: str) -> None:
        norm = normalize_key(key)
        try:
            self._store.remove([norm])
        except Exception:
            # idempotente: borrar algo inexistente no es error
            pass

    def signed_url(self, key: str, ttl: int | None = None) -> str:
        norm = normalize_key(key)
        seconds = ttl if ttl is not None else 900
        res = self._store.create_signed_url(norm, seconds)
        url = res.get("signedURL") or res.get("signed_url")
        if not url:
            raise StorageError(f"No se pudo firmar URL para {key!r}")
        return url

    def list_objects(self, prefix: str = "") -> list[BlobInfo]:
        # El SDK lista un nivel por vez; recorremos el árbol. Las "carpetas" vienen
        # como entradas con id=None (sin metadata). Los archivos traen metadata.size.
        prefix = prefix.strip("/")
        out: list[BlobInfo] = []
        _PAGE = 1000

        def _walk(path: str) -> None:
            offset = 0
            while True:
                try:
                    entries = self._store.list(
                        path=path,
                        options={"limit": _PAGE, "offset": offset},
                    ) or []
                except Exception:
                    return
                for e in entries:
                    name = e.get("name")
                    if not name:
                        continue
                    child = f"{path}/{name}" if path else name
                    meta = e.get("metadata")
                    if e.get("id") is None or not meta:
                        # Carpeta: recursar
                        _walk(child)
                    else:
                        size = int(meta.get("size", 0) or 0)
                        out.append(BlobInfo(key=child, size=size))
                if len(entries) < _PAGE:
                    break
                offset += _PAGE

        _walk(prefix)
        return out
