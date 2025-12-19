"""
Abstracciones (Protocols) para el motor genérico de documentación.

Estos protocols definen las interfaces que cada dominio debe implementar
para que el core genérico pueda trabajar con cualquier tipo de documento.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Protocol

from ..domain_models import EnrichedAsset


class DocumentBuilder(Protocol):
    """
    Interfaz para construir prompts y parsear documentos.
    
    Cada dominio debe implementar esta interfaz para definir:
    - Cómo construir el prompt para el LLM
    - Cómo parsear el JSON devuelto por el LLM
    - Qué prompt del sistema usar
    """

    def build_prompt(
        self,
        document_name: str,
        enriched_assets: List[EnrichedAsset],
    ) -> str:
        """
        Construye el prompt completo para el LLM a partir de assets enriquecidos.
        
        Args:
            document_name: Nombre del documento (ej: "Proceso X", "Receta Y")
            enriched_assets: Lista de assets enriquecidos (transcripciones, imágenes, etc.)
        
        Returns:
            Prompt completo como string, listo para enviar al LLM.
        """
        ...

    def parse_document(self, json_str: str) -> Any:
        """
        Parsea el JSON devuelto por el LLM a un modelo tipado del dominio.
        
        Args:
            json_str: JSON crudo devuelto por el LLM
        
        Returns:
            Modelo tipado específico del dominio (ej: ProcessDocument, RecipeDocument)
        """
        ...

    def get_system_prompt(self) -> str:
        """
        Devuelve el prompt del sistema para este dominio.
        
        Returns:
            Prompt del sistema que define el rol y comportamiento del LLM.
        """
        ...


class DocumentRenderer(Protocol):
    """
    Interfaz para renderizar documentos a Markdown.
    
    Cada dominio debe implementar esta interfaz para definir:
    - Cómo renderizar su modelo de documento a Markdown
    - Cómo manejar imágenes y evidencia visual
    - Qué perfiles de documento soporta
    """

    def render_markdown(
        self,
        document: Any,  # Tipo específico del dominio
        profile: Any,   # Perfil específico del dominio
        images_by_step: Dict[int, List[Dict[str, str]]] | None = None,
        evidence_images: List[Dict[str, str]] | None = None,
        output_base: Path | None = None,
    ) -> str:
        """
        Renderiza el documento a Markdown según el perfil indicado.
        
        Args:
            document: Modelo tipado del documento (específico del dominio)
            profile: Perfil de renderizado (específico del dominio)
            images_by_step: Capturas agrupadas por paso (desde video)
            evidence_images: Imágenes sueltas de evidencia
            output_base: Directorio base para validar rutas de imágenes
        
        Returns:
            Markdown renderizado como string.
        """
        ...

