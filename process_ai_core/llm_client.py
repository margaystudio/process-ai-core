from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import get_settings
from .prompts import get_process_doc_system_prompt


def get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurada en el .env")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe_audio(path: str, prompt: str | None = None) -> str:
    """
    Transcribe un archivo de audio local usando el endpoint de transcriptions.
    """
    settings = get_settings()
    client = get_client()

    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model=settings.openai_model_transcribe,
            file=audio_file,
            prompt=prompt or "",
            response_format="json",
        )

    return transcription.text


def transcribe_audio_with_timestamps(
    path: str,
    prompt: str | None = None,
    granularity: str = "segment",
) -> Dict[str, Any]:
    """
    Transcribe audio y devuelve verbose_json con timestamps (segment o word).
    """
    settings = get_settings()
    client = get_client()

    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

    if granularity not in {"segment", "word"}:
        raise ValueError("granularity debe ser 'segment' o 'word'")

    model = getattr(settings, "openai_model_transcribe_timestamps", "whisper-1")

    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            prompt=prompt or "",
            response_format="verbose_json",
            timestamp_granularities=[granularity],
        )

    data: Dict[str, Any] = {}
    if hasattr(transcription, "text"):
        data["text"] = transcription.text
    if hasattr(transcription, "segments"):
        data["segments"] = transcription.segments

    if not data and isinstance(transcription, dict):
        data = transcription

    data.setdefault("text", "")
    data.setdefault("segments", [])
    return data


def _image_file_to_data_url(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No se encontró la imagen: {p}")

    mime, _ = mimetypes.guess_type(str(p))
    if not mime:
        mime = "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def plan_steps_from_transcript_segments(
    segments: List[Dict[str, Any]],
    max_steps: int = 15,
) -> List[Dict[str, Any]]:
    """
    Infere pasos (cantidad dinámica) desde segmentos con timestamps.
    Retorna: [{order, start_s, end_s, summary, importance}, ...]
    """
    settings = get_settings()
    client = get_client()

    seg_lines: List[str] = []
    for s in segments:
        # Normalizar: dict o objeto con atributos
        if isinstance(s, dict):
            start = s.get("start", s.get("start_s", 0.0))
            end = s.get("end", s.get("end_s", start))
            text = s.get("text", "")
        else:
            start = getattr(s, "start", getattr(s, "start_s", 0.0))
            end = getattr(s, "end", getattr(s, "end_s", start))
            text = getattr(s, "text", "")

        try:
            start_f = float(start)
            end_f = float(end)
        except Exception:
            start_f, end_f = 0.0, 0.0

        text = str(text).strip()
        if text:
            seg_lines.append(f"[{start_f:.2f}–{end_f:.2f}] {text}")

    system = (
        "Sos un analista senior de procesos. "
        "Tu tarea es inferir pasos operativos a partir de segmentos con timestamps. "
        "Devolvé SOLO JSON válido."
    )

    user = (
        "A continuación tenés segmentos con timestamps.\n"
        f"Inferí pasos operativos (máximo {max_steps}).\n"
        "Reglas:\n"
        "1) La cantidad de pasos surge del contenido (no fija).\n"
        "2) Cada paso debe tener start_s y end_s cubriendo sus segmentos.\n"
        "3) Si hay muchos micro-pasos, agrupá en macro-pasos coherentes.\n"
        "4) importance ∈ {high, medium, low}.\n\n"
        "Respondé estrictamente con este esquema:\n"
        "{\n"
        '  "steps": [\n'
        '    {"order": 1, "start_s": 0.0, "end_s": 12.3, "summary": "...", "importance": "high"}\n'
        "  ]\n"
        "}\n\n"
        "SEGMENTOS:\n" + "\n".join(seg_lines)
    )

    completion = client.chat.completions.create(
        model=settings.openai_model_text,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)
    steps = data.get("steps", [])

    out: List[Dict[str, Any]] = []
    for i, st in enumerate(steps, start=1):
        out.append(
            {
                "order": int(st.get("order", i)),
                "start_s": float(st.get("start_s", 0.0)),
                "end_s": float(st.get("end_s", st.get("start_s", 0.0))),
                "summary": str(st.get("summary", "")).strip() or f"Paso {i}",
                "importance": str(st.get("importance", "medium")).strip() or "medium",
            }
        )

    return out[:max_steps]


def select_best_frame_for_step(
    step_summary: str,
    candidate_image_paths: List[str],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Usa un modelo con visión para elegir el mejor screenshot (o ninguno).
    JSON output: {"selected_index": int|-1, "title": str, "notes": str}
    """
    settings = get_settings()
    client = get_client()
    vision_model = model or settings.openai_model_text  # ideal: setear un modelo con visión acá

    content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Elegí el mejor screenshot (o ninguno) para ilustrar el paso.\n"
                "Devolvé SOLO JSON válido con el esquema:\n"
                '{"selected_index": 0..N-1 o -1, "title": string, "notes": string}\n\n'
                f"Paso: {step_summary}\n"
                "Criterios: preferí pantallas claras con la acción/estado del paso visible "
                "(botones, confirmaciones, logs). Si todas son redundantes o irrelevantes, "
                "usá selected_index=-1."
            ),
        }
    ]

    for p in candidate_image_paths:
        content.append({"type": "image_url", "image_url": {"url": _image_file_to_data_url(p)}})

    completion = client.chat.completions.create(
        model=vision_model,
        messages=[
            {
                "role": "system",
                "content": "Sos un asistente que analiza capturas de pantalla para documentación operativa. Respondés solo JSON.",
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)
    return {
        "selected_index": int(data.get("selected_index", -1)),
        "title": str(data.get("title", "")).strip(),
        "notes": str(data.get("notes", "")).strip(),
    }


def generate_process_document_json(prompt: str) -> str:
    """
    Usa un modelo de texto (chat.completions) para generar el JSON del documento de proceso.
    """
    settings = get_settings()
    client = get_client()

    system_instructions = get_process_doc_system_prompt(language_style="es_uy_formal")

    completion = client.chat.completions.create(
        model=settings.openai_model_text,
        messages=[
            {"role": "system", "content": system_instructions},
            {
                "role": "user",
                "content": (
                    "A continuación tenés el material bruto (texto, transcripciones, notas). "
                    "Leelo y generá el documento de proceso en formato JSON, siguiendo "
                    "estrictamente el esquema indicado en las instrucciones.\n\n" + prompt
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    return completion.choices[0].message.content