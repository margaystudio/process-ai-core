import json
from typing import List, Dict

from .models import EnrichedAsset, ProcessDocument, Step, VideoRef


def _assets_summary(enriched_assets: List[EnrichedAsset]) -> str:
    """
    Resumen explícito de activos disponibles (ancla anti-alucinaciones).
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
    Construye un prompt grande con todos los textos enriquecidos,
    para pedirle al modelo que genere el JSON del documento de proceso.
    """
    audios = [a for a in enriched_assets if a.kind == "audio"]
    textos = [a for a in enriched_assets if a.kind == "text"]
    imagenes = [a for a in enriched_assets if a.kind == "image"]
    videos = [a for a in enriched_assets if a.kind == "video"]

    # 🔍 DEBUG / VISIBILIDAD
    print("📦 Activos detectados:")
    print(f"  - audio: {len(audios)} ({', '.join(a.id for a in audios) or 'ninguno'})")
    print(f"  - video: {len(videos)} ({', '.join(a.id for a in videos) or 'ninguno'})")
    print(f"  - image: {len(imagenes)} ({', '.join(a.id for a in imagenes) or 'ninguna'})")
    print(f"  - text : {len(textos)} ({', '.join(a.id for a in textos) or 'ninguno'})")
    print("-" * 60)

    parts: List[str] = []
    parts.append(f"Proceso: {process_name}\n")

    # 🔒 Ancla anti-alucinaciones
    parts.append(_assets_summary(enriched_assets))

    # --- AUDIO (fuente oral) ---
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

    # --- TEXTO (notas/instrucciones) ---
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

    # --- IMÁGENES (bloque explícito) ---
    if imagenes:
        parts.append("=== IMAGENES DISPONIBLES (USO OBLIGATORIO SI EXISTEN) ===")
        parts.append(
            "Reglas:\n"
            "- Si se proveen imagenes, debes usarlas en el documento.\n"
            "- En la tabla de pasos NO insertes imagenes (para no romper la tabla).\n"
            "- En los pasos, referencialas como '(ver Imagen N)' donde aplique.\n"
            "- En el campo JSON 'material_referencia', incluye TODAS las imagenes en Markdown asi:\n"
            "  Imagen N: ![titulo](assets/archivo.png)\n"
            "- Si dudas donde va una imagen, igual incluila en 'material_referencia' y marca 'Ubicacion a validar'.\n"
        )
        parts.append("")

        for idx, asset in enumerate(imagenes, start=1):
            titulo = asset.metadata.get("titulo") or asset.metadata.get("title") or f"Imagen {idx}"
            parts.append(f"Imagen {idx}: id={asset.id} titulo={titulo}")
            parts.append(f"Referencia: {asset.extracted_text}")
            parts.append("")
        parts.append("")

    # --- VIDEO ---
    if videos:
        parts.append("=== VIDEOS DISPONIBLES (REFERENCIA) ===")
        parts.append(
            "Reglas:\n"
            "- Si se proveen videos, debes agregarlos en el campo JSON 'videos'.\n"
            "- Si hay URL en metadata, usala como 'url'.\n"
            "- En los pasos, referenciá '(ver Video 1)' cuando el video ilustre ese paso.\n"
            "- No insertes el video dentro de la tabla: solo referencias.\n"
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


def parse_process_document(json_str: str) -> ProcessDocument:
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
        for v in data.get("videos", [])  # ok si no viene
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


def render_markdown(doc: ProcessDocument) -> str:
    lines: List[str] = []

    lines.append(f"# Documento de Proceso – {doc.process_name}\n\n")

    lines.append("## 1. Meta y contexto del proceso\n")
    lines.append(f"- **Objetivo principal:** {doc.objetivo}\n")
    lines.append(f"- **Contexto:** {doc.contexto}\n\n")

    lines.append("## 2. Alcance\n")
    lines.append(f"- **Inicio:** {doc.inicio}\n")
    lines.append(f"- **Fin:** {doc.fin}\n")
    lines.append(f"- **Incluye:** {doc.incluidos}\n")
    lines.append(f"- **No incluye:** {doc.excluidos}\n\n")

    lines.append("## 3. Frecuencia y disparadores\n")
    lines.append(f"- **Frecuencia:** {doc.frecuencia}\n")
    lines.append(f"- **Disparadores:** {doc.disparadores}\n\n")

    lines.append("## 4. Actores y responsabilidades (resumen)\n")
    lines.append(f"{doc.actores_resumen}\n\n")

    lines.append("## 5. Sistemas, datos y artefactos\n")
    lines.append(f"- **Sistemas:** {doc.sistemas}\n")
    lines.append(f"- **Entradas:** {doc.inputs}\n")
    lines.append(f"- **Salidas:** {doc.outputs}\n\n")

    lines.append("## 6. Descripción paso a paso del proceso\n")
    lines.append("| # | Actor | Paso / actividad | Input | Output | Riesgos |\n")
    lines.append("|---|-------|------------------|-------|--------|---------|\n")
    for step in doc.pasos:
        lines.append(
            f"| {step.order} | {step.actor} | {step.action} | "
            f"{step.input} | {step.output} | {step.risks} |\n"
        )
    lines.append("\n")

    lines.append("## 7. Variantes y excepciones\n")
    lines.append(f"- **Variantes:** {doc.variantes}\n")
    lines.append(f"- **Excepciones:** {doc.excepciones}\n\n")

    lines.append("## 8. Indicadores y datos que genera el proceso\n")
    lines.append(f"- **Métricas clave:** {doc.metricas}\n")
    lines.append(f"- **Dónde se almacenan:** {doc.almacenamiento_datos}\n")
    lines.append(f"- **Quién usa estos datos y para qué:** {doc.usos_datos}\n\n")

    lines.append("## 9. Problemas actuales y oportunidades de mejora\n")
    lines.append(f"- **Problemas:** {doc.problemas}\n")
    lines.append(f"- **Oportunidades:** {doc.oportunidades}\n\n")

    lines.append("## 10. Preguntas abiertas / pendientes\n")
    lines.append(doc.preguntas_abiertas + "\n\n")

    # Numeración dinámica para secciones opcionales
    section_n = 11

    if doc.material_referencia.strip():
        lines.append(f"## {section_n}. Material de referencia\n")
        lines.append(doc.material_referencia.strip() + "\n\n")
        section_n += 1

    if doc.videos:
        lines.append(f"## {section_n}. Material de referencia (videos)\n")
        for v in doc.videos:
            lines.append(f"- **{v.title}** ({v.duration or 'duración no especificada'})\n")
            if v.url:
                lines.append(f"  - Enlace: {v.url}\n")
            if v.description:
                lines.append(f"  - Descripción: {v.description}\n")
        lines.append("\n")

    return "".join(lines)