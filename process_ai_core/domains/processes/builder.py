"""
Builder para documentos de procesos.

Implementa DocumentBuilder para construir prompts y parsear JSON de procesos.
"""

from __future__ import annotations

import json
from typing import List

from ...domain_models import EnrichedAsset, VideoRef
from .models import ProcessDocument, ProcessDocumentSchema, Step
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

    def validate_document(self, json_str: str) -> ProcessDocumentSchema:
        """
        Valida estructuralmente el JSON del LLM contra el esquema estricto.

        Lanza `json.JSONDecodeError` si el texto no es JSON y
        `pydantic.ValidationError` si la estructura no respeta el esquema
        (p.ej. `pasos` que no es una lista). Devuelve el esquema validado y
        normalizado (strings recortados, defaults aplicados).
        """
        data = json.loads(json_str)
        return ProcessDocumentSchema.model_validate(data)

    def is_document_usable(self, doc: ProcessDocument) -> bool:
        """True si el documento es servible (tiene al menos un paso u objetivo)."""
        return bool(doc.pasos) or bool(doc.objetivo.strip())

    def parse_document(self, json_str: str) -> ProcessDocument:
        """
        Parsea el JSON devuelto por el LLM a un ProcessDocument.

        Valida primero contra `ProcessDocumentSchema` (estructura/tipos) y luego
        construye el dataclass de dominio. Un JSON estructuralmente roto lanza
        excepción en vez de degradar silenciosamente a campos vacíos.
        """
        schema = self.validate_document(json_str)

        pasos: List[Step] = [
            Step(
                order=p.order,
                actor=p.actor,
                action=p.action,
                input=p.input,
                output=p.output,
                risks=p.risks,
            )
            for p in schema.pasos
        ]

        videos: List[VideoRef] = [
            VideoRef(
                title=v.title,
                url=v.url,
                duration=v.duration,
                description=v.description,
            )
            for v in schema.videos
        ]

        return ProcessDocument(
            process_name=schema.process_name,
            objetivo=schema.objetivo,
            contexto=schema.contexto,
            alcance=schema.alcance,
            inicio=schema.inicio,
            fin=schema.fin,
            incluidos=schema.incluidos,
            excluidos=schema.excluidos,
            frecuencia=schema.frecuencia,
            disparadores=schema.disparadores,
            actores_resumen=schema.actores_resumen,
            sistemas=schema.sistemas,
            inputs=schema.inputs,
            outputs=schema.outputs,
            pasos=pasos,
            variantes=schema.variantes,
            excepciones=schema.excepciones,
            metricas=schema.metricas,
            almacenamiento_datos=schema.almacenamiento_datos,
            usos_datos=schema.usos_datos,
            problemas=schema.problemas,
            oportunidades=schema.oportunidades,
            preguntas_abiertas=schema.preguntas_abiertas,
            material_referencia=schema.material_referencia,
            videos=videos,
        )

    def get_system_prompt(self) -> str:
        """
        Devuelve el prompt del sistema para procesos.
        """
        return get_process_doc_system_prompt(language_style="es_uy_formal")

