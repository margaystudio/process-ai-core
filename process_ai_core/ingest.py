from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from .domain_models import RawAsset

"""
process_ai_core.ingest
======================

Módulo de ingestión de insumos (input → RawAsset).

Responsabilidad
----------------
Este módulo se encarga exclusivamente de:

- Explorar la carpeta `input/`
- Detectar archivos soportados (audio, video, imagen, texto)
- Inferir su tipo a partir de la extensión
- Cargar metadata opcional desde archivos sidecar `.json`
- Construir objetos `RawAsset` con IDs estables

NO hace:
---------
- Transcripción
- Procesamiento multimedia
- Llamadas a LLM
- Copia a output/
- Render de documentos

Eso ocurre en etapas posteriores del pipeline (`media.enrich_assets`, etc).

Diseño
------
- Determinista: mismo input → mismos IDs
- Tolerante a errores: sidecars inválidos no rompen el flujo
- Simple: filesystem como fuente de verdad
"""

# ============================================================
# Extensiones soportadas
# ============================================================

AUDIO_EXT = {".m4a", ".mp3", ".wav"}
VIDEO_EXT = {".mp4", ".mov", ".mkv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXT  = {".txt", ".md"}


# ============================================================
# Helpers
# ============================================================

def _load_sidecar_metadata(file_path: Path) -> Dict[str, str]:
    """
    Carga metadata desde un archivo sidecar JSON, si existe.

    Convención:
    -----------
    - El sidecar debe llamarse igual que el archivo principal,
      pero con extensión `.json`.

    Ejemplo:
    --------
        video.mp4
        video.json

    El contenido del JSON se interpreta como metadata libre
    (clave → valor) asociada al asset.

    Reglas:
    -------
    - Si el sidecar no existe → retorna {}
    - Si el JSON está mal formado → retorna {}
    - Todos los valores se normalizan a string

    Esto permite agregar metadata sin romper el pipeline, por ejemplo:
    {
        "titulo": "Correr job en Cloud Run",
        "url": "https://console.cloud.google.com/...",
        "proceso": "GPU"
    }
    """
    sidecar = file_path.with_suffix(".json")
    if not sidecar.exists():
        return {}

    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        # Normalizamos todo a dict[str, str]
        return {
            str(k): "" if v is None else str(v)
            for k, v in data.items()
        }
    except Exception:
        # Error tolerante: no rompemos ingestión por un sidecar roto
        return {}


def _kind_from_ext(ext: str) -> str | None:
    """
    Devuelve el tipo lógico de asset a partir de la extensión.

    Retorna:
    --------
    - "audio" | "video" | "image" | "text"
    - None si la extensión no está soportada
    """
    ext = ext.lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in TEXT_EXT:
        return "text"
    return None


# ============================================================
# API pública
# ============================================================

def discover_raw_assets(input_dir: Path) -> List[RawAsset]:
    """
    Descubre automáticamente los insumos presentes en la carpeta `input/`
    y construye una lista de `RawAsset`.

    Flujo:
    ------
    1) Recorre recursivamente `input_dir`
    2) Ignora directorios y archivos `.json` (sidecars)
    3) Infere el tipo (`kind`) por extensión
    4) Ordena los resultados de forma estable
    5) Genera IDs secuenciales por tipo
    6) Aplica metadata desde sidecar (si existe)

    IDs:
    ----
    Los IDs se generan de forma determinista y por tipo:
        audio1, audio2, ...
        vid1, vid2, ...
        img1, img2, ...
        txt1, txt2, ...

    Esto es clave para:
    - reproducibilidad
    - referencias estables en logs y prompts
    - debugging

    Metadata:
    ---------
    - Se carga desde sidecar `.json` si existe
    - Si no hay `titulo`, se usa `path.stem`
    - Metadata queda libre para etapas posteriores

    Retorna:
    --------
    Lista de `RawAsset`.  
    Si `input_dir` no existe o está vacío → lista vacía.
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        return []

    # Recolectamos todos los archivos soportados
    found: List[Tuple[str, Path]] = []

    for p in input_dir.rglob("*"):
        if not p.is_file():
            continue

        # Ignoramos sidecars explícitamente
        if p.suffix.lower() == ".json":
            continue

        kind = _kind_from_ext(p.suffix)
        if kind:
            found.append((kind, p))

    # Orden estable → IDs consistentes entre corridas
    found.sort(key=lambda t: (t[0], str(t[1]).lower()))

    counters = {
        "audio": 0,
        "video": 0,
        "image": 0,
        "text": 0,
    }

    assets: List[RawAsset] = []

    for kind, path in found:
        counters[kind] += 1

        prefix = {
            "audio": "audio",
            "video": "vid",
            "image": "img",
            "text": "txt",
        }[kind]

        asset_id = f"{prefix}{counters[kind]}"

        meta = _load_sidecar_metadata(path)

        # Garantizamos siempre un título usable
        if "titulo" not in meta or not meta["titulo"].strip():
            meta["titulo"] = path.stem

        assets.append(
            RawAsset(
                id=asset_id,
                kind=kind,                # Literal["audio","video","image","text"]
                path_or_url=str(path),
                metadata=meta,
            )
        )

    return assets