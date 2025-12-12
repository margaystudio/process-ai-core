from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from .models import RawAsset


AUDIO_EXT = {".m4a", ".mp3", ".wav"}
VIDEO_EXT = {".mp4", ".mov", ".mkv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXT  = {".txt", ".md"}


def _load_sidecar_metadata(file_path: Path) -> Dict[str, str]:
    """
    Busca un JSON al lado del archivo (mismo nombre, .json).
    Ej: video.mp4 -> video.json
    """
    sidecar = file_path.with_suffix(".json")
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        # Normalizamos a dict[str,str]
        return {str(k): "" if v is None else str(v) for k, v in data.items()}
    except Exception:
        # si el json está mal, mejor no romper el pipeline
        return {}


def _kind_from_ext(ext: str) -> str | None:
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


def discover_raw_assets(input_dir: Path) -> List[RawAsset]:
    """
    Descubre automáticamente assets en input/ subcarpetas y arma RawAsset.
    - Genera IDs estables por tipo: audio1, audio2, vid1, img1, text1...
    - Aplica sidecar metadata si existe.
    """
    input_dir = Path(input_dir)
    if not input_dir.exists():
        return []

    # Recolectamos (kind, path)
    found: List[Tuple[str, Path]] = []
    for p in input_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() == ".json":
            # sidecar, lo ignoramos como asset
            continue
        kind = _kind_from_ext(p.suffix)
        if kind:
            found.append((kind, p))

    # Orden estable (para IDs consistentes)
    found.sort(key=lambda t: (t[0], str(t[1]).lower()))

    counters = {"audio": 0, "video": 0, "image": 0, "text": 0}
    assets: List[RawAsset] = []

    for kind, path in found:
        counters[kind] += 1
        prefix = {"audio": "audio", "video": "vid", "image": "img", "text": "txt"}[kind]
        asset_id = f"{prefix}{counters[kind]}"

        meta = _load_sidecar_metadata(path)
        if "titulo" not in meta or not meta["titulo"].strip():
            meta["titulo"] = path.stem

        assets.append(
            RawAsset(
                id=asset_id,
                kind=kind,                 # Literal["audio","video","image","text"]
                path_or_url=str(path),
                metadata=meta,
            )
        )

    return assets