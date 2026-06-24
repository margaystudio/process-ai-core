from __future__ import annotations

"""
process_ai_core.engine
======================

Orquestador de alto nivel del pipeline de documentación (genérico).

Este módulo expone una **API interna** y estable para correr el flujo completo
del core (ingest → enrich → LLM → parse → render), sin preocuparse por:

- HTTP
- frameworks web
- detalles de CLI
- dominio específico (procesos, recetas, etc.)

La idea es que:

- CLI simples (`cli.py`, `tools/run_demo.py`) usen estas funciones.
- Futuras APIs HTTP (FastAPI, etc.) también llamen a este módulo.
- La UI web NUNCA hable directo con `media.py` / `llm_client.py`, sino con una
  capa backend que use este engine.
- Cualquier dominio (procesos, recetas, etc.) puede usar el engine genérico.
"""

from pathlib import Path
from typing import Any, Dict, List, Sequence, TypedDict

from .assets_json import inject_assets_into_json
from .core.abstractions import DocumentBuilder, DocumentRenderer
from .domain_models import EnrichedAsset, RawAsset
from .llm_client import generate_document_json
from .media import enrich_assets


class DocumentRunResult(TypedDict):
    """
    Resultado de una corrida completa del pipeline (genérico).

    Esta estructura es deliberadamente simple y serializable, pensada para:
    - Devolver datos a una capa HTTP.
    - Guardar JSON/Markdown en base de datos o storage.
    - Realizar asserts en tests de integración.
    """

    json_str: str
    """JSON crudo devuelto por el LLM (string)."""

    doc: Any
    """Documento parseado (fuente de verdad tipada, específico del dominio)."""

    markdown: str
    """Markdown final renderizado según el perfil indicado."""

    images_by_step: Dict[int, List[Dict[str, str]]]
    """Capturas inferidas desde video, agrupadas por número de paso."""

    evidence_images: List[Dict[str, str]]
    """Imágenes sueltas de evidencia aportadas por el usuario."""

    enriched_assets: List[EnrichedAsset]
    """Assets enriquecidos (incluyen extracted_text/transcripción) para el manifiesto."""


def run_documentation_pipeline(
    *,
    document_name: str,
    raw_assets: Sequence[RawAsset],
    builder: DocumentBuilder,
    renderer: DocumentRenderer,
    profile: Any,  # Perfil específico del dominio
    context_block: str | None = None,
    output_base: Path | None = None,
) -> DocumentRunResult:
    """
    Ejecuta el pipeline genérico de documentación (funciona para cualquier dominio).

    Flujo:
    ------
    1) Enriquecimiento de assets (`media.enrich_assets`):
       - audio  → transcripción
       - video  → transcripción + pasos + capturas
       - image  → evidencia visual
       - text   → lectura directa

    2) Construcción de prompt:
       - `builder.build_prompt(document_name, enriched_assets)`
       - opcionalmente se antepone `context_block` si se provee.

    3) Llamada al LLM:
       - `generate_document_json(prompt, builder.get_system_prompt())` → JSON.

    4) Parsing:
       - `builder.parse_document(json_str)` → modelo tipado del dominio.

    5) Render:
       - `renderer.render_markdown(doc, profile, images_by_step, evidence_images)` → Markdown.

    Args:
        document_name:
            Nombre del documento (ej: "Proceso X", "Receta Y").
        raw_assets:
            Lista de `RawAsset` descubiertos.
        builder:
            Builder específico del dominio (implementa DocumentBuilder).
        renderer:
            Renderer específico del dominio (implementa DocumentRenderer).
        profile:
            Perfil de renderizado específico del dominio.
        context_block:
            Bloque de texto opcional para anteponer al prompt principal.
        output_base:
            Directorio base para validar rutas de imágenes.

    Returns:
        DocumentRunResult:
            Diccionario tipado con JSON, modelo parseado, Markdown y metadatos de imágenes.
    """
    # 1) Enriquecer assets (genérico)
    enriched, images_by_step, evidence_images = enrich_assets(
        list(raw_assets), output_base=output_base
    )
    # Asegurar que siempre sean dict/list (no None)
    images_by_step = images_by_step or {}
    evidence_images = evidence_images or []

    # 2) Construir prompt (específico del dominio)
    prompt_body = builder.build_prompt(document_name, enriched)
    prompt = f"{context_block}{prompt_body}" if context_block else prompt_body

    # 3) LLM → JSON (genérico, pero usa system prompt del dominio)
    json_str = generate_document_json(
        prompt=prompt,
        system_prompt=builder.get_system_prompt(),
    )

    # 4) Parsear (específico del dominio). Se parsea ANTES de enriquecer el JSON con
    #    imágenes para que el modelo del dominio no dependa del bloque `assets`.
    doc = builder.parse_document(json_str)

    # 4.b) Enriquecer el JSON con las imágenes estructuradas (imagen↔paso + evidencia)
    #      para que el content_json sea consumible por el RAG / asistente.
    json_str = inject_assets_into_json(json_str, images_by_step, evidence_images)

    # 5) Renderizar (específico del dominio)
    markdown = renderer.render_markdown(
        document=doc,
        profile=profile,
        images_by_step=images_by_step or {},
        evidence_images=evidence_images or [],
        output_base=output_base,
    )

    return DocumentRunResult(
        json_str=json_str,
        doc=doc,
        markdown=markdown,
        images_by_step=images_by_step,
        evidence_images=evidence_images,
        enriched_assets=list(enriched),
    )


# ============================================================
# Funciones de compatibilidad (procesos)
# ============================================================


def run_process_pipeline(
    *,
    process_name: str,
    raw_assets: Sequence[RawAsset],
    profile: Any,  # DocumentProfile
    context_block: str | None = None,
    output_base: Path | None = None,
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline de documentación de procesos (función de compatibilidad).

    Esta función mantiene compatibilidad con código existente.
    Internamente usa `run_documentation_pipeline` con el builder/renderer de procesos.

    Args:
        process_name:
            Nombre del proceso.
        raw_assets:
            Lista de `RawAsset` descubiertos.
        profile:
            `DocumentProfile` que controla cómo se renderiza el Markdown.
        context_block:
            Bloque de texto opcional para anteponer al prompt principal.
        output_base:
            Directorio base para validar rutas de imágenes.

    Returns:
        Dict con JSON, modelo parseado, Markdown y metadatos de imágenes.
    """
    from .domains.processes.builder import ProcessBuilder
    from .domains.processes.renderer import ProcessRenderer

    builder = ProcessBuilder()
    renderer = ProcessRenderer()

    result = run_documentation_pipeline(
        document_name=process_name,
        raw_assets=raw_assets,
        builder=builder,
        renderer=renderer,
        profile=profile,
        context_block=context_block,
        output_base=output_base,
    )

    # Mantener compatibilidad con el tipo ProcessRunResult
    return {
        "json_str": result["json_str"],
        "doc": result["doc"],
        "markdown": result["markdown"],
        "images_by_step": result["images_by_step"],
        "evidence_images": result["evidence_images"],
        "enriched_assets": result["enriched_assets"],
    }


# Alias para compatibilidad
ProcessRunResult = DocumentRunResult


# ============================================================
# Funciones de compatibilidad (recetas)
# ============================================================

def run_recipe_pipeline(
    *,
    recipe_name: str,
    raw_assets: Sequence[RawAsset],
    profile: Any,  # RecipeProfile
    context_block: str | None = None,
    output_base: Path | None = None,
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline de documentación de recetas (función de compatibilidad).

    Esta función permite usar el engine genérico con el dominio de recetas.
    Internamente usa `run_documentation_pipeline` con el builder/renderer de recetas.

    Args:
        recipe_name:
            Nombre de la receta.
        raw_assets:
            Lista de `RawAsset` descubiertos.
        profile:
            `RecipeProfile` que controla cómo se renderiza el Markdown.
        context_block:
            Bloque de texto opcional para anteponer al prompt principal.
        output_base:
            Directorio base para validar rutas de imágenes.

    Returns:
        Dict con JSON, modelo parseado, Markdown y metadatos de imágenes.
    """
    from .domains.recipes.builder import RecipeBuilder
    from .domains.recipes.renderer import RecipeRenderer

    builder = RecipeBuilder()
    renderer = RecipeRenderer()

    result = run_documentation_pipeline(
        document_name=recipe_name,
        raw_assets=raw_assets,
        builder=builder,
        renderer=renderer,
        profile=profile,
        context_block=context_block,
        output_base=output_base,
    )

    return {
        "json_str": result["json_str"],
        "doc": result["doc"],
        "markdown": result["markdown"],
        "images_by_step": result["images_by_step"],
        "evidence_images": result["evidence_images"],
        "enriched_assets": result["enriched_assets"],
    }
