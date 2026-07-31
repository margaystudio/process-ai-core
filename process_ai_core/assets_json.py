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
import logging
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def _asset_entry(img: Dict[str, str]) -> Optional[Dict[str, str]]:
    path = (img.get("path") or "").strip()
    if not path:
        return None
    asset_id = PurePosixPath(path).stem
    title = (img.get("title") or "").strip()
    entry = {"asset_id": asset_id, "path": path, "title": title}
    # La descripción de la imagen (generada con visión) es lo único de la imagen
    # que la capa semántica puede indexar. Va marcada como inferida: nadie la
    # escribió ni la validó (ADR-015).
    description = (img.get("description") or "").strip()
    if description:
        entry["description"] = description
        entry["description_confianza"] = "inferido"
    return entry


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


# ============================================================
# Numeración y asignación de imágenes a pasos
# ============================================================


def number_image_assets(enriched_assets: Sequence[Any]) -> Dict[int, Any]:
    """
    Numera los assets de imagen: `{1: asset, 2: asset, ...}`.

    Es una función PURA del orden de la lista, y por eso la puede llamar tanto el
    builder (que imprime "Imagen 3: ..." en el prompt) como el engine (que
    resuelve el "3" que devolvió el modelo). Si la numeración se calculara en un
    lado y se leyera en el otro, cualquier cambio en el armado del prompt
    desincronizaría las dos puntas en silencio: el modelo diría "paso 5 ↔ imagen
    3" y el pipeline pegaría otra imagen. El bug sería invisible.
    """
    return {
        n: asset
        for n, asset in enumerate(
            (a for a in enriched_assets if getattr(a, "kind", "") == "image"), start=1
        )
    }


def _image_entry_from_asset(asset: Any) -> Optional[Dict[str, str]]:
    """Entrada de `images_by_step` a partir de un EnrichedAsset de imagen."""
    metadata = getattr(asset, "metadata", None) or {}
    path = (metadata.get("path") or "").strip()
    if not path:
        return None
    return {
        "path": path,
        "title": (metadata.get("titulo") or "").strip(),
        "description": (metadata.get("descripcion") or "").strip(),
    }


def assign_referenced_images_to_steps(
    doc: Any,
    enriched_assets: Sequence[Any],
    images_by_step: Optional[Dict[int, List[Dict[str, str]]]] = None,
    *,
    origen: str = "pdf",
) -> Dict[int, List[Dict[str, str]]]:
    """
    Ubica en su paso las imágenes que el modelo referenció por número.

    Las capturas de video ya vienen con paso asignado (las infiere el pipeline de
    video). Las imágenes que salen de un PDF de entrada no: quién sabe a qué paso
    corresponde cada una es el modelo, que las tiene numeradas en el prompt junto
    con el texto que las rodeaba en el PDF. Acá se traduce ese número a la ruta
    del asset.

    Las que el modelo no referenció NO se tiran: van al paso 0, que el renderer
    imprime como "capturas adicionales (sin paso asignado)". Perder contenido en
    silencio es peor que imprimirlo diciendo que no se supo dónde ubicarlo.

    Args:
        origen: qué marca de `metadata["origen"]` es asignable a un paso. La
            evidencia suelta que aporta el usuario no lo es: ya tiene su propia
            sección y moverla cambiaría lo que el usuario pidió.
    """
    resultado: Dict[int, List[Dict[str, str]]] = {
        int(k): list(v) for k, v in (images_by_step or {}).items()
    }
    numerados = number_image_assets(enriched_assets)
    asignables = {
        n: a
        for n, a in numerados.items()
        if (getattr(a, "metadata", None) or {}).get("origen") == origen
    }
    if not asignables:
        return resultado

    referenciadas: set[int] = set()
    for paso in getattr(doc, "pasos", None) or []:
        orden = int(getattr(paso, "order", 0) or 0)
        for numero in getattr(paso, "imagenes", None) or []:
            try:
                numero = int(numero)
            except (TypeError, ValueError):
                continue
            asset = asignables.get(numero)
            if asset is None:
                # El modelo referenció una imagen que no existe o que no es
                # asignable. No se inventa nada: se loguea y se sigue.
                logger.info(
                    "El modelo referenció la imagen %s en el paso %s, que no "
                    "corresponde a ninguna imagen promovida; se ignora.",
                    numero, orden,
                )
                continue
            if numero in referenciadas:
                continue
            entrada = _image_entry_from_asset(asset)
            if entrada:
                resultado.setdefault(orden, []).append(entrada)
                referenciadas.add(numero)

    huerfanas = [a for n, a in sorted(asignables.items()) if n not in referenciadas]
    if huerfanas:
        logger.info(
            "%d imagen(es) de PDF sin paso asignado por el modelo: van a la "
            "sección de capturas adicionales.",
            len(huerfanas),
        )
        for asset in huerfanas:
            entrada = _image_entry_from_asset(asset)
            if entrada:
                resultado.setdefault(0, []).append(entrada)

    return resultado
