"""
Renderer para documentos de procesos.

Implementa DocumentRenderer para renderizar ProcessDocument a Markdown.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import ProcessDocument
from .profiles import DocumentProfile


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


class ProcessRenderer:
    """
    Renderer para documentos de procesos.
    
    Implementa la lógica específica de procesos para renderizar
    ProcessDocument a Markdown según un DocumentProfile.
    """

    def render_markdown(
        self,
        document: ProcessDocument,
        profile: DocumentProfile,
        images_by_step: Dict[int, List[Dict[str, str]]] | None = None,
        evidence_images: List[Dict[str, str]] | None = None,
        output_base: Path | None = None,
    ) -> str:
        """
        Renderiza el ProcessDocument a Markdown según el perfil indicado.
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
        lines.append(f"# {document.process_name}\n\n")

        # OBJETIVO
        if "objetivo" in profile.show:
            lines.append(f"## {title('objetivo', 'Objetivo')}\n\n")
            if document.objetivo.strip():
                lines.append(f"- {document.objetivo.strip()}\n")
            if "contexto" in profile.show and document.contexto.strip():
                lines.append(f"\n- Contexto: {document.contexto.strip()}\n")
            lines.append("\n")

        # CONTEXTO
        if "contexto" in profile.show and document.contexto.strip():
            lines.append(f"## {title('contexto', 'Contexto')}\n\n")
            lines.append(f"{document.contexto.strip()}\n\n")

        # ALCANCE
        if "alcance" in profile.show:
            lines.append(f"## {title('alcance', 'Alcance')}\n\n")
            if document.inicio.strip():
                lines.append(f"- Inicio: {document.inicio.strip()}\n")
            if document.fin.strip():
                lines.append(f"- Fin: {document.fin.strip()}\n")
            if document.incluidos.strip():
                lines.append(f"- Incluye: {document.incluidos.strip()}\n")
            if document.excluidos.strip():
                lines.append(f"- No incluye: {document.excluidos.strip()}\n")
            lines.append("\n")

        # FRECUENCIA
        if "frecuencia" in profile.show:
            lines.append(f"## {title('frecuencia', 'Frecuencia y disparadores')}\n\n")
            if document.frecuencia.strip():
                lines.append(f"- Frecuencia: {document.frecuencia.strip()}\n")
            if document.disparadores.strip():
                lines.append(f"- Disparadores: {document.disparadores.strip()}\n")
            lines.append("\n")

        # ACTORES
        if "actores" in profile.show and document.actores_resumen.strip():
            lines.append(f"## {title('actores', 'Actores y responsabilidades')}\n\n")
            lines.append(f"{document.actores_resumen.strip()}\n\n")

        # SISTEMAS / DATOS
        if "sistemas" in profile.show:
            lines.append(f"## {title('sistemas', 'Sistemas, datos y evidencias')}\n\n")
            if document.sistemas.strip():
                lines.append(f"- Sistemas: {document.sistemas.strip()}\n")
            if document.inputs.strip():
                lines.append(f"- Entradas: {document.inputs.strip()}\n")
            if document.outputs.strip():
                lines.append(f"- Salidas: {document.outputs.strip()}\n")
            lines.append("\n")

        # PASOS
        if "pasos" in profile.show:
            lines.append(f"## {title('pasos', 'Pasos')}\n\n")

            if profile.steps_format == "tabla":
                lines.append("| # | Actor | Acción | Input | Output | Riesgos |\n")
                lines.append("|---|-------|--------|-------|--------|--------|\n")
                for s in document.pasos:
                    action = s.action
                    if _has_capture(s.order):
                        action = f"{action} ({_cap_link(s.order)})"
                    lines.append(
                        f"| {s.order} | {s.actor} | {action} | {s.input} | {s.output} | {s.risks} |\n"
                    )
                lines.append("\n")
            else:
                for s in document.pasos:
                    header = f"**{s.order}. {s.action}**"
                    if _has_capture(s.order):
                        header += f" ({_cap_link(s.order)})"
                    lines.append(header + "\n")
                    if s.input.strip():
                        lines.append(f"- Entrada: {s.input.strip()}\n")
                    if s.output.strip():
                        lines.append(f"- Resultado: {s.output.strip()}\n")
                    if s.risks.strip() and "riesgos" in profile.show:
                        lines.append(f"- Riesgo: {s.risks.strip()}\n")
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
                    # \FloatBarrier fuerza que las imágenes anteriores se rendericen antes de continuar
                    lines.append(f"\\FloatBarrier\n")
                    lines.append(f"![{img_title}]({img['path']})\n\n")
                    lines.append(f"\\FloatBarrier\n\n")
                lines.append("---\n\n")

        # EVIDENCIA VISUAL (imágenes sueltas)
        if evidence_clean:
            lines.append(f"## {title('evidencia', 'Evidencia visual')}\n\n")
            lines.append(
                "Capturas aportadas como evidencia del proceso. "
                "La correspondencia exacta con un paso puede requerir validación.\n\n"
            )
            for img in evidence_clean:
                lines.append(f"![{img['title']}]({img['path']})\n\n")

        # RIESGOS / MÉTRICAS / OPORTUNIDADES
        if "riesgos" in profile.show and document.problemas.strip():
            lines.append(f"## {title('riesgos', 'Riesgos')}\n\n")
            lines.append(f"{document.problemas.strip()}\n\n")

        if "metricas" in profile.show and document.metricas.strip():
            lines.append(f"## {title('metricas', 'Indicadores')}\n\n")
            lines.append(f"{document.metricas.strip()}\n\n")

        if "oportunidades" in profile.show and document.oportunidades.strip():
            lines.append(f"## {title('oportunidades', 'Oportunidades de mejora')}\n\n")
            lines.append(f"{document.oportunidades.strip()}\n\n")

        # EXCEPCIONES
        if "excepciones" in profile.show:
            lines.append(f"## {title('excepciones', 'Excepciones')}\n\n")
            if document.excepciones.strip():
                lines.append(f"- {document.excepciones.strip()}\n")
            if document.variantes.strip():
                lines.append(f"- Variantes: {document.variantes.strip()}\n")
            lines.append("\n")

        # PREGUNTAS ABIERTAS
        if "preguntas_abiertas" in profile.show and document.preguntas_abiertas.strip():
            lines.append(f"## {title('preguntas_abiertas', 'Preguntas abiertas')}\n\n")
            lines.append(document.preguntas_abiertas.strip() + "\n\n")

        return "".join(lines)

