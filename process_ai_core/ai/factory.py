"""Selección de proveedores de IA según configuración.

Punto único para obtener proveedores. Hoy solo existe OpenAI; mañana puede
devolver Ollama u otro según `.env`, sin tocar los call-sites.

Estrategia de costos (Technical Architecture §10): `tier="strong"` para tareas
donde el error cuesta caro (generación final, respuesta de Tyto); `tier="cheap"`
para tareas que pasan por revisión humana (clasificación, extracción, relaciones
candidatas). Si no se configura un modelo barato, `cheap` usa el mismo que
`strong`, por lo que el comportamiento es idéntico hasta configurarlo.
"""

from __future__ import annotations

from ..config import get_settings
from .ocr_provider import TesseractOCRProvider
from .openai_provider import OpenAIProvider


def get_llm_provider(tier: str = "strong") -> OpenAIProvider:
    """Devuelve un `LLMProvider`.

    Args:
        tier: "strong" (default) o "cheap".
    """
    settings = get_settings()
    if tier == "cheap":
        model = getattr(settings, "openai_model_text_cheap", "") or settings.openai_model_text
    else:
        model = settings.openai_model_text
    return OpenAIProvider(model_text=model)


def get_transcription_provider() -> OpenAIProvider:
    """Devuelve un `TranscriptionProvider`."""
    return OpenAIProvider()


def get_vision_provider() -> OpenAIProvider:
    """Devuelve un `VisionProvider`."""
    return OpenAIProvider()


def get_embedding_provider():
    """Devuelve un `EmbeddingProvider`.

    Aún no implementado: los embeddings llegan con Tyto/RAG (Fase 4).
    """
    raise NotImplementedError(
        "EmbeddingProvider todavía no está implementado (ver Fase 4 — Tyto/RAG)."
    )


def get_ocr_provider() -> TesseractOCRProvider:
    """Devuelve un `OCRProvider` (Tesseract local)."""
    return TesseractOCRProvider()
