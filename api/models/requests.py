"""
Modelos de request para la API.

Estos modelos definen la estructura esperada de los requests HTTP,
validando tipos y valores antes de pasarlos al core.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProcessMode(str, Enum):
    """Modo del documento a generar."""

    OPERATIVO = "operativo"
    GESTION = "gestion"


class RecipeMode(str, Enum):
    """Modo del documento de receta a generar."""

    SIMPLE = "simple"
    DETALLADO = "detallado"


class ProcessRunRequest(BaseModel):
    """
    Request para crear una nueva corrida del pipeline.

    Este modelo valida los parámetros antes de llamar a `engine.run_process_pipeline`.
    """

    process_name: str = Field(..., description="Nombre del proceso a documentar")
    mode: ProcessMode = Field(
        default=ProcessMode.OPERATIVO,
        description="Modo del documento (operativo o gestión)",
    )

    # Parámetros opcionales de contexto (para inyectar en el prompt)
    detail_level: Optional[str] = Field(
        default=None,
        description="Nivel de detalle (ej: breve, estandar, detallado)",
    )

    # Nota: Los archivos se manejan aparte (multipart/form-data)
    # No los incluimos en este modelo porque FastAPI los maneja diferente


class ProcessRunResponse(BaseModel):
    """
    Response de una corrida del pipeline.

    Devuelve información sobre la corrida y URLs/paths a los artefactos generados.
    """

    run_id: str = Field(..., description="ID único de la corrida")
    process_name: str = Field(..., description="Nombre del proceso")
    status: str = Field(..., description="Estado: processing|completed|error")
    artifacts: dict = Field(
        default_factory=dict,
        description="URLs/paths a artefactos generados (json, markdown, pdf)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Mensaje de error si status='error'",
    )


class RecipeRunResponse(BaseModel):
    """
    Response de una corrida del pipeline de recetas.

    Devuelve información sobre la corrida y URLs/paths a los artefactos generados.
    """

    run_id: str = Field(..., description="ID único de la corrida")
    recipe_name: str = Field(..., description="Nombre de la receta")
    status: str = Field(..., description="Estado: processing|completed|error")
    artifacts: dict = Field(
        default_factory=dict,
        description="URLs/paths a artefactos generados (json, markdown, pdf)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Mensaje de error si status='error'",
    )


class WorkspaceCreateRequest(BaseModel):
    """Request para crear un workspace (cliente/organización)."""

    name: str = Field(..., description="Nombre de la organización/cliente")
    slug: str = Field(..., description="Slug único (usado en URLs)")
    country: str = Field(default="UY", description="Código de país (ISO2)")
    business_type: Optional[str] = Field(default=None, description="Tipo de negocio")
    language_style: str = Field(default="es_uy_formal", description="Estilo de idioma")
    default_audience: str = Field(default="operativo", description="Audiencia por defecto")
    context_text: Optional[str] = Field(default=None, description="Contexto libre del negocio")


class WorkspaceResponse(BaseModel):
    """Response de un workspace."""

    id: str = Field(..., description="ID único del workspace")
    name: str = Field(..., description="Nombre del workspace")
    slug: str = Field(..., description="Slug único")
    workspace_type: str = Field(..., description="Tipo: organization|user|community")
    created_at: str = Field(..., description="Fecha de creación")
