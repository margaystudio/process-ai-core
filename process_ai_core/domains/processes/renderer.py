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


#: Marca visible de contenido inferido y no validado. Se movió a
#: `core.inference` porque dejó de ser de este dominio: también la llevan las
#: descripciones de imagen generadas con visión. Se re-exporta acá para no
#: romper los call-sites que la importan desde el renderer.
from ...core.inference import CHIP_A_VALIDAR  # noqa: E402  (re-export)


def _t(valor) -> str:
    """Texto de un campo opcional: None y vacío colapsan a ''."""
    return (valor or "").strip()


def _chip_campo(doc, campo: str) -> str:
    """Chip para un campo de texto que el modelo declaró como inferido."""
    return f" {CHIP_A_VALIDAR}" if doc.es_inferido(campo) else ""


def _descripcion_de_captura(img: Dict[str, str]) -> str:
    """
    Pie de la captura con su descripción automática, o "" si no tiene.

    Va en el cuerpo del documento y no como `alt` de la imagen porque el `alt` no
    se imprime ni se indexa: el punto de describir la imagen es que su contenido
    exista en la capa semántica, y lo que Tyto indexa es el markdown. Lleva el
    chip porque es inferencia sin validar, como cualquier otro contenido inferido.
    """
    descripcion = (img.get("description") or "").strip()
    if not descripcion:
        return ""
    return f"{descripcion} {CHIP_A_VALIDAR}\n\n"


def _chip(confianza: str) -> str:
    """Sufijo con el chip si el ítem está inferido; '' si fue relevado."""
    from .models import CONFIANZA_INFERIDO

    return f" {CHIP_A_VALIDAR}" if confianza == CONFIANZA_INFERIDO else ""


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
                valid.append(
                    {
                        "path": path,
                        "title": cap_title,
                        "description": (img.get("description") or "").strip(),
                    }
                )
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
    if "objetivo" in profile.show and (_t(doc.objetivo) or _t(doc.contexto)):
        lines.append(f"## {title('objetivo', 'Objetivo')}\n\n")
        if _t(doc.objetivo):
            lines.append(f"- {_t(doc.objetivo)}{_chip_campo(doc, 'objetivo')}\n")
        # El contexto se inlinea acá SOLO si no tiene sección propia. Antes se
        # emitía en los dos lugares y el documento repetía el mismo párrafo dos
        # veces seguidas.
        if "contexto" not in profile.show and _t(doc.contexto):
            lines.append(f"\n- Contexto: {_t(doc.contexto)}\n")
        lines.append("\n")

    # CONTEXTO
    if "contexto" in profile.show and _t(doc.contexto):
        lines.append(f"## {title('contexto', 'Contexto')}\n\n")
        lines.append(f"{_t(doc.contexto)}\n\n")

    # ALCANCE
    # El encabezado se emite DESPUÉS de confirmar que hay contenido: si todos los
    # subcampos vienen vacíos, un "## Alcance" solo es peor que no tener la
    # sección — parece un documento incompleto en vez de uno que no releva eso.
    if "alcance" in profile.show and any(
        _t(x) for x in (doc.inicio, doc.fin, doc.incluidos, doc.excluidos)
    ):
        lines.append(f"## {title('alcance', 'Alcance')}\n\n")
        if _t(doc.inicio):
            lines.append(f"- Inicio: {_t(doc.inicio)}\n")
        if _t(doc.fin):
            lines.append(f"- Fin: {_t(doc.fin)}\n")
        if _t(doc.incluidos):
            lines.append(f"- Incluye: {_t(doc.incluidos)}\n")
        if _t(doc.excluidos):
            lines.append(f"- No incluye: {_t(doc.excluidos)}\n")
        lines.append("\n")

    # FRECUENCIA
    if "frecuencia" in profile.show and any(_t(x) for x in (doc.frecuencia, doc.disparadores)):
        lines.append(f"## {title('frecuencia', 'Frecuencia y disparadores')}\n\n")
        if _t(doc.frecuencia):
            lines.append(f"- Frecuencia: {_t(doc.frecuencia)}{_chip_campo(doc, 'frecuencia')}\n")
        if _t(doc.disparadores):
            lines.append(f"- Disparadores: {_t(doc.disparadores)}\n")
        lines.append("\n")

    # ACTORES
    if "actores" in profile.show and doc.actores:
        lines.append(f"## {title('actores', 'Actores y responsabilidades')}\n\n")
        lines.append("| Rol | Responsabilidad |\n|-----|------------------|\n")
        for a in doc.actores:
            rol = a.rol.strip() or "—"
            lines.append(f"| {rol} | {a.responsabilidad.strip()}{_chip(a.confianza)} |\n")
        lines.append("\n")

    # SISTEMAS / DATOS
    if "sistemas" in profile.show and any(
        _t(x) for x in (doc.sistemas, doc.inputs, doc.outputs,
                        doc.almacenamiento_datos, doc.usos_datos)
    ):
        lines.append(f"## {title('sistemas', 'Sistemas, datos y evidencias')}\n\n")
        if _t(doc.sistemas):
            lines.append(f"- Sistemas: {_t(doc.sistemas)}\n")
        if _t(doc.inputs):
            lines.append(f"- Entradas: {_t(doc.inputs)}\n")
        if _t(doc.outputs):
            lines.append(f"- Salidas: {_t(doc.outputs)}\n")
        # Estos dos estaban en el schema desde siempre y NUNCA se imprimían.
        # Son contenido de gobernanza: dónde viven los datos del proceso y para
        # qué se usan. Su lugar natural es acá.
        if _t(doc.almacenamiento_datos):
            lines.append(f"- Almacenamiento de datos: {_t(doc.almacenamiento_datos)}\n")
        if _t(doc.usos_datos):
            lines.append(f"- Usos de los datos: {_t(doc.usos_datos)}\n")
        lines.append("\n")

    # PASOS
    if "pasos" in profile.show:
        lines.append(f"## {title('pasos', 'Pasos')}\n\n")

        if profile.steps_format == "tabla":
            # Cinco columnas y no seis: la de Riesgos se movió a la matriz de
            # riesgos, que es donde un auditor la busca. Seis columnas en A4
            # quedaban ilegibles.
            lines.append("| # | Actor | Acción | Entrada | Salida |\n")
            lines.append("|---|-------|--------|---------|--------|\n")
            for s in doc.pasos:
                action = s.action + _chip(s.confianza)
                if _has_capture(s.order):
                    action = f"{action} ({_cap_link(s.order)})"
                lines.append(
                    f"| {s.order} | {s.actor} | {action} | {s.input} | {s.output} |\n"
                )
            lines.append("\n")
        else:
            for s in doc.pasos:
                header = f"**{s.order}. {s.action}**{_chip(s.confianza)}"
                if _has_capture(s.order):
                    header += f" ({_cap_link(s.order)})"
                lines.append(header + "\n")
                if s.input.strip():
                    lines.append(f"- Entrada: {s.input.strip()}\n")
                if s.output.strip():
                    lines.append(f"- Resultado: {s.output.strip()}\n")
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
                lines.append(_descripcion_de_captura(img))

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
                lines.append(_descripcion_de_captura(img))
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
    # Matriz de riesgos: riesgo + control + evidencia + criticidad es lo que
    # espera un auditor, y es lo que el prompt ya venía pidiendo en prosa.
    if "riesgos" in profile.show and doc.riesgos:
        lines.append(f"## {title('riesgos', 'Riesgos y controles')}\n\n")
        lines.append("| Riesgo | Control actual | Evidencia | Criticidad |\n")
        lines.append("|--------|----------------|-----------|------------|\n")
        for r in doc.riesgos:
            lines.append(
                f"| {r.riesgo.strip()}{_chip(r.confianza)} | {r.control_actual.strip() or '—'} "
                f"| {r.evidencia.strip() or '—'} | {r.criticidad.strip() or '—'} |\n"
            )
        lines.append("\n")

    if "metricas" in profile.show and doc.metricas:
        lines.append(f"## {title('metricas', 'Indicadores')}\n\n")
        lines.append("| Indicador | Definición | Frecuencia | Meta |\n")
        lines.append("|-----------|------------|------------|------|\n")
        for m in doc.metricas:
            lines.append(
                f"| {m.indicador.strip()}{_chip(m.confianza)} | {m.definicion.strip() or '—'} "
                f"| {m.frecuencia.strip() or '—'} | {m.meta.strip() or '—'} |\n"
            )
        lines.append("\n")

    if "oportunidades" in profile.show and _t(doc.oportunidades):
        lines.append(f"## {title('oportunidades', 'Oportunidades de mejora')}\n\n")
        lines.append(f"{_t(doc.oportunidades)}{_chip_campo(doc, 'oportunidades')}\n\n")

    # EXCEPCIONES
    if "excepciones" in profile.show and any(_t(x) for x in (doc.excepciones, doc.variantes)):
        lines.append(f"## {title('excepciones', 'Excepciones')}\n\n")
        if _t(doc.excepciones):
            lines.append(f"- {_t(doc.excepciones)}\n")
        if _t(doc.variantes):
            lines.append(f"- Variantes: {_t(doc.variantes)}\n")
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
