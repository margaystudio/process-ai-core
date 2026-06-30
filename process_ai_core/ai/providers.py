"""Interfaces (contratos) de los proveedores de IA.

Son `Protocol`s tipados, sin implementación. Las implementaciones concretas viven
en módulos aparte (`openai_provider`, y a futuro `ollama_provider`, etc.) y se
seleccionan vía `factory`.

Mapa de responsabilidades (Technical Architecture §9):
- `LLMProvider`          → generación de texto/JSON.
- `TranscriptionProvider`→ audio → texto (con o sin timestamps).
- `VisionProvider`       → análisis de imágenes (p. ej. elegir un frame).
- `EmbeddingProvider`    → texto → vectores (RAG/Tyto). *Aún sin implementación.*
- `OCRProvider`          → imagen/PDF escaneado → texto. *Aún sin implementación.*
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Generación con un modelo de lenguaje."""

    def complete_json(self, *, system: str, user: str, temperature: float = 0.2) -> str:
        """Completa un prompt y devuelve el **string JSON crudo** del modelo.

        El modelo se fuerza a responder en formato JSON (response_format json).
        El parseo/validación se hace en otra capa (ej. validación Pydantic).
        """
        ...


@runtime_checkable
class TranscriptionProvider(Protocol):
    """Transcripción de audio a texto."""

    def transcribe(self, path: str, *, prompt: str | None = None) -> str:
        """Devuelve el texto plano transcripto de un archivo de audio local."""
        ...

    def transcribe_with_timestamps(
        self,
        path: str,
        *,
        prompt: str | None = None,
        granularity: str = "segment",
    ) -> dict[str, Any]:
        """Devuelve `{"text": str, "segments": [...]}` con marcas de tiempo."""
        ...


@runtime_checkable
class VisionProvider(Protocol):
    """Análisis de imágenes con un modelo con visión."""

    def pick_frame(
        self,
        *,
        step_summary: str,
        image_paths: list[str],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Elige el mejor screenshot para un paso.

        Devuelve `{"selected_index": int (-1 si ninguno), "title": str, "notes": str}`.
        """
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Generación de embeddings (texto → vector). Reservado para Tyto/RAG."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Devuelve un vector por cada texto de entrada, en el mismo orden."""
        ...


@runtime_checkable
class OCRProvider(Protocol):
    """Extracción de texto de imágenes / PDFs escaneados. Reservado (Fase 1.2)."""

    def extract_text(self, data: bytes, *, content_type: str | None = None) -> str:
        """Devuelve el texto extraído de los bytes de una imagen o PDF."""
        ...
