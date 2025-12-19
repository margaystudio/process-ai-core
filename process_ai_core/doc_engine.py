from __future__ import annotations

"""
process_ai_core.doc_engine
==========================

Este módulo centraliza tres responsabilidades:

1) Prompt building
   - Arma el prompt de entrada al LLM a partir de assets enriquecidos
     (audio transcripto, texto, referencias a imágenes, referencias a video).
   - Incluye un "ancla anti-alucinaciones" listando los activos disponibles.

2) Parsing
   - Parsea el JSON devuelto por el LLM a un modelo tipado (ProcessDocument).

3) Rendering
   - Renderiza un Markdown final según un DocumentProfile (operativo vs gestión).
   - Inserta capturas automáticamente:
        * images_by_step: capturas inferidas desde videos (o asignadas por sistema),
          agrupadas por paso.
        * evidence_images: imágenes sueltas aportadas por el usuario (evidencia),
          sin asignación a pasos.

Notas de diseño
---------------
- El LLM NO debe "dibujar" imágenes en el JSON: solo referencia textual.
- El render se encarga de insertar imágenes en el Markdown, con paths relativos
  para que Pandoc (cwd=output/) resuelva correctamente "assets/...".
- Las capturas del video van en una sección separada, pero desde la tabla/lista
  de pasos se agrega un link "(ver captura)" al bloque del paso correspondiente.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .document_profiles import DocumentProfile
from .domain_models import EnrichedAsset, ProcessDocument, Step, VideoRef


# ============================================================
# Prompt builder
# ============================================================

def _assets_summary(enriched_assets: List[EnrichedAsset]) -> str:
    """
    Construye un resumen explícito de activos disponibles.

    Objetivo:
        Servir como "fuente de verdad" para reducir alucinaciones del modelo.

    Formato:
        - audio: N (ids...)
        - video: N (ids...)
        - image: N (ids...)
        - text : N (ids...)

    Args:
        enriched_assets: Lista de EnrichedAsset que ya pasaron por enrich_assets().

    Returns:
        Un bloque de texto para incluir en el prompt.
    """
    buckets: Dict[str, List[str]] = {"audio": [], "video": [], "image": [], "text": []}
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


def build_prompt_from_enriched(process_name: str, enriched_assets: List[EnrichedAsset]) -> str:
    """
    Construye un prompt grande con todos los textos enriquecidos para que el modelo genere
    el JSON del documento de proceso.

    Convención:
    - EnrichedAsset.extracted_text de imágenes incluye algo tipo:
        [IMAGEN:img1] titulo='...' archivo='assets/...'
      Esto NO implica que el modelo deba renderizar Markdown de imágenes.
      El modelo solo debe tenerlo como referencia/evidencia.

    Args:
        process_name: Nombre humano del proceso a documentar.
        enriched_assets: Lista de EnrichedAsset (audio, video, image, text).

    Returns:
        Prompt listo para enviar al LLM.
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
    parts.append(f"Proceso: {process_name}\n")
    parts.append(_assets_summary(enriched_assets))

    # --- AUDIO ---
    if audios:
        parts.append("=== TRANSCRIPCION (FUENTE ORAL) ===")
        for asset in audios:
            header = f"[AUDIO {asset.id}]"
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
            "- Si se proveen imagenes, usalas como evidencia (sin inventar contenido).\n"
            "- En los pasos, referencialas como '(ver evidencia visual)' o '(ver captura)' cuando aplique.\n"
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
            "- En los pasos, referenciá '(ver video)' cuando aplique.\n"
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


# ============================================================
# Parsing
# ============================================================

def parse_process_document(json_str: str) -> ProcessDocument:
    """
    Parsea el JSON generado por el LLM a ProcessDocument.

    Requisitos esperados del JSON:
      - process_name: str
      - objetivo/contexto/...: str
      - pasos: list[ {order, actor, action, input, output, risks} ]
      - videos (opcional): list[ {title, url, duration?, description?} ]

    Args:
        json_str: JSON crudo (string).

    Returns:
        ProcessDocument tipado.
    """
    data = json.loads(json_str)

    pasos = [
        Step(
            order=p["order"],
            actor=p["actor"],
            action=p["action"],
            input=p["input"],
            output=p["output"],
            risks=p["risks"],
        )
        for p in data.get("pasos", [])
    ]

    videos = [
        VideoRef(
            title=v.get("title", ""),
            url=v.get("url", ""),
            duration=v.get("duration"),
            description=v.get("description"),
        )
        for v in data.get("videos", [])
    ]

    return ProcessDocument(
        process_name=data["process_name"],
        objetivo=data["objetivo"],
        contexto=data["contexto"],
        alcance=data["alcance"],
        inicio=data["inicio"],
        fin=data["fin"],
        incluidos=data["incluidos"],
        excluidos=data["excluidos"],
        frecuencia=data["frecuencia"],
        disparadores=data["disparadores"],
        actores_resumen=data["actores_resumen"],
        sistemas=data["sistemas"],
        inputs=data["inputs"],
        outputs=data["outputs"],
        pasos=pasos,
        variantes=data["variantes"],
        excepciones=data["excepciones"],
        metricas=data["metricas"],
        almacenamiento_datos=data["almacenamiento_datos"],
        usos_datos=data["usos_datos"],
        problemas=data["problemas"],
        oportunidades=data["oportunidades"],
        preguntas_abiertas=data["preguntas_abiertas"],
        material_referencia=data.get("material_referencia", ""),
        videos=videos,
    )


# ============================================================
# Rendering helpers
# ============================================================

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

    # PREGUNTAS ABIERTAS
    if "preguntas_abiertas" in profile.show and doc.preguntas_abiertas.strip():
        lines.append(f"## {title('preguntas_abiertas', 'Preguntas abiertas')}\n\n")
        lines.append(doc.preguntas_abiertas.strip() + "\n\n")

    return "".join(lines)