"""Implementación OpenAI de los proveedores de IA.

**Único** módulo del proyecto que importa `openai`. Concentra la creación del
cliente y las llamadas a la API (chat/JSON, transcripción Whisper, visión).

La lógica acá es la que vivía en `process_ai_core.llm_client`; ese módulo ahora es
una fachada de compatibilidad que delega en este proveedor vía `factory`.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from openai import AuthenticationError, OpenAI, OpenAIError

from ..config import get_settings
from .credentials import record_auth_failure, record_success

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """Falla de una operación contra OpenAI tras agotar los reintentos del SDK.

    El SDK ya reintenta con backoff ante rate-limit, 5xx, timeouts y errores de
    conexión; si igual falla, traducimos la excepción cruda del SDK a esta —con el
    nombre de la operación— para que el pipeline la loguee y la propague de forma
    diagnosticable (p. ej. un fallo de transcripción no queda como traceback opaco).
    """


@contextmanager
def _openai_call(operation: str):
    """
    Envuelve una llamada al SDK: traduce OpenAIError a AIProviderError (logueado).

    De paso registra el estado de la credencial. Es el único punto por donde pasan
    todas las llamadas al proveedor, así que es el lugar natural: `/health` puede
    decir si la key sirve sin gastar una sola llamada extra, porque lo aprende de
    las que ya se hacen.
    """
    try:
        yield
    except AuthenticationError as exc:
        record_auth_failure(operation, type(exc).__name__)
        logger.error("OpenAI %s falló: %s: %s", operation, type(exc).__name__, exc)
        raise AIProviderError(
            f"OpenAI {operation} falló: {type(exc).__name__}: {exc}"
        ) from exc
    except OpenAIError as exc:
        # Un 500 o un rate-limit no dicen nada sobre la credencial: no se toca el
        # estado, o un pico de carga se leería como una key rota.
        logger.error("OpenAI %s falló: %s: %s", operation, type(exc).__name__, exc)
        raise AIProviderError(
            f"OpenAI {operation} falló: {type(exc).__name__}: {exc}"
        ) from exc
    else:
        record_success(operation)


class OpenAIProvider:
    """Implementa `LLMProvider`, `TranscriptionProvider`, `VisionProvider` y `EmbeddingProvider`."""

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
        self._timeout = getattr(settings, "openai_timeout_seconds", 600.0)
        self._max_retries = getattr(settings, "openai_max_retries", 3)
        self._client = client

    @property
    def client(self) -> OpenAI:
        """Cliente OpenAI (lazy). Falla si no hay API key configurada.

        Se configura timeout por request y reintentos con backoff (el SDK reintenta
        solo ante rate-limit, 5xx, timeouts y errores de conexión).
        """
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY no está configurada en el .env")
            self._client = OpenAI(
                api_key=self._api_key,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        return self._client

    # ------------------------------------------------------------------
    # LLMProvider
    # ------------------------------------------------------------------
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> str:
        """
        Completa a JSON. Con `response_format` de tipo json_schema + strict, el
        proveedor GARANTIZA la forma: desaparece la clase de error "el modelo
        devolvió JSON con otra estructura", que antes se cubría describiendo el
        esquema en prosa dentro del prompt y reintentando.

        Sin `response_format` cae a `json_object`, que es lo que necesitan los
        llamadores que no tienen un modelo Pydantic detrás.
        """
        with _openai_call("chat.completions (complete_json)"):
            completion = self.client.chat.completions.create(
                model=self._model_text,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format=response_format or {"type": "json_object"},
                temperature=temperature,
            )
        return completion.choices[0].message.content or "{}"

    def stream_text(self, *, system: str, user: str, temperature: float = 0.2):
        """Genera texto en streaming: yield de deltas de contenido (str).

        A diferencia de `complete_json`, la salida es texto plano (prosa). Los
        errores del SDK — incluidos los que ocurren a MITAD del stream — se
        traducen a AIProviderError, para que el caller pueda emitir un error
        explícito en vez de una respuesta truncada silenciosa.
        """
        with _openai_call("chat.completions (stream_text)"):
            stream = self.client.chat.completions.create(
                model=self._model_text,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

    # ------------------------------------------------------------------
    # EmbeddingProvider
    # ------------------------------------------------------------------
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        settings = get_settings()
        with _openai_call("embeddings.create"):
            response = self.client.embeddings.create(
                model=settings.openai_model_embedding,
                input=texts,
            )
        # La API devuelve los embeddings con índice; ordenar por las dudas.
        items = sorted(response.data, key=lambda d: d.index)
        return [item.embedding for item in items]

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
                with _openai_call("audio.transcriptions (transcribe)"):
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
                with _openai_call("audio.transcriptions (transcribe_with_timestamps)"):
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

        with _openai_call("chat.completions (pick_frame)"):
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

    def describe_image(
        self,
        *,
        data: bytes,
        mime_type: str = "image/png",
        context: str = "",
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Describe una imagen para que su contenido exista en la capa semántica.

        Tyto indexa TEXTO. Si el paso clave de un procedimiento es una captura de
        qué celdas completar, sin esta descripción esa información no existe en
        el índice y Tyto nunca va a poder responderla.

        La descripción es INFERENCIA PURA: nadie la escribió ni la validó. Quien
        la consuma tiene que marcarla como tal (chip "A VALIDAR", ADR-015).

        Returns:
            `{"titulo": str, "descripcion": str}` — vacíos si el modelo no
            devolvió nada utilizable.
        """
        vision_model = model or self._model_text
        b64 = base64.b64encode(data).decode("ascii")

        instruccion = (
            "Describí esta imagen para que alguien que NO la ve pueda entender qué "
            "muestra y usarla en un procedimiento operativo.\n"
            "Devolvé SOLO JSON válido con el esquema:\n"
            '{"titulo": string, "descripcion": string}\n\n'
            "- titulo: una línea corta (máx. 10 palabras) que nombre la imagen.\n"
            "- descripcion: 2 a 4 oraciones. Si es una captura de pantalla o una "
            "planilla, decí qué pantalla/planilla es, qué campos o celdas se ven y "
            "qué valores o acciones aparecen. Transcribí los rótulos legibles.\n"
            "- No inventes nada que no se vea en la imagen. No opines."
        )
        if context.strip():
            instruccion += (
                "\n\nTexto del documento alrededor de la imagen (contexto, no es la "
                f"imagen):\n{context.strip()[:1200]}"
            )

        with _openai_call("chat.completions (describe_image)"):
            completion = self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Sos un asistente que describe imágenes de documentación "
                            "operativa. Respondés solo JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": instruccion},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

        raw = completion.choices[0].message.content or "{}"
        data_json = json.loads(raw)
        return {
            "titulo": str(data_json.get("titulo", "")).strip(),
            "descripcion": str(data_json.get("descripcion", "")).strip(),
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
