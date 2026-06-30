from __future__ import annotations

"""
process_ai_core.llm_client
==========================

**Fachada de compatibilidad.** La lógica de IA vive ahora en
`process_ai_core.ai` (interfaces + `OpenAIProvider`), seleccionable vía
`process_ai_core.ai.factory`. Este módulo conserva las funciones históricas con
sus mismas firmas y comportamiento, delegando en los proveedores, para no romper
los call-sites existentes (`engine.py`, `media.py`).

Código nuevo: usar `process_ai_core.ai.factory` directamente.
"""

import json
from typing import Any, Dict, List, Optional

from .ai.factory import (
    get_llm_provider,
    get_transcription_provider,
    get_vision_provider,
)
from .ai.openai_provider import OpenAIProvider
from .prompts import get_process_doc_system_prompt

# Re-export para compatibilidad (algún código viejo podía importarlo).
_image_file_to_data_url = OpenAIProvider._image_file_to_data_url


def get_client():
    """DEPRECADO. Devuelve el cliente OpenAI subyacente del proveedor por defecto.

    Preferí `process_ai_core.ai.factory` y los métodos del proveedor.
    """
    return get_llm_provider().client


# ============================================================
# Transcripción de audio
# ============================================================

def transcribe_audio(path: str, prompt: str | None = None) -> str:
    """Transcribe un archivo de audio local a texto plano. Ver `TranscriptionProvider`."""
    return get_transcription_provider().transcribe(path, prompt=prompt)


def transcribe_audio_with_timestamps(
    path: str,
    prompt: str | None = None,
    granularity: str = "segment",
) -> Dict[str, Any]:
    """Transcribe audio devolviendo texto + segmentos con timestamps."""
    return get_transcription_provider().transcribe_with_timestamps(
        path, prompt=prompt, granularity=granularity
    )


# ============================================================
# Inferencia de pasos desde audio
# ============================================================

def plan_steps_from_transcript_segments(
    segments: List[Dict[str, Any]],
    max_steps: int = 15,
) -> List[Dict[str, Any]]:
    """Infiere pasos operativos a partir de segmentos de audio con timestamps.

    Orquestación local (construcción del prompt + parseo); la llamada al modelo
    va por `LLMProvider.complete_json`.
    """
    seg_lines: List[str] = []
    for s in segments:
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

    raw = get_llm_provider("strong").complete_json(system=system, user=user, temperature=0.1)
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


# ============================================================
# Selección de screenshot por visión
# ============================================================

def select_best_frame_for_step(
    step_summary: str,
    candidate_image_paths: List[str],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Elige el mejor screenshot para un paso. Ver `VisionProvider.pick_frame`."""
    return get_vision_provider().pick_frame(
        step_summary=step_summary,
        image_paths=candidate_image_paths,
        model=model,
    )


# ============================================================
# Generación de documentos (genérico)
# ============================================================

DEFAULT_DOCUMENT_USER_PREFIX = (
    "A continuación tenés el material bruto (texto, transcripciones, notas). "
    "Leelo y generá el documento en formato JSON, siguiendo "
    "estrictamente el esquema indicado en las instrucciones.\n\n"
)


def generate_document_json(
    prompt: str,
    system_prompt: str,
    user_message_prefix: str = DEFAULT_DOCUMENT_USER_PREFIX,
    temperature: float = 0.2,
) -> str:
    """Genera el JSON final de un documento a partir de un prompt largo (genérico)."""
    return get_llm_provider("strong").complete_json(
        system=system_prompt,
        user=user_message_prefix + prompt,
        temperature=temperature,
    )


# ============================================================
# Generación del documento de proceso (compatibilidad)
# ============================================================

def generate_process_document_json(prompt: str) -> str:
    """Genera el JSON final del documento de proceso (función de compatibilidad)."""
    system_instructions = get_process_doc_system_prompt(language_style="es_uy_formal")
    return generate_document_json(
        prompt=prompt,
        system_prompt=system_instructions,
        user_message_prefix=(
            "A continuación tenés el material bruto (texto, transcripciones, notas). "
            "Leelo y generá el documento de proceso en formato JSON, siguiendo "
            "estrictamente el esquema indicado en las instrucciones.\n\n"
        ),
    )
