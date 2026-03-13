"""Shared upload validation constants used by API routes."""

from __future__ import annotations

from typing import Dict, FrozenSet

from .ingest import AUDIO_EXT, IMAGE_EXT, TEXT_EXT, VIDEO_EXT

ALLOWED_UPLOAD_EXTENSIONS: Dict[str, FrozenSet[str]] = {
    "audio": frozenset(AUDIO_EXT),
    "video": frozenset(VIDEO_EXT),
    "image": frozenset(IMAGE_EXT),
    "text": frozenset(TEXT_EXT),
}
