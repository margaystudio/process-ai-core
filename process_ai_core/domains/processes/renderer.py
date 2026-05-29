"""Renderizado Markdown para documentos de procesos."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .models import ProcessDocument
from .profiles import DocumentProfile


def _norm_asset_path(p: str) -> str:
    """
    Normaliza rutas para que Pandoc resuelva bien desde cwd=output/.

    Casos soportados:
      - ".../output/assets/xxx.png" -> "assets/xxx.png"
      - "output/assets/xxx.png"     -> "assets/xxx.png"
      - "/algo/assets/xxx.png"      -> "assets/xxx.png" (best effort)
      - "assets/xxx.png"            -> "assets/xxx.png"

    Args:
        p: Ruta original.

    Returns:
        Ruta normalizada, o "" si p es vacía.
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


# ============================================================
# Rendering
# ============================================================

def render_markdown(
    doc: ProcessDocument,
    profile: DocumentProfile,
    images_by_step: Optional[Dict[int, List[Dict[str, str]]]] = None,
    evidence_images: Optional[List[Dict[str, str]]] = None,
    output_base: Optional[Path] = None,
) -> str:
    """
    Renderiza el Markdown final aplicando un DocumentProfile.

    Estructura:
      - Secciones controladas por profile.show y profile.titles.
      - Pasos: tabla o lista según profile.steps_format.
      - Capturas (images_by_step): sección separada con anclas por paso.
      - Evidencia visual (evidence_images): sección separada.

    Comportamiento de capturas:
      - Si images_by_step tiene paso N, entonces en el paso N se agrega un link
        "(ver captura)" que salta a la subsección correspondiente.
      - Si existe la clave 0 en images_by_step, se trata como "capturas adicionales"
        (sin paso asignado).

    Args:
        doc: ProcessDocument parseado.
        profile: DocumentProfile (operativo/gestión).
        images_by_step: dict { paso: [ {"path": "...", "title": "..."} ] }.
        evidence_images: lista de imágenes sueltas del usuario.

    Returns:
        Markdown (string).
    """

    def title(key: str, fallback: str) -> str:
        t = (profile.titles.get(key, "") or "").strip()
        return t if t else fallback

    # ---------- Normalización y cache de capturas ----------
    captures_clean: Dict[int, List[Dict[str, str]]] = {}
    if images_by_step:
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
        # Apunta a la subsección "### Paso N {#cap-paso-N}"
        return f"[ver captura](#cap-paso-{step_n})"

    # ---------- Evidencias sueltas ----------
    evidence_clean: List[Dict[str, str]] = []
    if evidence_images:
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
    lines.append(f"# {doc.process_name}\n\n")

    # OBJETIVO
    if "objetivo" in profile.show:
        lines.append(f"## {title('objetivo', 'Objetivo')}\n\n")
        if doc.objetivo.strip():
            lines.append(f"- {doc.objetivo.strip()}\n")
        if "contexto" in profile.show and doc.contexto.strip():
            lines.append(f"\n- Contexto: {doc.contexto.strip()}\n")
        lines.append("\n")

    # CONTEXTO
    if "contexto" in profile.show and doc.contexto.strip():
        lines.append(f"## {title('contexto', 'Contexto')}\n\n")
        lines.append(f"{doc.contexto.strip()}\n\n")

    # ALCANCE
    if "alcance" in profile.show:
        lines.append(f"## {title('alcance', 'Alcance')}\n\n")
        if doc.inicio.strip():
            lines.append(f"- Inicio: {doc.inicio.strip()}\n")
        if doc.fin.strip():
            lines.append(f"- Fin: {doc.fin.strip()}\n")
        if doc.incluidos.strip():
            lines.append(f"- Incluye: {doc.incluidos.strip()}\n")
        if doc.excluidos.strip():
            lines.append(f"- No incluye: {doc.excluidos.strip()}\n")
        lines.append("\n")

    # FRECUENCIA
    if "frecuencia" in profile.show:
        lines.append(f"## {title('frecuencia', 'Frecuencia y disparadores')}\n\n")
        if doc.frecuencia.strip():
            lines.append(f"- Frecuencia: {doc.frecuencia.strip()}\n")
        if doc.disparadores.strip():
            lines.append(f"- Disparadores: {doc.disparadores.strip()}\n")
        lines.append("\n")

    # ACTORES
    if "actores" in profile.show and doc.actores_resumen.strip():
        lines.append(f"## {title('actores', 'Actores y responsabilidades')}\n\n")
        lines.append(f"{doc.actores_resumen.strip()}\n\n")

    # SISTEMAS / DATOS
    if "sistemas" in profile.show:
        lines.append(f"## {title('sistemas', 'Sistemas, datos y evidencias')}\n\n")
        if doc.sistemas.strip():
            lines.append(f"- Sistemas: {doc.sistemas.strip()}\n")
        if doc.inputs.strip():
            lines.append(f"- Entradas: {doc.inputs.strip()}\n")
        if doc.outputs.strip():
            lines.append(f"- Salidas: {doc.outputs.strip()}\n")
        lines.append("\n")

    # PASOS
    if "pasos" in profile.show:
        lines.append(f"## {title('pasos', 'Pasos')}\n\n")

        if profile.steps_format == "tabla":
            lines.append("| # | Actor | Acción | Input | Output | Riesgos |\n")
            lines.append("|---|-------|--------|-------|--------|--------|\n")
            for s in doc.pasos:
                action = s.action
                if _has_capture(s.order):
                    action = f"{action} ({_cap_link(s.order)})"
                lines.append(
                    f"| {s.order} | {s.actor} | {action} | {s.input} | {s.output} | {s.risks} |\n"
                )
            lines.append("\n")
        else:
            for s in doc.pasos:
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
            # Formato Pandoc para anclas: usar formato más explícito
            # Las llaves dobles {{ se escapan a una sola {
            anchor_id = f"cap-paso-{step_n}"
            lines.append(f"### Paso {step_n} {{#{anchor_id}}}\n\n")
            for img in captures_clean[step_n]:
                img_title = img.get("title", "").strip() or f"Captura del paso {step_n}"
                # Título descriptivo antes de la imagen (en negrita)
                lines.append(f"**{img_title}**\n\n")
                # Imagen con alt text descriptivo
                lines.append(f"![{img_title}]({img['path']})\n\n")
            # Separador visual entre pasos (opcional, ayuda a la legibilidad)
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
    if "riesgos" in profile.show and doc.problemas.strip():
        lines.append(f"## {title('riesgos', 'Riesgos')}\n\n")
        lines.append(f"{doc.problemas.strip()}\n\n")

    if "metricas" in profile.show and doc.metricas.strip():
        lines.append(f"## {title('metricas', 'Indicadores')}\n\n")
        lines.append(f"{doc.metricas.strip()}\n\n")

    if "oportunidades" in profile.show and doc.oportunidades.strip():
        lines.append(f"## {title('oportunidades', 'Oportunidades de mejora')}\n\n")
        lines.append(f"{doc.oportunidades.strip()}\n\n")

    # EXCEPCIONES
    if "excepciones" in profile.show:
        lines.append(f"## {title('excepciones', 'Excepciones')}\n\n")
        if doc.excepciones.strip():
            lines.append(f"- {doc.excepciones.strip()}\n")
        if doc.variantes.strip():
            lines.append(f"- Variantes: {doc.variantes.strip()}\n")
        lines.append("\n")

    return "".join(lines)

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
        images_by_step: dict[int, list[dict[str, str]]] | None = None,
        evidence_images: list[dict[str, str]] | None = None,
        output_base: Path | None = None,
    ) -> str:
        return render_markdown(
            doc=document,
            profile=profile,
            images_by_step=images_by_step,
            evidence_images=evidence_images,
            output_base=output_base,
        )
