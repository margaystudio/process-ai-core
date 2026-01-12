"""
Renderer para documentos de recetas.

Implementa DocumentRenderer para renderizar RecipeDocument a Markdown.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import RecipeDocument
from .profiles import RecipeProfile


def _norm_asset_path(p: str) -> str:
    """
    Normaliza rutas para que Pandoc resuelva bien desde cwd=output/.
    """
    p = (p or "").strip().replace("\\", "/")
    if not p:
        return ""

    marker = "/assets/"
    if marker in p:
        return "assets/" + p.split(marker, 1)[1]

    if p.startswith("output/assets/"):
        return p.replace("output/", "", 1)

    return p


class RecipeRenderer:
    """
    Renderer para documentos de recetas.
    
    Implementa la lógica específica de recetas para renderizar
    RecipeDocument a Markdown según un RecipeProfile.
    """

    def render_markdown(
        self,
        document: RecipeDocument,
        profile: RecipeProfile,
        images_by_step: Dict[int, List[Dict[str, str]]] | None = None,
        evidence_images: List[Dict[str, str]] | None = None,
        output_base: Path | None = None,
    ) -> str:
        """
        Renderiza el RecipeDocument a Markdown según el perfil indicado.
        """
        def title(key: str, fallback: str) -> str:
            t = (profile.titles.get(key, "") or "").strip()
            return t if t else fallback

        # ---------- Normalización y cache de capturas ----------
        captures_clean: Dict[int, List[Dict[str, str]]] = {}
        if images_by_step is not None:
            for k, imgs in images_by_step.items():
                step_n = int(k)
                valid: List[Dict[str, str]] = []
                for img in imgs or []:
                    path = _norm_asset_path(img.get("path", ""))
                    if not path:
                        continue
                    # Validar que la imagen existe si tenemos output_base
                    if output_base:
                        img_full_path = output_base / path
                        if not img_full_path.exists():
                            print(f"⚠️  Imagen no encontrada: {img_full_path} (ruta en markdown: {path})")
                            continue
                    cap_title = (img.get("title") or "").strip() or f"Captura paso {step_n}"
                    valid.append({"path": path, "title": cap_title})
                if valid:
                    captures_clean[step_n] = valid

        def _has_capture(step_n: int) -> bool:
            return bool(captures_clean.get(step_n))

        def _cap_link(step_n: int) -> str:
            return f"[ver captura](#cap-paso-{step_n})"

        # ---------- Evidencias sueltas ----------
        evidence_clean: List[Dict[str, str]] = []
        if evidence_images is not None:
            for i, img in enumerate(evidence_images, start=1):
                path = _norm_asset_path(img.get("path", ""))
                if not path:
                    continue
                # Validar que la imagen existe si tenemos output_base
                if output_base:
                    img_full_path = output_base / path
                    if not img_full_path.exists():
                        print(f"⚠️  Evidencia no encontrada: {img_full_path} (ruta en markdown: {path})")
                        continue
                ev_title = (img.get("title") or "").strip() or f"Evidencia {i}"
                evidence_clean.append({"path": path, "title": ev_title})

        # ---------- Render ----------
        lines: List[str] = []
        lines.append(f"# {document.recipe_name}\n\n")

        # DESCRIPCIÓN
        if "description" in profile.show and document.description.strip():
            lines.append(f"## {title('description', 'Descripción')}\n\n")
            lines.append(f"{document.description.strip()}\n\n")

        # INFORMACIÓN GENERAL
        if "info" in profile.show:
            lines.append(f"## {title('info', 'Información')}\n\n")
            if document.cuisine.strip():
                lines.append(f"- **Cocina**: {document.cuisine.strip()}\n")
            if document.difficulty.strip():
                lines.append(f"- **Dificultad**: {document.difficulty.strip()}\n")
            if document.servings > 0:
                lines.append(f"- **Porciones**: {document.servings}\n")
            if document.prep_time.strip():
                lines.append(f"- **Tiempo de preparación**: {document.prep_time.strip()}\n")
            if document.cook_time.strip():
                lines.append(f"- **Tiempo de cocción**: {document.cook_time.strip()}\n")
            if document.total_time.strip():
                lines.append(f"- **Tiempo total**: {document.total_time.strip()}\n")
            lines.append("\n")

        # EQUIPAMIENTO
        if "equipment" in profile.show and document.equipment.strip():
            lines.append(f"## {title('equipment', 'Equipamiento necesario')}\n\n")
            lines.append(f"{document.equipment.strip()}\n\n")

        # INGREDIENTES
        if "ingredients" in profile.show and document.ingredients:
            lines.append(f"## {title('ingredients', 'Ingredientes')}\n\n")
            for ing in document.ingredients:
                qty = ing.quantity.strip()
                unit = ing.unit.strip()
                qty_str = f"{qty} {unit}".strip() if qty or unit else ""
                if qty_str:
                    lines.append(f"- **{ing.name}**: {qty_str}")
                else:
                    lines.append(f"- **{ing.name}**")
                if ing.notes.strip():
                    lines.append(f" ({ing.notes.strip()})")
                lines.append("\n")
            lines.append("\n")

        # INSTRUCCIONES
        if "instructions" in profile.show and document.instructions:
            lines.append(f"## {title('instructions', 'Instrucciones')}\n\n")

            for inst in sorted(document.instructions, key=lambda x: x.order):
                header = f"**{inst.order}. {inst.instruction}**"
                if _has_capture(inst.order):
                    header += f" ({_cap_link(inst.order)})"
                lines.append(header + "\n")
                
                if inst.duration:
                    lines.append(f"- Tiempo: {inst.duration.strip()}\n")
                if inst.temperature:
                    lines.append(f"- Temperatura: {inst.temperature.strip()}\n")
                if inst.tips.strip():
                    lines.append(f"- 💡 Tip: {inst.tips.strip()}\n")
                lines.append("\n")

        # CAPTURAS DEL PROCEDIMIENTO (sección separada)
        if captures_clean:
            lines.append(f"## {title('capturas', 'Capturas del procedimiento')}\n\n")

            # Paso 0: capturas adicionales
            if 0 in captures_clean:
                lines.append("### Capturas adicionales (sin paso asignado)\n\n")
                for img in captures_clean[0]:
                    img_title = img.get("title", "").strip() or "Captura adicional"
                    lines.append(f"**{img_title}**\n\n")
                    lines.append(f"![{img_title}]({img['path']})\n\n")

            # Pasos 1..N: con ancla para link desde pasos
            for step_n in sorted(k for k in captures_clean.keys() if k != 0):
                anchor_id = f"cap-paso-{step_n}"
                lines.append(f"### Paso {step_n} {{#{anchor_id}}}\n\n")
                for img in captures_clean[step_n]:
                    img_title = img.get("title", "").strip() or f"Captura del paso {step_n}"
                    lines.append(f"**{img_title}**\n\n")
                    # Usar formato LaTeX para evitar que las imágenes floten
                    lines.append(f"\\FloatBarrier\n")
                    lines.append(f"![{img_title}]({img['path']})\n\n")
                    lines.append(f"\\FloatBarrier\n\n")
                lines.append("---\n\n")

        # EVIDENCIA VISUAL (imágenes sueltas)
        if evidence_clean:
            lines.append(f"## {title('evidencia', 'Evidencia visual')}\n\n")
            lines.append(
                "Fotos aportadas como evidencia de la receta. "
                "La correspondencia exacta con un paso puede requerir validación.\n\n"
            )
            for img in evidence_clean:
                lines.append(f"![{img['title']}]({img['path']})\n\n")

        # TIPS
        if "tips" in profile.show and document.tips.strip():
            lines.append(f"## {title('tips', 'Consejos y tips')}\n\n")
            lines.append(f"{document.tips.strip()}\n\n")

        # VARIACIONES
        if "variations" in profile.show and document.variations.strip():
            lines.append(f"## {title('variations', 'Variaciones')}\n\n")
            lines.append(f"{document.variations.strip()}\n\n")

        # ALMACENAMIENTO
        if "storage" in profile.show and document.storage.strip():
            lines.append(f"## {title('storage', 'Conservación y almacenamiento')}\n\n")
            lines.append(f"{document.storage.strip()}\n\n")

        # INFORMACIÓN NUTRICIONAL
        if "nutritional_info" in profile.show and document.nutritional_info.strip():
            lines.append(f"## {title('nutritional_info', 'Información nutricional')}\n\n")
            lines.append(f"{document.nutritional_info.strip()}\n\n")

        # VIDEOS
        if "videos" in profile.show and document.videos:
            lines.append(f"## {title('videos', 'Videos relacionados')}\n\n")
            for v in document.videos:
                lines.append(f"### {v.title}\n\n")
                if v.description:
                    lines.append(f"{v.description.strip()}\n\n")
                if v.url:
                    lines.append(f"🔗 [Ver video]({v.url})\n\n")
                if v.duration:
                    lines.append(f"⏱️ Duración: {v.duration}\n\n")
                lines.append("---\n\n")

        return "".join(lines)



