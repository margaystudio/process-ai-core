"""
Implementación de `BlobStorage` sobre el filesystem local.

Raíz configurable (por defecto `output_dir`). Las claves se mapean a
`{root}/{key}`. Preserva el comportamiento actual del módulo (artefactos en
`output/{run_id}/{filename}`) cuando la clave es `{run_id}/{filename}`.
"""

from __future__ import annotations

from pathlib import Path

from .base import BlobStorage, normalize_key


class LocalDiskStorage(BlobStorage):
    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        norm = normalize_key(key)
        path = (self._root / norm).resolve()
        # Defensa en profundidad: el path resuelto debe quedar dentro de root.
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"Clave fuera de la raíz de storage: {key!r}") from exc
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return normalize_key(key)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(f"Blob no encontrado: {key!r}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def signed_url(self, key: str, ttl: int | None = None) -> str:
        # El backend local no expone URLs directas; los artefactos se sirven
        # vía el endpoint firmado de la API. Devolvemos la ruta interna.
        return f"file://{self._path(key)}"
