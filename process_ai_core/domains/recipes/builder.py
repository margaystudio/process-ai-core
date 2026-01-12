"""
Builder para documentos de recetas.

Implementa DocumentBuilder para construir prompts y parsear JSON de recetas.
"""

from __future__ import annotations

import json
from typing import List

from ...domain_models import EnrichedAsset, VideoRef
from .models import RecipeDocument, Ingredient, Instruction
from .prompts import get_recipe_doc_system_prompt


def _assets_summary(enriched_assets: List[EnrichedAsset]) -> str:
    """
    Construye un resumen explícito de activos disponibles.
    """
    buckets: dict[str, List[str]] = {"audio": [], "video": [], "image": [], "text": []}
    for a in enriched_assets:
        buckets.setdefault(a.kind, []).append(a.id)

    lines: List[str] = []
    lines.append("=== ACTIVOS DISPONIBLES (FUENTE DE VERDAD) ===")
    lines.append(f"- audio: {len(buckets.get('audio', []))} ({', '.join(buckets.get('audio', [])) or 'ninguno'})")
    lines.append(f"- video: {len(buckets.get('video', []))} ({', '.join(buckets.get('video', [])) or 'ninguno'})")
    lines.append(f"- image: {len(buckets.get('image', []))} ({', '.join(buckets.get('image', [])) or 'ninguna'})")
    lines.append(f"- text : {len(buckets.get('text', []))} ({', '.join(buckets.get('text', [])) or 'ninguno'})")
    lines.append(
        "Regla: solo podés referenciar activos listados arriba. "
        "Si un tipo está en cero, NO lo inventes.\n"
    )
    return "\n".join(lines)


class RecipeBuilder:
    """
    Builder para documentos de recetas.
    
    Implementa la lógica específica de recetas:
    - Construcción de prompts
    - Parsing de JSON a RecipeDocument
    """

    def build_prompt(
        self,
        document_name: str,
        enriched_assets: List[EnrichedAsset],
    ) -> str:
        """
        Construye el prompt completo para generar un documento de receta.
        """
        audios = [a for a in enriched_assets if a.kind == "audio"]
        textos = [a for a in enriched_assets if a.kind == "text"]
        imagenes = [a for a in enriched_assets if a.kind == "image"]
        videos = [a for a in enriched_assets if a.kind == "video"]

        # Debug visible (sirve para QA del pipeline)
        print("📦 Activos detectados:")
        print(f"  - audio: {len(audios)} ({', '.join(a.id for a in audios) or 'ninguno'})")
        print(f"  - video: {len(videos)} ({', '.join(a.id for a in videos) or 'ninguno'})")
        print(f"  - image: {len(imagenes)} ({', '.join(a.id for a in imagenes) or 'ninguna'})")
        print(f"  - text : {len(textos)} ({', '.join(a.id for a in textos) or 'ninguno'})")
        print("-" * 60)

        parts: List[str] = []
        parts.append(f"Receta: {document_name}\n")
        parts.append(_assets_summary(enriched_assets))

        # --- AUDIO/VIDEO ---
        if audios or videos:
            parts.append("=== TRANSCRIPCIÓN (FUENTE ORAL/VIDEO) ===")
            for asset in audios + videos:
                header = f"[{asset.kind.upper()} {asset.id}]"
                meta = ", ".join(f"{k}={v}" for k, v in asset.metadata.items())
                if meta:
                    header += f" ({meta})"
                parts.append(header)
                parts.append(asset.extracted_text)
                parts.append("")
            parts.append("")

        # --- TEXTO ---
        if textos:
            parts.append("=== NOTAS / INSTRUCCIONES ESCRITAS ===")
            for asset in textos:
                header = f"[TEXT {asset.id}]"
                meta = ", ".join(f"{k}={v}" for k, v in asset.metadata.items())
                if meta:
                    header += f" ({meta})"
                parts.append(header)
                parts.append(asset.extracted_text)
                parts.append("")
            parts.append("")

        # --- IMÁGENES (referencia) ---
        if imagenes:
            parts.append("=== IMAGENES DISPONIBLES (REFERENCIA) ===")
            parts.append(
                "Reglas:\n"
                "- Si se proveen imagenes, usalas como referencia visual (ingredientes, plato final, técnicas).\n"
                "- En las instrucciones, referencialas como '(ver evidencia visual)' o '(ver captura)' cuando aplique.\n"
                "- NO generes Markdown de imágenes en la respuesta JSON: el sistema las inserta en el Markdown final.\n"
            )
            parts.append("")
            for idx, asset in enumerate(imagenes, start=1):
                titulo = asset.metadata.get("titulo") or asset.metadata.get("title") or f"Imagen {idx}"
                parts.append(f"Imagen {idx}: id={asset.id} titulo={titulo}")
                parts.append(f"Referencia: {asset.extracted_text}")
                parts.append("")
            parts.append("")

        # --- VIDEO (referencia) ---
        if videos:
            parts.append("=== VIDEOS DISPONIBLES (REFERENCIA) ===")
            parts.append(
                "Reglas:\n"
                "- Si se proveen videos, agregalos en el campo JSON 'videos'.\n"
                "- Si hay URL en metadata, usala como 'url'.\n"
                "- En las instrucciones, referenciá '(ver video)' cuando aplique.\n"
            )
            parts.append("")
            for asset in videos:
                header = f"[VIDEO {asset.id}]"
                meta = ", ".join(f"{k}={v}" for k, v in asset.metadata.items())
                if meta:
                    header += f" ({meta})"
                parts.append(header)
                parts.append(asset.extracted_text)
                parts.append("")
            parts.append("")

        return "\n".join(parts)

    def parse_document(self, json_str: str) -> RecipeDocument:
        """
        Parsea el JSON devuelto por el LLM a un RecipeDocument.
        """
        data = json.loads(json_str)

        # Parsear ingredientes
        ingredients: List[Ingredient] = []
        for ing in data.get("ingredients", []):
            ingredients.append(
                Ingredient(
                    name=str(ing.get("name", "")).strip(),
                    quantity=str(ing.get("quantity", "")).strip(),
                    unit=str(ing.get("unit", "")).strip(),
                    notes=str(ing.get("notes", "")).strip(),
                )
            )

        # Parsear instrucciones
        instructions: List[Instruction] = []
        for inst in data.get("instructions", []):
            instructions.append(
                Instruction(
                    order=int(inst.get("order", 0) or 0),
                    instruction=str(inst.get("instruction", "")).strip(),
                    duration=str(inst.get("duration", "")).strip() or None,
                    temperature=str(inst.get("temperature", "")).strip() or None,
                    tips=str(inst.get("tips", "")).strip(),
                )
            )

        # Parsear videos
        videos: List[VideoRef] = []
        for v in data.get("videos", []):
            videos.append(
                VideoRef(
                    title=str(v.get("title", "")).strip(),
                    url=str(v.get("url", "")).strip() or None,
                    duration=str(v.get("duration", "")).strip() or None,
                    description=str(v.get("description", "")).strip() or None,
                )
            )

        return RecipeDocument(
            recipe_name=str(data.get("recipe_name", "")).strip(),
            description=str(data.get("description", "")).strip(),
            cuisine=str(data.get("cuisine", "")).strip(),
            difficulty=str(data.get("difficulty", "")).strip(),
            servings=int(data.get("servings", 0) or 0),
            prep_time=str(data.get("prep_time", "")).strip(),
            cook_time=str(data.get("cook_time", "")).strip(),
            total_time=str(data.get("total_time", "")).strip(),
            ingredients=ingredients,
            instructions=instructions,
            tips=str(data.get("tips", "")).strip(),
            variations=str(data.get("variations", "")).strip(),
            storage=str(data.get("storage", "")).strip(),
            nutritional_info=str(data.get("nutritional_info", "")).strip(),
            equipment=str(data.get("equipment", "")).strip(),
            videos=videos,
        )

    def get_system_prompt(self) -> str:
        """
        Devuelve el prompt del sistema para recetas.
        """
        return get_recipe_doc_system_prompt(language_style="es_uy")



