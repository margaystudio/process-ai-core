"""
Modelos de dominio específicos para procesos.

Estos modelos definen la estructura de datos para documentos de procesos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...domain_models import VideoRef


@dataclass
class Step:
    """
    Representa un paso del proceso dentro del documento final.
    """
    order: int
    actor: str
    action: str
    input: str
    output: str
    risks: str


@dataclass
class ProcessDocument:
    """
    Documento completo de proceso (modelo final parseado del JSON del LLM).
    """
    process_name: str
    objetivo: str
    contexto: str
    alcance: str
    inicio: str
    fin: str
    incluidos: str
    excluidos: str
    frecuencia: str
    disparadores: str
    actores_resumen: str
    sistemas: str
    inputs: str
    outputs: str
    pasos: List[Step]
    variantes: str
    excepciones: str
    metricas: str
    almacenamiento_datos: str
    usos_datos: str
    problemas: str
    oportunidades: str
    preguntas_abiertas: str
    material_referencia: str
    videos: List[VideoRef] = field(default_factory=list)


# ============================================================
# Esquema estricto de validación (Pydantic)
# ============================================================
#
# Los dataclasses de arriba son el modelo de dominio que consume el renderer.
# Los modelos Pydantic de abajo son la *compuerta de validación* del JSON que
# devuelve el LLM: garantizan la forma (tipos correctos, `pasos` como lista de
# objetos, etc.) y normalizan strings, antes de construir el dataclass. Si el
# LLM devuelve algo estructuralmente roto, `model_validate` lanza y el pipeline
# puede reintentar la generación.
#
# `PROCESS_DOCUMENT_SCHEMA_VERSION` versiona el contrato de salida para poder
# evolucionarlo sin romper compatibilidad (futuros migradores por versión).

PROCESS_DOCUMENT_SCHEMA_VERSION = 1

# Campos de texto libre del documento (todos string, normalizados con strip()).
_PROCESS_TEXT_FIELDS = (
    "process_name", "objetivo", "contexto", "alcance", "inicio", "fin",
    "incluidos", "excluidos", "frecuencia", "disparadores", "actores_resumen",
    "sistemas", "inputs", "outputs", "variantes", "excepciones", "metricas",
    "almacenamiento_datos", "usos_datos", "problemas", "oportunidades",
    "preguntas_abiertas", "material_referencia",
)


def _to_stripped_str(value: object) -> str:
    """Coerciona cualquier escalar a string recortado; None → ''."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_optional_str(value: object) -> Optional[str]:
    """Coerciona a string recortado o None si queda vacío."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class StepSchema(BaseModel):
    """Validación de un paso del proceso."""
    model_config = ConfigDict(extra="ignore")

    order: int = 0
    actor: str = ""
    action: str = ""
    input: str = ""
    output: str = ""
    risks: str = ""

    @field_validator("actor", "action", "input", "output", "risks", mode="before")
    @classmethod
    def _coerce_text(cls, v: object) -> str:
        return _to_stripped_str(v)

    @field_validator("order", mode="before")
    @classmethod
    def _coerce_order(cls, v: object) -> int:
        if v is None or v == "":
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


class VideoRefSchema(BaseModel):
    """Validación de una referencia a video."""
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    url: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None

    @field_validator("title", mode="before")
    @classmethod
    def _coerce_title(cls, v: object) -> str:
        return _to_stripped_str(v)

    @field_validator("url", "duration", "description", mode="before")
    @classmethod
    def _coerce_optional(cls, v: object) -> Optional[str]:
        return _to_optional_str(v)


class ProcessDocumentSchema(BaseModel):
    """
    Esquema estricto del documento de proceso devuelto por el LLM.

    Estricto en *forma* (tipos y estructura) pero tolerante en *presencia*:
    los campos faltantes toman default. Esto evita rechazar documentos válidos
    aunque sean ralos, a la vez que detecta estructuras rotas (p.ej. `pasos`
    que no es una lista) para disparar un reintento de generación.
    """
    model_config = ConfigDict(extra="ignore")

    schema_version: int = PROCESS_DOCUMENT_SCHEMA_VERSION

    process_name: str = ""
    objetivo: str = ""
    contexto: str = ""
    alcance: str = ""
    inicio: str = ""
    fin: str = ""
    incluidos: str = ""
    excluidos: str = ""
    frecuencia: str = ""
    disparadores: str = ""
    actores_resumen: str = ""
    sistemas: str = ""
    inputs: str = ""
    outputs: str = ""
    variantes: str = ""
    excepciones: str = ""
    metricas: str = ""
    almacenamiento_datos: str = ""
    usos_datos: str = ""
    problemas: str = ""
    oportunidades: str = ""
    preguntas_abiertas: str = ""
    material_referencia: str = ""

    pasos: List[StepSchema] = Field(default_factory=list)
    videos: List[VideoRefSchema] = Field(default_factory=list)

    @field_validator(*_PROCESS_TEXT_FIELDS, mode="before")
    @classmethod
    def _coerce_text(cls, v: object) -> str:
        return _to_stripped_str(v)

    @field_validator("pasos", "videos", mode="before")
    @classmethod
    def _none_to_list(cls, v: object) -> object:
        return [] if v is None else v

    def is_usable(self) -> bool:
        """
        Heurística de "documento servible": tiene al menos un paso o un objetivo
        con contenido. Se usa para decidir si conviene reintentar la generación.
        """
        return bool(self.pasos) or bool(self.objetivo.strip())

