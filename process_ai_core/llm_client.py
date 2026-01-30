from __future__ import annotations

"""
process_ai_core.llm_client
==========================

Este módulo centraliza **todas las interacciones con OpenAI** utilizadas por el sistema.

Responsabilidades principales
------------------------------
1. Crear y configurar el cliente OpenAI a partir de settings.
2. Transcribir audio (con o sin timestamps).
3. Inferir pasos de proceso a partir de transcripciones con timestamps.
4. Seleccionar capturas relevantes desde imágenes (visión).
5. Generar el JSON final del documento de proceso a partir de un prompt largo.

Diseño
------
- Este módulo NO decide estructura de documentos.
- NO renderiza Markdown ni PDF.
- Se limita a:
    * convertir inputs (audio, imágenes, texto) en **outputs semánticos**
    * siempre devolviendo estructuras simples (str / dict / list).

Esto permite testear y evolucionar la lógica de IA sin romper el pipeline.
"""

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import get_settings
from .prompts import get_process_doc_system_prompt


# ============================================================
# Cliente OpenAI
# ============================================================

def get_client() -> OpenAI:
    """
    Construye y devuelve un cliente OpenAI usando la API key configurada.

    La API key se obtiene desde `get_settings()` y debe estar definida
    en variables de entorno o archivo .env.

    Raises:
        RuntimeError:
            Si OPENAI_API_KEY no está configurada.

    Returns:
        OpenAI:
            Cliente listo para usar en llamadas a audio, chat, visión, etc.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurada en el .env")
    return OpenAI(api_key=settings.openai_api_key)


# ============================================================
# Transcripción de audio
# ============================================================

def transcribe_audio(path: str, prompt: str | None = None) -> str:
    """
    Transcribe un archivo de audio local a texto plano.

    - Usa el endpoint de `audio.transcriptions`.
    - Ideal para audios sin necesidad de timestamps.
    - Devuelve solo el texto final, sin estructura adicional.
    - Convierte automáticamente formatos no soportados (ogg/opus) a MP3.

    Args:
        path:
            Ruta al archivo de audio local.
        prompt:
            Prompt opcional para guiar la transcripción
            (por ejemplo, nombres propios o contexto).

    Raises:
        FileNotFoundError:
            Si el archivo no existe.

    Returns:
        str:
            Texto transcripto.
    """
    import tempfile
    from process_ai_core.media import _ffmpeg_convert_audio_to_mp3
    
    settings = get_settings()
    client = get_client()

    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

    # Formatos soportados directamente por Whisper
    whisper_supported = {'.mp3', '.m4a', '.wav', '.aac', '.flac', '.webm'}
    
    # Si el formato no es soportado, convertir a MP3
    audio_file_path = audio_path
    needs_conversion = audio_path.suffix.lower() not in whisper_supported
    
    if needs_conversion:
        # Convertir a MP3 temporal
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
            tmp_mp3_path = Path(tmp_file.name)
        
        try:
            _ffmpeg_convert_audio_to_mp3(audio_path, tmp_mp3_path)
            audio_file_path = tmp_mp3_path
        except Exception as e:
            # Si falla la conversión, intentar con el original (puede que funcione)
            print(f"⚠️  Advertencia: No se pudo convertir {audio_path.suffix} a MP3: {e}")
            print(f"   Intentando con el archivo original...")

    try:
        with audio_file_path.open("rb") as audio_file:
            # Necesitamos pasar el nombre del archivo con extensión correcta
            # OpenAI Whisper detecta el formato por el nombre del archivo
            transcription = client.audio.transcriptions.create(
                model=settings.openai_model_transcribe,
                file=(audio_file_path.name, audio_file, "audio/mpeg" if needs_conversion else None),
                prompt=prompt or "",
                response_format="json",
            )
        return transcription.text
    finally:
        # Limpiar archivo temporal si se creó
        if needs_conversion and tmp_mp3_path.exists():
            try:
                tmp_mp3_path.unlink()
            except:
                pass


def transcribe_audio_with_timestamps(
    path: str,
    prompt: str | None = None,
    granularity: str = "segment",
) -> Dict[str, Any]:
    """
    Transcribe audio y devuelve texto + segmentos con timestamps.

    Se usa cuando:
    - El audio proviene de un video.
    - Necesitamos mapear partes del audio a momentos específicos
      (por ejemplo, para capturar screenshots).
    - Convierte automáticamente formatos no soportados (ogg/opus) a MP3.

    Args:
        path:
            Ruta al archivo de audio.
        prompt:
            Prompt opcional para mejorar la transcripción.
        granularity:
            Nivel de timestamp:
            - "segment": frases/segmentos (recomendado)
            - "word": palabra por palabra

    Raises:
        FileNotFoundError:
            Si el archivo no existe.
        ValueError:
            Si granularity no es válido.

    Returns:
        Dict[str, Any]:
            {
                "text": str,
                "segments": [
                    {"start": float, "end": float, "text": str, ...}
                ]
            }
    """
    import tempfile
    from process_ai_core.media import _ffmpeg_convert_audio_to_mp3
    
    settings = get_settings()
    client = get_client()

    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

    if granularity not in {"segment", "word"}:
        raise ValueError("granularity debe ser 'segment' o 'word'")

    model = getattr(settings, "openai_model_transcribe_timestamps", "whisper-1")

    # Formatos soportados directamente por Whisper
    whisper_supported = {'.mp3', '.m4a', '.wav', '.aac', '.flac', '.webm'}
    
    # Si el formato no es soportado, convertir a MP3
    audio_file_path = audio_path
    needs_conversion = audio_path.suffix.lower() not in whisper_supported
    
    if needs_conversion:
        # Convertir a MP3 temporal
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
            tmp_mp3_path = Path(tmp_file.name)
        
        try:
            _ffmpeg_convert_audio_to_mp3(audio_path, tmp_mp3_path)
            audio_file_path = tmp_mp3_path
        except Exception as e:
            # Si falla la conversión, intentar con el original (puede que funcione)
            print(f"⚠️  Advertencia: No se pudo convertir {audio_path.suffix} a MP3: {e}")
            print(f"   Intentando con el archivo original...")

    try:
        with audio_file_path.open("rb") as audio_file:
            # Necesitamos pasar el nombre del archivo con extensión correcta
            transcription = client.audio.transcriptions.create(
                model=model,
                file=(audio_file_path.name, audio_file, "audio/mpeg" if needs_conversion else None),
                prompt=prompt or "",
                response_format="verbose_json",
                timestamp_granularities=[granularity],
            )

        # Normalizamos salida (objeto o dict)
        data: Dict[str, Any] = {}
        if hasattr(transcription, "text"):
            data["text"] = transcription.text
        if hasattr(transcription, "segments"):
            data["segments"] = transcription.segments

        if not data and isinstance(transcription, dict):
            data = transcription
    finally:
        # Limpiar archivo temporal si se creó
        if needs_conversion and tmp_mp3_path.exists():
            try:
                tmp_mp3_path.unlink()
            except:
                pass

    data.setdefault("text", "")
    data.setdefault("segments", [])
    return data


# ============================================================
# Utilidades de imagen (visión)
# ============================================================

def _image_file_to_data_url(path: str) -> str:
    """
    Convierte una imagen local en un data URL base64.

    Se usa para enviar imágenes al modelo con visión
    sin depender de URLs públicas.

    Args:
        path:
            Ruta local a la imagen.

    Raises:
        FileNotFoundError:
            Si la imagen no existe.

    Returns:
        str:
            data:<mime>;base64,<contenido>
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No se encontró la imagen: {p}")

    mime, _ = mimetypes.guess_type(str(p))
    if not mime:
        mime = "image/png"

    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ============================================================
# Inferencia de pasos desde audio
# ============================================================

def plan_steps_from_transcript_segments(
    segments: List[Dict[str, Any]],
    max_steps: int = 15,
) -> List[Dict[str, Any]]:
    """
    Infere pasos operativos a partir de segmentos de audio con timestamps.

    Esta función:
    - No asume cantidad fija de pasos.
    - Agrupa micro-acciones en macro-pasos coherentes.
    - Devuelve rangos temporales por paso.

    Output esperado:
        [
            {
                "order": int,
                "start_s": float,
                "end_s": float,
                "summary": str,
                "importance": "high" | "medium" | "low"
            }
        ]

    Args:
        segments:
            Segmentos con timestamps (de Whisper u otro transcriptor).
        max_steps:
            Límite superior de pasos a devolver.

    Returns:
        Lista de pasos inferidos, ordenados.
    """
    settings = get_settings()
    client = get_client()

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


# ============================================================
# Selección de screenshot por visión
# ============================================================

def select_best_frame_for_step(
    step_summary: str,
    candidate_image_paths: List[str],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Usa un modelo con visión para elegir el mejor screenshot
    que represente un paso del proceso.

    El modelo puede:
    - Elegir una imagen (índice).
    - Rechazar todas (selected_index = -1).

    Args:
        step_summary:
            Descripción textual del paso.
        candidate_image_paths:
            Rutas locales a imágenes candidatas.
        model:
            Modelo a usar (si None, usa el default configurado).

    Returns:
        Dict con estructura:
        {
            "selected_index": int,  # índice o -1
            "title": str,           # caption sugerido
            "notes": str            # comentarios opcionales
        }
    """
    settings = get_settings()
    client = get_client()
    vision_model = model or settings.openai_model_text  # ideal: usar modelo con visión dedicado

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
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_file_to_data_url(p)},
            }
        )

    completion = client.chat.completions.create(
        model=vision_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Sos un asistente que analiza capturas de pantalla "
                    "para documentación operativa. Respondés solo JSON."
                ),
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


# ============================================================
# Generación de documentos (genérico)
# ============================================================

def generate_document_json(
    prompt: str,
    system_prompt: str,
    user_message_prefix: str = "A continuación tenés el material bruto (texto, transcripciones, notas). "
    "Leelo y generá el documento en formato JSON, siguiendo "
    "estrictamente el esquema indicado en las instrucciones.\n\n",
    temperature: float = 0.2,
) -> str:
    """
    Genera el JSON final de un documento a partir de un prompt largo (genérico).

    - Usa instrucciones de sistema proporcionadas (pueden ser específicas del dominio).
    - Devuelve texto JSON (string), no parseado.
    - El parseo y validación se hacen en otra capa.

    Args:
        prompt:
            Prompt completo (contexto + transcripciones + evidencia).
        system_prompt:
            Prompt del sistema que define el rol y comportamiento del LLM.
        user_message_prefix:
            Prefijo del mensaje del usuario (puede personalizarse por dominio).
        temperature:
            Temperatura para la generación (default: 0.2).

    Returns:
        str:
            JSON generado por el modelo (string).
    """
    settings = get_settings()
    client = get_client()

    completion = client.chat.completions.create(
        model=settings.openai_model_text,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_message_prefix + prompt,
            },
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )

    return completion.choices[0].message.content or "{}"


# ============================================================
# Generación del documento de proceso (compatibilidad)
# ============================================================

def generate_process_document_json(prompt: str) -> str:
    """
    Genera el JSON final del documento de proceso (función de compatibilidad).

    Esta función mantiene compatibilidad con código existente.
    Internamente usa `generate_document_json` con el prompt específico de procesos.

    Args:
        prompt:
            Prompt completo (contexto + transcripciones + evidencia).    Returns:
        str:
            JSON generado por el modelo (string).
    """
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
