from pathlib import Path
from typing import List

from .models import RawAsset, EnrichedAsset
from .llm_client import transcribe_audio


def enrich_assets(raw_assets: List[RawAsset]) -> List[EnrichedAsset]:
    """
    Convierte RawAsset crudos en EnrichedAsset con extracted_text.

    - audio: transcribe con OpenAI (real)
    - video: mock (a futuro: extraer audio y transcribir)
    - image: mock (a futuro: visión)
    - text: lee el archivo
    """
    enriched: List[EnrichedAsset] = []

    for a in raw_assets:
        path = a.path_or_url

        if a.kind == "audio":
            extracted = transcribe_audio(path)

        elif a.kind == "video":
            # FUTURO: extraer audio del video y transcribir,
            # o usar un modelo multimodal que entienda video.
            extracted = f"Transcripción simulada del video {a.id}"

        elif a.kind == "image":
            # FUTURO: enviar imagen a modelo con visión y describir el contenido.
            extracted = f"Descripción simulada de la imagen {a.id}"

        else:  # text
            text_path = Path(path)
            if not text_path.exists():
                raise FileNotFoundError(f"No se encontró el archivo de texto: {text_path}")
            extracted = text_path.read_text(encoding="utf-8")

        enriched.append(
            EnrichedAsset(
                id=a.id,
                kind=a.kind,
                raw_path=path,
                metadata=a.metadata,
                extracted_text=extracted,
            )
        )

    return enriched