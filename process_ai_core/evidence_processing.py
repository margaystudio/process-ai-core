"""Procesamiento de evidencias individuales para el wizard (Bloque C).

Expone funciones por tipo de archivo que devuelven texto extraído + metadata
(idioma, duración, páginas, used_ocr). Reutiliza providers existentes.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .ai.factory import get_ocr_provider
from .ai.ocr_provider import TesseractNotAvailableError
from .llm_client import transcribe_audio
from .media import _extract_text_from_document, _ffmpeg_extract_audio

EvidenceStatus = Literal["done", "error", "no_text"]

# Umbral mínimo de caracteres para considerar que un PDF tiene texto embebido
_MIN_EMBEDDED_TEXT_CHARS = 30


@dataclass
class EvidenceResult:
    status: EvidenceStatus
    extracted_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def detect_language(text: str) -> str | None:
    """Detecta idioma del texto (código ISO 639-1, ej. 'es')."""
    cleaned = (text or "").strip()
    if len(cleaned) < 20:
        return None
    try:
        from langdetect import detect

        return detect(cleaned)
    except Exception:
        return None


def get_media_duration_seconds(path: Path) -> float | None:
    """Duración en segundos vía ffprobe (audio/video)."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def _format_language_label(code: str | None) -> str | None:
    if not code:
        return None
    return code.upper()


def process_audio(path: Path) -> EvidenceResult:
    """Transcribe audio y devuelve texto + idioma + duración."""
    try:
        text = transcribe_audio(str(path))
        duration = get_media_duration_seconds(path)
        lang = detect_language(text)
        metadata: dict[str, Any] = {}
        if lang:
            metadata["language"] = _format_language_label(lang)
        if duration is not None:
            metadata["duration_seconds"] = int(round(duration))

        if not (text or "").strip():
            return EvidenceResult(
                status="no_text",
                extracted_text="",
                metadata=metadata,
            )

        return EvidenceResult(
            status="done",
            extracted_text=text.strip(),
            metadata=metadata,
        )
    except Exception as exc:
        return EvidenceResult(status="error", error=str(exc))


def process_video(path: Path) -> EvidenceResult:
    """Extrae audio del video, transcribe, detecta idioma y duración."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            audio_path = tmp_dir / "extracted_audio.m4a"
            _ffmpeg_extract_audio(path, audio_path)
            text = transcribe_audio(str(audio_path))

        duration = get_media_duration_seconds(path)
        lang = detect_language(text)
        metadata: dict[str, Any] = {}
        if lang:
            metadata["language"] = _format_language_label(lang)
        if duration is not None:
            metadata["duration_seconds"] = int(round(duration))

        if not (text or "").strip():
            return EvidenceResult(
                status="no_text",
                extracted_text="",
                metadata=metadata,
            )

        return EvidenceResult(
            status="done",
            extracted_text=text.strip(),
            metadata=metadata,
        )
    except Exception as exc:
        return EvidenceResult(status="error", error=str(exc))


def _count_pdf_pages(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        return len(reader.pages)
    except Exception:
        return None


def process_text_document(path: Path, filename: str | None = None) -> EvidenceResult:
    """Extrae texto embebido; PDF escaneado → fallback OCR."""
    ext = path.suffix.lower()
    metadata: dict[str, Any] = {}

    if ext == ".pdf":
        pages = _count_pdf_pages(path)
        if pages is not None:
            metadata["pages"] = pages

    try:
        text = _extract_text_from_document(path)
        used_ocr = False

        # PDF escaneado: poco o ningún texto embebido → OCR
        if ext == ".pdf" and len((text or "").strip()) < _MIN_EMBEDDED_TEXT_CHARS:
            try:
                data = path.read_bytes()
                ocr = get_ocr_provider()
                ocr_text = ocr.extract_text(data, content_type="application/pdf")
                if ocr_text.strip():
                    text = ocr_text
                    used_ocr = True
                    metadata["used_ocr"] = True
            except TesseractNotAvailableError as exc:
                if not (text or "").strip():
                    return EvidenceResult(status="error", error=str(exc))
            except Exception as exc:
                if not (text or "").strip():
                    return EvidenceResult(status="error", error=str(exc))

        lang = detect_language(text)
        if lang:
            metadata["language"] = _format_language_label(lang)
        if used_ocr:
            metadata["used_ocr"] = True

        if not (text or "").strip():
            return EvidenceResult(status="no_text", metadata=metadata)

        return EvidenceResult(
            status="done",
            extracted_text=text.strip(),
            metadata=metadata,
        )
    except Exception as exc:
        return EvidenceResult(status="error", error=str(exc))


def process_image(path: Path) -> EvidenceResult:
    """OCR directo sobre imagen."""
    try:
        data = path.read_bytes()
        ocr = get_ocr_provider()
        text = ocr.extract_text(data, content_type="image/jpeg")
        lang = detect_language(text)
        metadata: dict[str, Any] = {"used_ocr": True}
        if lang:
            metadata["language"] = _format_language_label(lang)

        if not (text or "").strip():
            return EvidenceResult(status="no_text", metadata=metadata)

        return EvidenceResult(
            status="done",
            extracted_text=text.strip(),
            metadata=metadata,
        )
    except TesseractNotAvailableError as exc:
        return EvidenceResult(status="error", error=str(exc))
    except Exception as exc:
        return EvidenceResult(status="error", error=str(exc))


def process_evidence_file(path: Path, kind: str, filename: str | None = None) -> EvidenceResult:
    """Despacha procesamiento según kind (audio|video|image|text)."""
    if kind == "audio":
        return process_audio(path)
    if kind == "video":
        return process_video(path)
    if kind == "image":
        return process_image(path)
    if kind == "text":
        return process_text_document(path, filename)
    return EvidenceResult(status="error", error=f"Tipo de evidencia no soportado: {kind}")
