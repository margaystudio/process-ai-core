"""Implementación OpenAI de los proveedores de IA.

**Único** módulo del proyecto que importa `openai`. Concentra la creación del
cliente y las llamadas a la API (chat/JSON, transcripción Whisper, visión).

La lógica acá es la que vivía en `process_ai_core.llm_client`; ese módulo ahora es
una fachada de compatibilidad que delega en este proveedor vía `factory`.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import tempfile
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import get_settings


class OpenAIProvider:
    """Implementa `LLMProvider`, `TranscriptionProvider` y `VisionProvider`."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_text: str | None = None,
        model_transcribe: str | None = None,
        model_transcribe_timestamps: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model_text = model_text or settings.openai_model_text
        self._model_transcribe = model_transcribe or settings.openai_model_transcribe
        self._model_transcribe_timestamps = (
            model_transcribe_timestamps
            or getattr(settings, "openai_model_transcribe_timestamps", "whisper-1")
        )
        self._client = client

    @property
    def client(self) -> OpenAI:
        """Cliente OpenAI (lazy). Falla si no hay API key configurada."""
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY no está configurada en el .env")
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    # ------------------------------------------------------------------
    # LLMProvider
    # ------------------------------------------------------------------
    def complete_json(self, *, system: str, user: str, temperature: float = 0.2) -> str:
        completion = self.client.chat.completions.create(
            model=self._model_text,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        return completion.choices[0].message.content or "{}"

    # ------------------------------------------------------------------
    # TranscriptionProvider
    # ------------------------------------------------------------------
    def transcribe(self, path: str, *, prompt: str | None = None) -> str:
        from ..media import _ffmpeg_convert_audio_to_mp3

        audio_path = Path(path)
        if not audio_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

        whisper_supported = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".webm"}

        audio_file_path = audio_path
        needs_conversion = audio_path.suffix.lower() not in whisper_supported

        if needs_conversion:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_mp3_path = Path(tmp_file.name)
            try:
                _ffmpeg_convert_audio_to_mp3(audio_path, tmp_mp3_path)
                audio_file_path = tmp_mp3_path
            except Exception as e:
                print(f"⚠️  Advertencia: No se pudo convertir {audio_path.suffix} a MP3: {e}")
                print("   Intentando con el archivo original...")

        try:
            with audio_file_path.open("rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=self._model_transcribe,
                    file=(
                        audio_file_path.name,
                        audio_file,
                        "audio/mpeg" if needs_conversion else None,
                    ),
                    prompt=prompt or "",
                    response_format="json",
                )
            return transcription.text
        finally:
            if needs_conversion and tmp_mp3_path.exists():
                try:
                    tmp_mp3_path.unlink()
                except Exception:
                    pass

    def transcribe_with_timestamps(
        self,
        path: str,
        *,
        prompt: str | None = None,
        granularity: str = "segment",
    ) -> dict[str, Any]:
        from ..media import _ffmpeg_convert_audio_to_mp3

        audio_path = Path(path)
        if not audio_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

        if granularity not in {"segment", "word"}:
            raise ValueError("granularity debe ser 'segment' o 'word'")

        model = self._model_transcribe_timestamps

        whisper_supported = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".webm"}

        audio_file_path = audio_path
        needs_conversion = audio_path.suffix.lower() not in whisper_supported

        if needs_conversion:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
                tmp_mp3_path = Path(tmp_file.name)
            try:
                _ffmpeg_convert_audio_to_mp3(audio_path, tmp_mp3_path)
                audio_file_path = tmp_mp3_path
            except Exception as e:
                print(f"⚠️  Advertencia: No se pudo convertir {audio_path.suffix} a MP3: {e}")
                print("   Intentando con el archivo original...")

        try:
            with audio_file_path.open("rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=model,
                    file=(
                        audio_file_path.name,
                        audio_file,
                        "audio/mpeg" if needs_conversion else None,
                    ),
                    prompt=prompt or "",
                    response_format="verbose_json",
                    timestamp_granularities=[granularity],
                )

            data: dict[str, Any] = {}
            if hasattr(transcription, "text"):
                data["text"] = transcription.text
            if hasattr(transcription, "segments"):
                data["segments"] = transcription.segments

            if not data and isinstance(transcription, dict):
                data = transcription
        finally:
            if needs_conversion and tmp_mp3_path.exists():
                try:
                    tmp_mp3_path.unlink()
                except Exception:
                    pass

        data.setdefault("text", "")
        data.setdefault("segments", [])
        return data

    # ------------------------------------------------------------------
    # VisionProvider
    # ------------------------------------------------------------------
    def pick_frame(
        self,
        *,
        step_summary: str,
        image_paths: list[str],
        model: str | None = None,
    ) -> dict[str, Any]:
        vision_model = model or self._model_text  # ideal: modelo con visión dedicado

        content: list[dict[str, Any]] = [
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

        for p in image_paths:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._image_file_to_data_url(p)},
                }
            )

        completion = self.client.chat.completions.create(
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _image_file_to_data_url(path: str) -> str:
        """Convierte una imagen local en un data URL base64 (para visión)."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"No se encontró la imagen: {p}")

        mime, _ = mimetypes.guess_type(str(p))
        if not mime:
            mime = "image/png"

        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
