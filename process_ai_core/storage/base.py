"""
Abstracción de almacenamiento de blobs (PDFs, imágenes, JSON/MD de export).

Desacopla el código del filesystem local. Dos implementaciones:
- `LocalDiskStorage`  → desarrollo/local/test (raíz en `output_dir`).
- `SupabaseStorage`   → producción (Supabase Storage, S3-compatible).

Toda interacción con artefactos pasa por esta interfaz, de modo que cambiar de
backend (o mover cierto tipo de blob a GCS más adelante) sea cambiar una
implementación sin tocar el resto del código.

Esquema de claves (key): rutas relativas estilo POSIX, sin barra inicial.
Las claves NUNCA deben contener `..` (se valida en `normalize_key`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class StorageError(RuntimeError):
    """Error genérico de la capa de almacenamiento."""


@dataclass(frozen=True)
class BlobInfo:
    """Metadata mínima de un blob para listados/contabilidad."""
    key: str
    size: int


def normalize_key(key: str) -> str:
    """
    Normaliza y valida una clave de blob.

    - Quita barras iniciales/finales redundantes.
    - Rechaza claves vacías, absolutas o con traversal (`..`).

    Raises:
        ValueError: si la clave es inválida (vacía o con `..`).
    """
    if not key or not key.strip():
        raise ValueError("La clave de blob no puede estar vacía.")
    cleaned = key.strip().lstrip("/")
    parts = [p for p in cleaned.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"Clave de blob inválida (traversal no permitido): {key!r}")
    if not parts:
        raise ValueError(f"Clave de blob inválida: {key!r}")
    return "/".join(parts)


class BlobStorage(ABC):
    """Interfaz mínima de almacenamiento de blobs por clave."""

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Sube `data` bajo `key`. Devuelve la clave normalizada almacenada."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Devuelve los bytes almacenados en `key`. Lanza `FileNotFoundError` si no existe."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True si existe un blob en `key`."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Borra el blob en `key`. No falla si no existe (idempotente)."""

    @abstractmethod
    def signed_url(self, key: str, ttl: int | None = None) -> str:
        """
        URL temporal directa al blob (cuando el backend lo soporta).

        Nota: el endpoint de artefactos sirve los bytes vía `get()` + firma HMAC
        propia (api/artifact_signing.py). Este método es para acceso directo
        opcional; backends que no lo soporten pueden lanzar NotImplementedError.
        """

    @abstractmethod
    def list_objects(self, prefix: str = "") -> list[BlobInfo]:
        """Lista (recursivo) todos los blobs bajo `prefix`, con su tamaño."""

    def usage_bytes(self, prefix: str = "") -> int:
        """Suma de tamaños (bytes) de todos los blobs bajo `prefix`."""
        return sum(b.size for b in self.list_objects(prefix))

    def delete_prefix(self, prefix: str) -> int:
        """Borra (recursivo) todos los blobs bajo `prefix`. Devuelve cuántos borró."""
        keys = [b.key for b in self.list_objects(prefix)]
        for k in keys:
            self.delete(k)
        return len(keys)
