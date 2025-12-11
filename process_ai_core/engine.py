import json
from typing import List

from .models import EnrichedAsset, ProcessDocument, Step, VideoRef


def build_prompt_from_enriched(process_name: str, enriched_assets: List[EnrichedAsset]) -> str:
    """
    Construye un prompt grande con todos los textos enriquecidos,
    para pedirle al modelo que genere el JSON del documento de proceso.
    """
    parts: List[str] = []
    parts.append(f"Proceso: {process_name}")
    parts.append("")

    for asset in enriched_assets:
        header = f"[{asset.kind.upper()} {asset.id}]"
        meta = ", ".join(f"{k}={v}" for k, v in asset.metadata.items())
        if meta:
            header += f" ({meta})"
        parts.append(header)
        parts.append(asset.extracted_text)
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

    if doc.videos:
        lines.append("## 11. Material de referencia (videos)\n")
        for v in doc.videos:
            lines.append(f"- **{v.title}** ({v.duration or 'duración no especificada'})\n")
            if v.url:
                lines.append(f"  - Enlace: {v.url}\n")
            if v.description:
                lines.append(f"  - Descripción: {v.description}\n")
        lines.append("\n")

    return "".join(lines)