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
    audience: Optional[str] = Field(
        default=None,
        description="Audiencia objetivo (ej: direccion, operativo, rrhh)",
    )
    detail_level: Optional[str] = Field(
        default=None,
        description="Nivel de detalle (ej: breve, estandar, detallado)",
    )
    formality: Optional[str] = Field(
        default=None,
        description="Nivel de formalidad (ej: baja, media, alta)",
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

