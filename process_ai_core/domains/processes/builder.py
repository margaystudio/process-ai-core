"""
Builder para documentos de procesos.

Implementa DocumentBuilder para construir prompts y parsear JSON de procesos.
"""

from __future__ import annotations

import json
from typing import List

from ...domain_models import EnrichedAsset, VideoRef
from .models import ProcessDocument, Step
from .prompts import get_process_doc_system_prompt


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


class ProcessBuilder:
    """
    Builder para documentos de procesos.
    
    Implementa la lógica específica de procesos:
    - Construcción de prompts
    - Parsing de JSON a ProcessDocument
    """

    def build_prompt(
        self,
        document_name: str,
        enriched_assets: List[EnrichedAsset],
    ) -> str:
        """
        Construye el prompt completo para generar un documento de proceso.
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
        parts.append(f"Proceso: {document_name}\n")
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

    def parse_document(self, json_str: str) -> ProcessDocument:
        """
        Parsea el JSON devuelto por el LLM a un ProcessDocument.
        """
        data = json.loads(json_str)

        # Parsear pasos
        pasos: List[Step] = []
        for p in data.get("pasos", []):
            pasos.append(
                Step(
                    order=int(p.get("order", 0) or 0),
                    actor=str(p.get("actor", "")).strip(),
                    action=str(p.get("action", "")).strip(),
                    input=str(p.get("input", "")).strip(),
                    output=str(p.get("output", "")).strip(),
                    risks=str(p.get("risks", "")).strip(),
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

        return ProcessDocument(
            process_name=str(data.get("process_name", "")).strip(),
            objetivo=str(data.get("objetivo", "")).strip(),
            contexto=str(data.get("contexto", "")).strip(),
            alcance=str(data.get("alcance", "")).strip(),
            inicio=str(data.get("inicio", "")).strip(),
            fin=str(data.get("fin", "")).strip(),
            incluidos=str(data.get("incluidos", "")).strip(),
            excluidos=str(data.get("excluidos", "")).strip(),
            frecuencia=str(data.get("frecuencia", "")).strip(),
            disparadores=str(data.get("disparadores", "")).strip(),
            actores_resumen=str(data.get("actores_resumen", "")).strip(),
            sistemas=str(data.get("sistemas", "")).strip(),
            inputs=str(data.get("inputs", "")).strip(),
            outputs=str(data.get("outputs", "")).strip(),
            pasos=pasos,
            variantes=str(data.get("variantes", "")).strip(),
            excepciones=str(data.get("excepciones", "")).strip(),
            metricas=str(data.get("metricas", "")).strip(),
            almacenamiento_datos=str(data.get("almacenamiento_datos", "")).strip(),
            usos_datos=str(data.get("usos_datos", "")).strip(),
            problemas=str(data.get("problemas", "")).strip(),
            oportunidades=str(data.get("oportunidades", "")).strip(),
            preguntas_abiertas=str(data.get("preguntas_abiertas", "")).strip(),
            material_referencia=str(data.get("material_referencia", "")).strip(),
            videos=videos,
        )

    def get_system_prompt(self) -> str:
        """
        Devuelve el prompt del sistema para procesos.
        """
        return get_process_doc_system_prompt(language_style="es_uy_formal")

