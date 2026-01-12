"""
Perfiles de documento (presentación) para el render final de recetas.

Este módulo define "perfiles" que controlan *cómo* se presenta un mismo
`RecipeDocument` según el público objetivo (por ejemplo: simple vs detallado).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal

# Modo general (público objetivo / intención del documento)
Mode = Literal["simple", "detallado"]


@dataclass(frozen=True)
class RecipeProfile:
    """
    Define un perfil de render para un documento de receta.

    Attributes
    ----------
    id:
        Identificador estable del perfil (útil para logging, versionado y tests).
        Ej: "simple_v1", "detallado_v1".
    mode:
        Modo principal del perfil. Se usa para seleccionar defaults.
        Valores permitidos: "simple" | "detallado".
    label:
        Etiqueta humana del perfil (para UI / debugging).
    show:
        Lista de claves de secciones que deben renderizarse.
        Estas claves deben estar alineadas con lo que soporta `RecipeRenderer.render_markdown`.
        Ej: "description", "ingredients", "instructions", etc.
    titles:
        Mapeo de clave de sección → título que se renderiza en el documento.
        Permite adaptar el lenguaje al público.
    """

    id: str
    mode: Mode
    label: str

    # Qué secciones mostrar (controla estructura)
    show: List[str]

    # Títulos por sección (controla lenguaje)
    titles: Dict[str, str]


# ============================================================
# Perfiles predefinidos (V1)
# ============================================================

SIMPLE_V1 = RecipeProfile(
    id="simple_v1",
    mode="simple",
    label="Simple (rápido)",
    show=[
        "description",
        "info",
        "ingredients",
        "instructions",
        "tips",
    ],
    titles={
        "description": "Descripción",
        "info": "Información",
        "ingredients": "Ingredientes",
        "instructions": "Instrucciones",
        "tips": "Consejos",
    },
)

DETALLADO_V1 = RecipeProfile(
    id="detallado_v1",
    mode="detallado",
    label="Detallado (completo)",
    show=[
        "description",
        "info",
        "equipment",
        "ingredients",
        "instructions",
        "tips",
        "variations",
        "storage",
        "nutritional_info",
        "videos",
    ],
    titles={
        "description": "Descripción",
        "info": "Información",
        "equipment": "Equipamiento necesario",
        "ingredients": "Ingredientes",
        "instructions": "Instrucciones paso a paso",
        "tips": "Consejos y tips",
        "variations": "Variaciones",
        "storage": "Conservación y almacenamiento",
        "nutritional_info": "Información nutricional",
        "videos": "Videos relacionados",
    },
)


# ============================================================
# Selector de perfil
# ============================================================

def get_profile(mode: Mode) -> RecipeProfile:
    """
    Devuelve el perfil por defecto para un `mode`.

    Parameters
    ----------
    mode:
        "simple" o "detallado".

    Returns
    -------
    RecipeProfile
        Perfil predefinido V1 correspondiente.

    Notes
    -----
    - Hoy la selección es binaria (simple vs detallado).
    - En el futuro puede evolucionar a:
        - `get_profile(workspace_id, mode, version=...)`
        - perfiles cargados desde DB o config
        - feature flags por workspace
    """
    return SIMPLE_V1 if mode == "simple" else DETALLADO_V1



