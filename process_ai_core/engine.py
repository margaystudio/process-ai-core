from __future__ import annotations

"""
process_ai_core.engine
======================

Orquestador de alto nivel del pipeline de documentación de procesos.

Este módulo expone una **API interna** y estable para correr el flujo completo
del core (ingest → enrich → LLM → parse → render), sin preocuparse por:

- HTTP
- frameworks web
- detalles de CLI

La idea es que:

- CLI simples (`cli.py`, `tools/run_demo.py`) usen estas funciones.
- Futuras APIs HTTP (FastAPI, etc.) también llamen a este módulo.
- La UI web NUNCA hable directo con `media.py` / `llm_client.py`, sino con una
  capa backend que use este engine.
"""

from typing import Dict, List, Sequence, TypedDict

from .document_profiles import DocumentProfile
from .domain_models import EnrichedAsset, ProcessDocument, RawAsset
from .doc_engine import (
    build_prompt_from_enriched,
    parse_process_document,
    render_markdown,
)
from .llm_client import generate_process_document_json
from .media import enrich_assets


class ProcessRunResult(TypedDict):
    """
    Resultado de una corrida completa del pipeline.

    Esta estructura es deliberadamente simple y serializable, pensada para:
    - Devolver datos a una capa HTTP.
    - Guardar JSON/Markdown en base de datos o storage.
    - Realizar asserts en tests de integración.
    """

    json_str: str
    """JSON crudo devuelto por el LLM (string)."""

    doc: ProcessDocument
    """Documento de proceso parseado (fuente de verdad tipada para el core)."""

    markdown: str
    """Markdown final renderizado según el perfil indicado."""

    images_by_step: Dict[int, List[Dict[str, str]]]
    """Capturas inferidas desde video, agrupadas por número de paso."""

    evidence_images: List[Dict[str, str]]
    """Imágenes sueltas de evidencia aportadas por el usuario."""


def run_process_pipeline(
    *,
    process_name: str,
    raw_assets: Sequence[RawAsset],
    profile: DocumentProfile,
    context_block: str | None = None,
) -> ProcessRunResult:
    """
    Ejecuta el pipeline principal de documentación de procesos (sin I/O de archivos).

    Flujo:
    ------
    1) Enriquecimiento de assets (`media.enrich_assets`):
       - audio  → transcripción
       - video  → transcripción + pasos + capturas
       - image  → evidencia visual
       - text   → lectura directa

    2) Construcción de prompt:
       - `build_prompt_from_enriched(process_name, enriched_assets)`
       - opcionalmente se antepone `context_block` si se provee.

    3) Llamada al LLM:
       - `generate_process_document_json(prompt)` → JSON con el documento.

    4) Parsing:
       - `parse_process_document(json_str)` → `ProcessDocument`.

    5) Render:
       - `render_markdown(doc, profile, images_by_step, evidence_images)` → Markdown.

    NOTA IMPORTANTE:
    ----------------
    - Esta función NO escribe archivos en disco.
    - El export a PDF (Pandoc) y la persistencia quedan a cargo de la capa llamadora
      (CLI, API HTTP, scripts, etc.).

    Args:
        process_name:
            Nombre humano del proceso (se usa en el prompt y en el título del documento).
        raw_assets:
            Lista de `RawAsset` descubiertos (desde filesystem, upload, DB, etc.).
        profile:
            `DocumentProfile` que controla cómo se renderiza el Markdown (operativo/gestión).
        context_block:
            Bloque de texto opcional para anteponer al prompt principal. Suele provenir
            de catálogos/DB (`prompt_context.build_context_block`) o de preferencias
            elegidas en la UI.

    Returns:
        ProcessRunResult:
            Diccionario tipado con JSON, modelo parseado, Markdown y metadatos de imágenes.
    """
    # 1) Enriquecer assets
    enriched, images_by_step, evidence_images = enrich_assets(list(raw_assets))

    # 2) Construir prompt
    prompt_body = build_prompt_from_enriched(process_name, enriched)
    prompt = f"{context_block}{prompt_body}" if context_block else prompt_body

    # 3) LLM → JSON
    json_str = generate_process_document_json(prompt)

    # 4) Parse a modelo tipado
    doc = parse_process_document(json_str)

    # 5) Render Markdown final
    markdown = render_markdown(
        doc,
        profile,
        images_by_step=images_by_step,
        evidence_images=evidence_images,
    )

    return ProcessRunResult(
        json_str=json_str,
        doc=doc,
        markdown=markdown,
        images_by_step=images_by_step,
        evidence_images=evidence_images,
    )


