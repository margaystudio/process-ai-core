"""
Construcción del manifiesto de fuentes de un run (Fase D).

Las fuentes crudas (audio/video/imágenes/texto) se borran tras generar el documento
(temp dir efímero). Para defensa de auditoría, antes de borrarlas registramos en
`Run.input_manifest_json` un manifiesto liviano: por cada fuente, su tipo, nombre,
tamaño y **SHA-256** — sin guardar los bytes pesados. Además se persiste el texto
extraído / transcripción (texto barato, evidencia real del contenido y futuro insumo
del RAG).

Estructura:

    {
      "sources": [
        {"id": "vid1", "kind": "video", "filename": "...", "size": 12345,
         "sha256": "...", "title": "...", "extracted_text": "..."},
        ...
      ],
      "captured_at": "2026-06-24T...Z"
    }
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def _sha256_of_file(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def build_input_manifest(
    raw_assets: Sequence[Any],
    enriched_assets: Optional[Sequence[Any]] = None,
    uploaded_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Construye el manifiesto a partir de los RawAsset (y EnrichedAsset si están).

    Args:
        raw_assets: lista de RawAsset (id, kind, path_or_url, metadata).
        enriched_assets: lista de EnrichedAsset (id, extracted_text) para adjuntar
                         la transcripción/texto extraído por id.
        uploaded_by: id del usuario que subió las fuentes (opcional).

    Returns:
        dict serializable para guardar en Run.input_manifest_json.
    """
    text_by_id: Dict[str, str] = {}
    for ea in enriched_assets or []:
        ea_id = getattr(ea, "id", None)
        text = getattr(ea, "extracted_text", "") or ""
        if ea_id:
            text_by_id[ea_id] = text

    sources: List[Dict[str, Any]] = []
    for a in raw_assets:
        path_or_url = getattr(a, "path_or_url", "") or ""
        metadata = getattr(a, "metadata", {}) or {}
        entry: Dict[str, Any] = {
            "id": getattr(a, "id", ""),
            "kind": getattr(a, "kind", ""),
            "title": metadata.get("titulo", ""),
        }

        p = Path(path_or_url)
        if path_or_url and not path_or_url.startswith(("http://", "https://")) and p.exists():
            entry["filename"] = p.name
            try:
                entry["size"] = p.stat().st_size
            except OSError:
                entry["size"] = None
            entry["sha256"] = _sha256_of_file(p)
        else:
            entry["filename"] = Path(path_or_url).name if path_or_url else ""
            entry["source_url"] = path_or_url if path_or_url.startswith(("http://", "https://")) else None

        text = text_by_id.get(entry["id"], "")
        if text:
            entry["extracted_text"] = text

        sources.append(entry)

    return {
        "sources": sources,
        "uploaded_by": uploaded_by,
        "captured_at": datetime.now(UTC).isoformat(),
    }


def build_input_manifest_json(
    raw_assets: Sequence[Any],
    enriched_assets: Optional[Sequence[Any]] = None,
    uploaded_by: Optional[str] = None,
) -> str:
    """Igual que build_input_manifest pero devuelve el string JSON listo para persistir."""
    return json.dumps(
        build_input_manifest(raw_assets, enriched_assets, uploaded_by),
        ensure_ascii=False,
    )
