from __future__ import annotations

"""
process_ai_core.prompt_context
==============================

Este módulo construye un **bloque de contexto** para anteponer al prompt principal
que se le envía al LLM.

Idea central
------------
En vez de hardcodear instrucciones (“modo gestión”, “formalidad alta”, etc.),
el texto se obtiene desde un **catálogo parametrizable en base de datos**
(`CatalogOption`), permitiendo:

- Ajustar estilo / audiencia / nivel de detalle sin tocar código.
- Reutilizar estándares por cliente (defaults) y permitir overrides por proceso.
- Mantener consistencia en prompts para distintos procesos del mismo cliente.

Salidas
-------
- `build_context_block(...)` devuelve un string con formato tipo:

    === CONTEXTO Y PREFERENCIAS (CATÁLOGOS) ===
    - <prompt_text business_type>
    - <prompt_text language_style>
    - <prompt_text process_type>
    - <prompt_text audience>
    - <prompt_text detail_level>
    - <prompt_text formality>

    Contexto del cliente:
    ...

    Contexto del proceso:
    ...

Ese bloque se concatena con el resto del prompt (transcripciones, evidencia, etc.).
"""

from typing import Optional

from sqlalchemy import select

from process_ai_core.db.models_catalog import CatalogOption
from process_ai_core.db.models import Client, Process  # ajustá el import si tu módulo se llama distinto


def _prompt_for(session, domain: str, value: Optional[str]) -> str:
    """
    Obtiene el texto de prompt (`prompt_text`) desde el catálogo para una combinación
    (domain, value).

    El catálogo está modelado por `CatalogOption`, y se asume que:
    - `domain` agrupa categorías (ej: "audience", "formality", "detail_level").
    - `value` es la opción elegida dentro del dominio (ej: "direccion", "alta", "estandar").
    - `is_active` permite habilitar/deshabilitar opciones sin borrar datos.

    Reglas:
    - Si `value` es None o string vacío → retorna "".
    - Si no existe una opción activa en catálogo para (domain, value) → retorna "".
    - Si existe → retorna el `prompt_text` asociado.

    Args:
        session:
            Sesión SQLAlchemy activa.
        domain:
            Dominio del catálogo (ej: "audience").
        value:
            Valor elegido (ej: "direccion").

    Returns:
        Texto del prompt para inyectar al bloque de contexto, o string vacío si no aplica.
    """
    if not value:
        return ""

    stmt = (
        select(CatalogOption.prompt_text)
        .where(
            CatalogOption.domain == domain,
            CatalogOption.value == value,
            CatalogOption.is_active.is_(True),
        )
        .limit(1)
    )
    out = session.execute(stmt).scalar_one_or_none()
    return out or ""


def build_context_block(session, client: Client, process: Process) -> str:
    """
    Construye el bloque de contexto a partir de:

    1) Defaults del cliente (`Client`)
       - default_audience
       - default_formality
       - default_detail_level
       - language_style
       - business_type
       - context_text (texto libre)

    2) Overrides del proceso (`Process`)
       - audience
       - formality
       - detail_level
       - process_type
       - context_text (texto libre)

    Regla de override
    -----------------
    Para audience / formality / detail_level:
    - Si `process.<campo>` tiene valor truthy (no vacío / no None), se usa ese.
    - Si está vacío, se usa el default del cliente.

    Para process_type:
    - Es propio del proceso. Si no está definido, se omite.

    Para language_style y business_type:
    - Son del cliente. Si no están definidos, se omiten.

    Cómo se arma el texto
    ---------------------
    - Se recorre una lista fija de dominios (business_type, language_style, etc.)
      y para cada uno se consulta el catálogo con `_prompt_for`.
    - Si existe prompt_text, se agrega como bullet: `- <prompt_text>`.
    - Al final se agregan bloques de texto libre (si existen), separados por líneas en blanco:
        * "Contexto del cliente:"
        * "Contexto del proceso:"

    Args:
        session:
            Sesión SQLAlchemy activa.
        client:
            Instancia del cliente (contiene defaults y atributos de estilo global).
        process:
            Instancia del proceso (contiene overrides y atributos específicos del proceso).

    Returns:
        String terminado en doble salto de línea (`\\n\\n`) para poder concatenarlo
        fácilmente al prompt principal.
    """

    # Overrides por proceso (si vacío => defaults del cliente)
    audience = process.audience or client.default_audience
    formality = process.formality or client.default_formality
    detail_level = process.detail_level or client.default_detail_level

    # Atributos propios del proceso / cliente
    process_type = process.process_type or ""
    language_style = client.language_style or ""
    business_type = client.business_type or ""

    lines: list[str] = []
    lines.append("=== CONTEXTO Y PREFERENCIAS (CATÁLOGOS) ===")

    for domain, val in [
        ("business_type", business_type),
        ("language_style", language_style),
        ("process_type", process_type),
        ("audience", audience),
        ("detail_level", detail_level),
        ("formality", formality),
    ]:
        txt = _prompt_for(session, domain, val)
        if txt:
            lines.append(f"- {txt}")

    # Contextos libres
    if client.context_text and client.context_text.strip():
        lines.append("")
        lines.append("Contexto del cliente:")
        lines.append(client.context_text.strip())

    if process.context_text and process.context_text.strip():
        lines.append("")
        lines.append("Contexto del proceso:")
        lines.append(process.context_text.strip())

    return "\n".join(lines).strip() + "\n\n"