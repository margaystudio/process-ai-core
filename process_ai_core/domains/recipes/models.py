"""
Modelos de dominio específicos para recetas.

Estos modelos definen la estructura de datos para documentos de recetas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ...domain_models import VideoRef


@dataclass
class Ingredient:
    """
    Representa un ingrediente de la receta.
    """
    name: str
    quantity: str
    unit: str
    notes: str = ""


@dataclass
class Instruction:
    """
    Representa un paso de instrucción en la receta.
    """
    order: int
    instruction: str
    duration: Optional[str] = None
    temperature: Optional[str] = None
    tips: str = ""


@dataclass
class RecipeDocument:
    """
    Documento completo de receta (modelo final parseado del JSON del LLM).
    """
    recipe_name: str
    description: str
    cuisine: str
    difficulty: str  # "fácil" | "media" | "difícil"
    servings: int
    prep_time: str  # ej: "15 minutos"
    cook_time: str  # ej: "30 minutos"
    total_time: str  # ej: "45 minutos"
    ingredients: List[Ingredient]
    instructions: List[Instruction]
    tips: str
    variations: str
    storage: str
    nutritional_info: str
    equipment: str
    videos: List[VideoRef] = field(default_factory=list)

