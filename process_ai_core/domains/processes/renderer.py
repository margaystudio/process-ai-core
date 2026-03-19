"""Renderer de procesos (wrapper sobre la fuente de verdad compartida)."""

from __future__ import annotations

from pathlib import Path

from .models import ProcessDocument
from .profiles import DocumentProfile
from ...doc_engine import render_markdown as shared_render_markdown


class ProcessRenderer:
    """
    Renderer para documentos de procesos.
    
    Implementa la lógica específica de procesos para renderizar
    ProcessDocument a Markdown según un DocumentProfile.
    """

    def render_markdown(
        self,
        document: ProcessDocument,
        profile: DocumentProfile,
        images_by_step: dict[int, list[dict[str, str]]] | None = None,
        evidence_images: list[dict[str, str]] | None = None,
        output_base: Path | None = None,
    ) -> str:
        """
        Renderiza delegando en `process_ai_core.doc_engine.render_markdown`.

        `doc_engine` es la fuente de verdad para evitar divergencias entre
        implementaciones de render de procesos.
        """
        return shared_render_markdown(
            doc=document,
            profile=profile,
            images_by_step=images_by_step,
            evidence_images=evidence_images,
            output_base=output_base,
        )

