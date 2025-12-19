"""
Modelos de dominio específicos para procesos.

Estos modelos definen la estructura de datos para documentos de procesos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

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

