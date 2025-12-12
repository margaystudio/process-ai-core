from pathlib import Path
from typing import List

import shutil

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
            print(f"🎧 Transcripción de {a.id}:\n{extracted}\n{'-'*60}")

        elif a.kind == "video":
            # FUTURO: extraer audio del video y transcribir,
            # o usar un modelo multimodal que entienda video.
            extracted = f"Transcripción simulada del video {a.id}"

        elif a.kind == "image":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró la imagen: {src}")

            # crear carpeta output/assets si no existe
            output_assets = Path("output") / "assets"
            output_assets.mkdir(parents=True, exist_ok=True)

            dest = output_assets / f"{a.id}_{src.name}"
            shutil.copy(src, dest)

            titulo = a.metadata.get("titulo", src.stem)

            extracted = (
                f"[IMAGEN:{a.id}] "
                f"titulo='{titulo}' "
                f"archivo='assets/{dest.name}'"
            )
        elif a.kind == "video":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró el video: {src}")

            # output/assets
            output_assets = Path("output") / "assets"
            output_assets.mkdir(parents=True, exist_ok=True)

            dest_video = output_assets / f"{a.id}_{src.name}"
            shutil.copy(src, dest_video)

            # extraer audio a .m4a (AAC) para transcribir
            dest_audio = output_assets / f"{a.id}.m4a"
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(dest_video),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
                "-c:a", "aac",
                str(dest_audio),
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            extracted = transcribe_audio(str(dest_audio))
            print(f"🎥 Transcripción de {a.id} (desde video):\n{extracted}\n{'-'*60}")

            # además dejamos una “ref” para el prompt (con link si está)
            url = a.metadata.get("url", "")
            titulo = a.metadata.get("titulo", dest_video.stem)
            extracted += (
                f"\n\n[VIDEO_REF:{a.id}] titulo='{titulo}' "
                f"archivo='assets/{dest_video.name}' "
                + (f"url='{url}'" if url else "")
            )
            
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