from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PdfBranding:
    logo_path: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
