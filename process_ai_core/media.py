from __future__ import annotations

"""
process_ai_core.media
=====================

Este módulo se encarga de **enriquecer insumos crudos (RawAsset)** para que puedan
ser usados por el motor de documentación de procesos.

Responsabilidades principales
------------------------------
- Transcribir audio.
- Procesar video:
    * extraer audio
    * transcribir con timestamps
    * inferir pasos con IA
    * extraer frames candidatos
    * seleccionar la mejor captura por paso con IA
- Manejar imágenes sueltas como evidencia visual.
- Preparar estructuras auxiliares para el render final (Markdown / PDF).

Salida clave
------------
La función principal `enrich_assets` devuelve **tres estructuras**:
1. enriched_assets:
   Lista de EnrichedAsset → se usa para construir el prompt del LLM.
2. images_by_step:
   Dict[int, List[dict]] → capturas inferidas desde video, agrupadas por paso.
3. evidence_images:
   List[dict] → imágenes sueltas aportadas por el usuario (evidencia visual).
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .config import get_settings
from .llm_client import (
    plan_steps_from_transcript_segments,
    select_best_frame_for_step,
    transcribe_audio,
    transcribe_audio_with_timestamps,
)
from .domain_models import EnrichedAsset, RawAsset


# ============================================================
# Helpers de filesystem y ffmpeg
# ============================================================

def _ensure_output_assets_dir(output_base: Path | None = None) -> Path:
    """
    Asegura la existencia del directorio base donde se guardan
    todos los assets generados automáticamente.

    Args:
        output_base: Directorio base opcional. Si se especifica, los assets
                     se copian ahí. Si es None, usa settings.output_dir/assets/

    Returns:
        Path al directorio de assets
    """
    if output_base:
        assets_dir = output_base / "assets"
    else:
        settings = get_settings()
        assets_dir = Path(settings.output_dir) / settings.assets_dir
    
    assets_dir.mkdir(parents=True, exist_ok=True)
    return assets_dir


def _ffmpeg_convert_audio_to_mp3(input_path: Path, output_path: Path) -> None:
    """
    Convierte un archivo de audio a MP3 usando ffmpeg.
    
    Útil para convertir formatos no soportados por OpenAI Whisper (como .ogg/.opus)
    a un formato compatible (.mp3).
    
    Args:
        input_path: Ruta al archivo de audio original.
        output_path: Ruta de salida del archivo MP3.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-acodec",
        "libmp3lame",
        "-ar",
        "16000",  # Sample rate compatible con Whisper
        "-ac",
        "1",  # Mono
        "-q:a",
        "2",  # Calidad alta
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _ffmpeg_extract_audio(video_path: Path, out_audio: Path) -> None:
    """
    Extrae el audio de un video usando ffmpeg.

    Convenciones:
    - Audio mono
    - Sample rate 16kHz
    - Codec AAC

    Args:
        video_path: Ruta al video original.
        out_audio: Ruta de salida del archivo de audio.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        str(out_audio),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _ffmpeg_frame_at_time(video_path: Path, t_s: float, out_img: Path) -> None:
    """
    Extrae un frame de un video en un timestamp específico.

    Args:
        video_path: Ruta al video.
        t_s: Tiempo en segundos desde el inicio del video.
        out_img: Ruta de salida de la imagen PNG.
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{t_s:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_img),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _pick_candidate_times(start_s: float, end_s: float, n: int = 3) -> List[float]:
    """
    Selecciona timestamps candidatos dentro de un intervalo [start_s, end_s].

    Estrategia:
    - Si el intervalo es muy corto, devuelve el punto medio.
    - Si es más largo, evita bordes y genera N puntos equiespaciados.

    Args:
        start_s: Inicio del segmento (segundos).
        end_s: Fin del segmento (segundos).
        n: Cantidad de timestamps a generar.

    Returns:
        Lista de tiempos (en segundos) >= 0.
    """
    if end_s < start_s:
        start_s, end_s = end_s, start_s

    dur = max(0.0, end_s - start_s)
    if dur < 0.75:
        return [max(0.0, start_s + dur / 2.0)]

    pad = min(1.0, dur * 0.2)
    a = start_s + pad
    b = end_s - pad
    if b <= a:
        return [max(0.0, start_s + dur / 2.0)]

    if n <= 1:
        return [max(0.0, (a + b) / 2.0)]

    step = (b - a) / (n - 1)
    return [max(0.0, a + i * step) for i in range(n)]


def _join_segments_text(segments: List[Dict[str, Any]]) -> str:
    """
    Concatena texto de segmentos de transcripción.

    Args:
        segments: Lista de dicts con clave "text".

    Returns:
        Texto concatenado, separado por espacios.
    """
    out: List[str] = []
    for s in segments:
        t = str(s.get("text", "")).strip()
        if t:
            out.append(t)
    return " ".join(out).strip()


# ============================================================
# API principal
# ============================================================

def enrich_assets(
    raw_assets: List[RawAsset],
    output_base: Path | None = None,
) -> tuple[List[EnrichedAsset], Dict[int, List[Dict[str, str]]], List[Dict[str, str]]]:
    """
    Enriquecimiento central de assets.

    Qué hace según el tipo:
    -----------------------
    - audio:
        * Transcribe audio completo.
    - text:
        * Lee archivo de texto.
    - image:
        * Copia a output/assets/evidence/
        * Se trata como evidencia visual (no como paso).
    - video:
        * Copia video a output/assets/
        * Extrae audio
        * Transcribe con timestamps
        * IA infiere pasos
        * Extrae frames candidatos por paso
        * IA selecciona el mejor frame por paso

    Returns:
        enriched_assets:
            Lista de EnrichedAsset para construir el prompt del LLM.
        images_by_step:
            Dict { paso_n: [ {"path": "assets/...", "title": "..."} ] }
            Capturas inferidas desde video.
        evidence_images:
            Lista de {"path": "...", "title": "..."} para sección "Evidencia visual".
    """
    enriched: List[EnrichedAsset] = []
    images_by_step: Dict[int, List[Dict[str, str]]] = {}
    evidence_images: List[Dict[str, str]] = []

    settings = get_settings()
    output_assets = _ensure_output_assets_dir(output_base)
    evidence_dir = output_assets / settings.evidence_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Debug de conteo inicial
    counts = {"audio": 0, "video": 0, "image": 0, "text": 0}
    for a in raw_assets:
        counts[a.kind] = counts.get(a.kind, 0) + 1
    print(
        "📦 Activos detectados: "
        f"audio={counts.get('audio', 0)} | "
        f"video={counts.get('video', 0)} | "
        f"image={counts.get('image', 0)} | "
        f"text={counts.get('text', 0)}"
    )

    for a in raw_assets:
        path = a.path_or_url

        # ----------------------------
        # AUDIO
        # ----------------------------
        if a.kind == "audio":
            extracted = transcribe_audio(path)
            print(f"🎧 Transcripción de {a.id}:\n{extracted}\n{'-'*60}")
            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted,
                )
            )
            continue

        # ----------------------------
        # TEXT
        # ----------------------------
        if a.kind == "text":
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
            continue

        # ----------------------------
        # IMAGE (evidencia suelta)
        # ----------------------------
        if a.kind == "image":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró la imagen: {src}")

            dest = evidence_dir / f"{a.id}_{src.name}"
            shutil.copy(src, dest)

            titulo = (a.metadata.get("titulo") or src.stem).strip() or src.stem
            rel_path = f"assets/evidence/{dest.name}"

            extracted = f"[IMAGEN:{a.id}] titulo='{titulo}' archivo='{rel_path}'"

            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted,
                )
            )

            evidence_images.append({"path": rel_path, "title": titulo})
            continue

        # ----------------------------
        # VIDEO
        # ----------------------------
        if a.kind == "video":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró el video: {src}")

            # Copiar video
            dest_video = output_assets / f"{a.id}_{src.name}"
            shutil.copy(src, dest_video)

            # Extraer audio
            dest_audio = output_assets / f"{a.id}.m4a"
            _ffmpeg_extract_audio(dest_video, dest_audio)

            # Transcripción con timestamps
            verbose = transcribe_audio_with_timestamps(str(dest_audio), granularity="segment")
            if isinstance(verbose, dict):
                segments = verbose.get("segments", []) or []
                transcript_text = str(verbose.get("text") or "").strip() or _join_segments_text(segments)
            else:
                segments = getattr(verbose, "segments", []) or []
                transcript_text = str(getattr(verbose, "text", "") or "").strip() or _join_segments_text(segments)

            print(f"🎥 Transcripción de {a.id} (desde video):\n{transcript_text}\n{'-'*60}")

            # Inferir pasos con IA
            try:
                planned_steps = plan_steps_from_transcript_segments(segments, max_steps=15)
            except Exception as e:
                planned_steps = []
                print(f"⚠️ No se pudo inferir pasos ({e}). Se continúa sin screenshots.")

            selected_images: List[Tuple[int, Path, str]] = []

            if planned_steps:
                frames_dir = output_assets / f"frames_{a.id}"
                frames_dir.mkdir(parents=True, exist_ok=True)

                print(f"🧩 Pasos inferidos para {a.id}: {len(planned_steps)}")
                for st in planned_steps:
                    if isinstance(st, dict):
                        order = int(st.get("order", 0) or 0)
                        start_s = float(st.get("start_s", 0.0) or 0.0)
                        end_s = float(st.get("end_s", start_s) or start_s)
                        summary = str(st.get("summary", "")).strip() or f"Paso {order}"
                    else:
                        order = int(getattr(st, "order", 0) or 0)
                        start_s = float(getattr(st, "start_s", 0.0) or 0.0)
                        end_s = float(getattr(st, "end_s", start_s) or start_s)
                        summary = str(getattr(st, "summary", "")).strip() or f"Paso {order}"

                    cand_times = _pick_candidate_times(start_s, end_s, n=3)
                    candidate_paths: List[str] = []

                    for i, t in enumerate(cand_times, start=1):
                        out_img = frames_dir / f"step{order:02d}_{i}.png"
                        try:
                            _ffmpeg_frame_at_time(dest_video, t, out_img)
                            candidate_paths.append(str(out_img))
                        except Exception as e:
                            print(f"⚠️ No se pudo extraer frame t={t:.2f}s (paso {order}): {e}")

                    if not candidate_paths:
                        continue

                    try:
                        choice = select_best_frame_for_step(summary, candidate_paths)
                        if isinstance(choice, dict):
                            idx = int(choice.get("selected_index", -1))
                            title = str(choice.get("title", "")).strip() or summary
                        else:
                            idx = int(getattr(choice, "selected_index", -1))
                            title = str(getattr(choice, "title", "")).strip() or summary

                        if 0 <= idx < len(candidate_paths):
                            chosen_path = Path(candidate_paths[idx])
                            selected_images.append((order, chosen_path, title))
                            print(f"🖼️  Paso {order}: seleccionado {chosen_path.name} — {title}")
                        else:
                            print(f"🖼️  Paso {order}: sin imagen seleccionada")
                    except Exception as e:
                        print(f"⚠️ No se pudo seleccionar frame con IA (paso {order}): {e}")

            # EnrichedAsset del video
            url = a.metadata.get("url", "")
            titulo = (a.metadata.get("titulo") or dest_video.stem).strip() or dest_video.stem
            extracted_video = transcript_text + (
                f"\n\n[VIDEO_REF:{a.id}] titulo='{titulo}' archivo='assets/{dest_video.name}'"
                + (f" url='{url}'" if url else "")
            )

            enriched.append(
                EnrichedAsset(
                    id=a.id,
                    kind=a.kind,
                    raw_path=path,
                    metadata=a.metadata,
                    extracted_text=extracted_video,
                )
            )

            # Imágenes seleccionadas
            for order, img_path, title in selected_images:
                img_id = f"{a.id}_img{order:02d}"
                rel = img_path.relative_to(output_assets).as_posix()
                render_path = f"assets/{rel}"

                images_by_step.setdefault(order, []).append(
                    {"path": render_path, "title": title}
                )

                extracted_img = f"[IMAGEN:{img_id}] titulo='{title}' archivo='{render_path}'"
                enriched.append(
                    EnrichedAsset(
                        id=img_id,
                        kind="image",
                        raw_path=str(img_path),
                        metadata={
                            "titulo": title,
                            "paso_sugerido": str(order),
                            "source_video": a.id,
                        },
                        extracted_text=extracted_img,
                    )
                )

            # El video suele ser el asset principal → salimos
            return enriched, images_by_step, evidence_images

        raise ValueError(f"Tipo de asset no soportado: {a.kind}")

    return enriched, images_by_step, evidence_images