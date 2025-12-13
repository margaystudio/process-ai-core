from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .llm_client import (
    plan_steps_from_transcript_segments,
    select_best_frame_for_step,
    transcribe_audio,
    transcribe_audio_with_timestamps,
)
from .models import EnrichedAsset, RawAsset


def _ensure_output_assets_dir() -> Path:
    out = Path("output") / "assets"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _ffmpeg_extract_audio(video_path: Path, out_audio: Path) -> None:
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
    out: List[str] = []
    for s in segments:
        t = str(s.get("text", "")).strip()
        if t:
            out.append(t)
    return " ".join(out).strip()


def enrich_assets(raw_assets: List[RawAsset]) -> List[EnrichedAsset]:
    """
    - audio: transcribe real
    - video: extrae audio + transcribe (timestamps) + IA infiere pasos + screenshots candidatos + IA elige
    - image: copia a output/assets y referencia para el prompt
    - text: lee archivo

    Para video, además se agregan EnrichedAssets extra tipo image (las capturas seleccionadas).
    """
    enriched: List[EnrichedAsset] = []
    output_assets = _ensure_output_assets_dir()

    # Debug útil en esta etapa
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

        if a.kind == "image":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró la imagen: {src}")

            dest = output_assets / f"{a.id}_{src.name}"
            shutil.copy(src, dest)

            titulo = a.metadata.get("titulo", src.stem)
            extracted = f"[IMAGEN:{a.id}] titulo='{titulo}' archivo='assets/{dest.name}'"

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

        if a.kind == "video":
            src = Path(path)
            if not src.exists():
                raise FileNotFoundError(f"No se encontró el video: {src}")

            # 1) Copiar video
            dest_video = output_assets / f"{a.id}_{src.name}"
            shutil.copy(src, dest_video)

            # 2) Audio + transcripción con timestamps
            dest_audio = output_assets / f"{a.id}.m4a"
            _ffmpeg_extract_audio(dest_video, dest_audio)

            verbose = transcribe_audio_with_timestamps(str(dest_audio), granularity="segment")
            segments = verbose.get("segments", []) or []
            transcript_text = str(verbose.get("text") or "").strip() or _join_segments_text(segments)

            print(f"🎥 Transcripción de {a.id} (desde video):\n{transcript_text}\n{'-'*60}")

            # 3) IA: inferir pasos
            try:
                planned_steps = plan_steps_from_transcript_segments(segments, max_steps=15)
            except Exception as e:
                planned_steps = []
                print(f"⚠️ No se pudo inferir pasos ({e}). Se continúa sin screenshots.")

            # 4) Extraer candidatos + IA elige
            selected_images: List[Tuple[int, Path, str]] = []  # (order, path, title)
            if planned_steps:
                frames_dir = output_assets / f"frames_{a.id}"
                frames_dir.mkdir(parents=True, exist_ok=True)

                print(f"🧩 Pasos inferidos para {a.id}: {len(planned_steps)}")
                for st in planned_steps:
                    order = int(st.get("order", 0) or 0)
                    start_s = float(st.get("start_s", 0.0) or 0.0)
                    end_s = float(st.get("end_s", start_s) or start_s)
                    summary = str(st.get("summary", "")).strip() or f"Paso {order}"

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
                        idx = int(choice.get("selected_index", -1))
                        title = str(choice.get("title", "")).strip() or summary

                        if 0 <= idx < len(candidate_paths):
                            chosen_path = Path(candidate_paths[idx])
                            selected_images.append((order, chosen_path, title))
                            print(f"🖼️  Paso {order}: seleccionado {chosen_path.name} — {title}")
                        else:
                            print(f"🖼️  Paso {order}: sin imagen seleccionada")
                    except Exception as e:
                        print(f"⚠️ No se pudo seleccionar frame con IA (paso {order}): {e}")

            # 5) EnrichedAsset del video (transcripción + ref)
            url = a.metadata.get("url", "")
            titulo = a.metadata.get("titulo", dest_video.stem)
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

            # 6) Agregar imágenes seleccionadas como EnrichedAssets (para que el engine las use)
            for order, img_path, title in selected_images:
                img_id = f"{a.id}_img{order:02d}"
                rel = img_path.relative_to(output_assets).as_posix()
                extracted_img = f"[IMAGEN:{img_id}] titulo='{title}' archivo='assets/{rel}'"

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

            continue

        raise ValueError(f"Tipo de asset no soportado: {a.kind}")

    return enriched