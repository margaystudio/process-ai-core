"""
Inyección de referencias de imágenes estructuradas en el JSON de un documento.

El `json_str` que produce el LLM no incluye las imágenes (evidencia + frames de
video). Estas se calculan aparte (`media.enrich_assets`) y hasta ahora solo iban al
Markdown como paths relativos. Para que el RAG y el asistente proactivo puedan asociar
"esta captura ↔ este paso", las agregamos al JSON de forma estructurada.

Es genérico: aplica a cualquier dominio que pase por el engine (procesos, recetas).

Estructura agregada (clave `assets`):

    "assets": {
      "images_by_step": {
        "1": [{"asset_id": "...", "path": "assets/...", "title": "..."}],
        "5": [...]
      },
      "evidence_images": [{"asset_id": "...", "path": "assets/...", "title": "..."}]
    }

- `asset_id`: identificador estable derivado del nombre de archivo (stem). Junto con
  el `run_id`, la ruta `assets/...` es la referencia canónica en object storage.
- Paso `0` en images_by_step = capturas sin paso asignado.
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional


def _asset_entry(img: Dict[str, str]) -> Optional[Dict[str, str]]:
    path = (img.get("path") or "").strip()
    if not path:
        return None
    asset_id = PurePosixPath(path).stem
    title = (img.get("title") or "").strip()
    return {"asset_id": asset_id, "path": path, "title": title}


def build_assets_block(
    images_by_step: Optional[Dict[int, List[Dict[str, str]]]],
    evidence_images: Optional[List[Dict[str, str]]],
) -> Dict[str, Any]:
    """Construye el bloque `assets` estructurado (imagen↔paso + evidencia)."""
    by_step: Dict[str, List[Dict[str, str]]] = {}
    for step_n, imgs in (images_by_step or {}).items():
        entries = [e for e in (_asset_entry(i) for i in (imgs or [])) if e]
        if entries:
            by_step[str(int(step_n))] = entries

    evidence = [e for e in (_asset_entry(i) for i in (evidence_images or [])) if e]

    return {"images_by_step": by_step, "evidence_images": evidence}


def inject_assets_into_json(
    json_str: str,
    images_by_step: Optional[Dict[int, List[Dict[str, str]]]],
    evidence_images: Optional[List[Dict[str, str]]],
) -> str:
    """
    Devuelve `json_str` enriquecido con el bloque `assets`. Best-effort: si el JSON no
    parsea, devuelve el original sin tocar (no rompe el pipeline).
    """
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return json_str
    except (json.JSONDecodeError, TypeError):
        return json_str

    data["assets"] = build_assets_block(images_by_step, evidence_images)
    return json.dumps(data, ensure_ascii=False, indent=2)
