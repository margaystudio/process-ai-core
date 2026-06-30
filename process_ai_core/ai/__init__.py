"""Capa de proveedores de IA.

Define interfaces (`providers`) y una implementación OpenAI (`openai_provider`),
seleccionables vía `factory`. El resto de la app debería obtener proveedores a
través de `process_ai_core.ai.factory`, nunca instanciando clientes de OpenAI
directamente. Así se puede cambiar de proveedor (OpenAI, Ollama, etc.) y aplicar
la estrategia de costos "IA cara / IA barata" sin tocar el código de dominio.
"""

from .providers import (
    EmbeddingProvider,
    LLMProvider,
    OCRProvider,
    TranscriptionProvider,
    VisionProvider,
)
from .factory import (
    get_embedding_provider,
    get_llm_provider,
    get_transcription_provider,
    get_vision_provider,
)

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "OCRProvider",
    "TranscriptionProvider",
    "VisionProvider",
    "get_embedding_provider",
    "get_llm_provider",
    "get_transcription_provider",
    "get_vision_provider",
]
