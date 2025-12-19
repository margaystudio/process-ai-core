# process_ai_core/document_profiles.py
from __future__ import annotations

"""
process_ai_core.document_profiles
=================================

Perfiles de documento (presentación) para el render final.

Este módulo define "perfiles" que controlan *cómo* se presenta un mismo
`ProcessDocument` según el público objetivo (por ejemplo: operativo vs gestión).

Responsabilidad
---------------
- Definir perfiles preconfigurados (v1) con:
  - qué secciones se muestran (`show`)
  - cómo se titulan esas secciones (`titles`)
  - qué formato se usa para los pasos (`steps_format`)

NO hace
-------
- No transforma contenido del proceso
- No decide qué "dice" el documento (eso lo genera el LLM y lo parsea doc_engine)
- No renderiza Markdown (eso lo hace `doc_engine.render_markdown`)

Idea clave
----------
Un mismo JSON de `ProcessDocument` puede renderizarse de forma distinta
dependiendo del perfil. Esto permite reutilizar la misma fuente de verdad
y ajustar el output a distintos públicos.

Extensibilidad
--------------
Es esperable que este módulo crezca con nuevas variantes:
- perfiles por industria
- perfiles por cliente
- perfiles por norma (ISO, auditoría)
- versiones v2/v3 (evolución del formato)

Recomendación práctica
----------------------
Mantener `id` estable (sirve para tracking, logs, tests, comparar versiones).
"""

from dataclasses import dataclass
from typing import Dict, List, Literal

# Modo general (público objetivo / intención del documento)
Mode = Literal["operativo", "gestion"]


@dataclass(frozen=True)
class DocumentProfile:
    """
    Define un perfil de render para un documento de proceso.

    Attributes
    ----------
    id:
        Identificador estable del perfil (útil para logging, versionado y tests).
        Ej: "operativo_v1", "gestion_v1".
    mode:
        Modo principal del perfil. Se usa para seleccionar defaults.
        Valores permitidos: "operativo" | "gestion".
    label:
        Etiqueta humana del perfil (para UI / debugging).
    show:
        Lista de claves de secciones que deben renderizarse.
        Estas claves deben estar alineadas con lo que soporta `doc_engine.render_markdown`.
        Ej: "objetivo", "pasos", "riesgos", etc.
    titles:
        Mapeo de clave de sección → título que se renderiza en el documento.
        Permite adaptar el lenguaje al público.
    steps_format:
        Formato de render de la sección `pasos`:
        - "lista": bullets/estructura narrativa
        - "tabla": tabla Markdown (más apto para gestión/controles)
    """

    id: str
    mode: Mode
    label: str

    # Qué secciones mostrar (controla estructura)
    show: List[str]

    # Títulos por sección (controla lenguaje)
    titles: Dict[str, str]

    # Formato de pasos
    steps_format: Literal["lista", "tabla"] = "lista"


# ============================================================
# Perfiles predefinidos (V1)
# ============================================================

OPERATIVO_V1 = DocumentProfile(
    id="operativo_v1",
    mode="operativo",
    label="Operativo (pistero)",
    show=[
        "objetivo",
        "pasos",
        "excepciones",
        "preguntas_abiertas",
    ],
    titles={
        "objetivo": "Qué hay que hacer",
        "pasos": "Cómo hacerlo (paso a paso)",
        "excepciones": "Si algo sale mal / casos especiales",
        "preguntas_abiertas": "Dudas para confirmar",
    },
    steps_format="lista",
)

GESTION_V1 = DocumentProfile(
    id="gestion_v1",
    mode="gestion",
    label="Gestión / Dueños",
    show=[
        "objetivo",
        "contexto",
        "alcance",
        "frecuencia",
        "actores",
        "sistemas",
        "pasos",
        "riesgos",
        "metricas",
        "oportunidades",
        "preguntas_abiertas",
    ],
    titles={
        "objetivo": "Objetivo",
        "contexto": "Contexto",
        "alcance": "Alcance",
        "frecuencia": "Frecuencia y disparadores",
        "actores": "Actores y responsabilidades",
        "sistemas": "Sistemas, datos y evidencias",
        "pasos": "Descripción paso a paso",
        "riesgos": "Riesgos principales",
        "metricas": "Indicadores",
        "oportunidades": "Oportunidades de mejora",
        "preguntas_abiertas": "Preguntas abiertas / pendientes",
    },
    steps_format="tabla",
)


# ============================================================
# Selector de perfil
# ============================================================

def get_profile(mode: Mode) -> DocumentProfile:
    """
    Devuelve el perfil por defecto para un `mode`.

    Parameters
    ----------
    mode:
        "operativo" o "gestion".

    Returns
    -------
    DocumentProfile
        Perfil predefinido V1 correspondiente.

    Notes
    -----
    - Hoy la selección es binaria (operativo vs gestión).
    - En el futuro puede evolucionar a:
        - `get_profile(client_id, mode, version=...)`
        - perfiles cargados desde DB o config
        - feature flags por cliente
    """
    return OPERATIVO_V1 if mode == "operativo" else GESTION_V1