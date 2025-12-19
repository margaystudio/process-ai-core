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
from process_ai_core.db.models import Workspace, Document
from process_ai_core.db.helpers import get_workspace_metadata, get_document_metadata


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


def build_context_block(session, workspace: Workspace, document: Document) -> str:
    """
    Construye el bloque de contexto a partir de:

    1) Defaults del workspace (`Workspace`)
       - default_audience
       - default_formality
       - default_detail_level
       - language_style
       - business_type
       - context_text (texto libre)

    2) Overrides del documento (`Document`)
       - audience
       - formality
       - detail_level
       - process_type
       - context_text (texto libre)

    Regla de override
    -----------------
    Para audience / formality / detail_level:
    - Si `document.domain_metadata_json` tiene valor, se usa ese.
    - Si está vacío, se usa el default del workspace.

    Para process_type:
    - Es propio del documento. Si no está definido, se omite.

    Para language_style y business_type:
    - Son del workspace. Si no están definidos, se omiten.

    Cómo se arma el texto
    ---------------------
    - Se recorre una lista fija de dominios (business_type, language_style, etc.)
      y para cada uno se consulta el catálogo con `_prompt_for`.
    - Si existe prompt_text, se agrega como bullet: `- <prompt_text>`.
    - Al final se agregan bloques de texto libre (si existen), separados por líneas en blanco:
        * "Contexto del workspace:"
        * "Contexto del documento:"

    Args:
        session:
            Sesión SQLAlchemy activa.
        workspace:
            Instancia del workspace (contiene defaults y atributos de estilo global).
        document:
            Instancia del documento (contiene overrides y atributos específicos).

    Returns:
        String terminado en doble salto de línea (`\\n\\n`) para poder concatenarlo
        fácilmente al prompt principal.
    """
    # Obtener metadata desde JSON
    workspace_meta = get_workspace_metadata(workspace)
    document_meta = get_document_metadata(document)

    # Overrides por documento (si vacío => defaults del workspace)
    audience = document_meta.get("audience") or workspace_meta.get("default_audience", "")
    formality = document_meta.get("formality") or workspace_meta.get("default_formality", "")
    detail_level = document_meta.get("detail_level") or workspace_meta.get("default_detail_level", "")

    # Atributos propios del documento / workspace
    process_type = document_meta.get("process_type", "")
    language_style = workspace_meta.get("language_style", "")
    business_type = workspace_meta.get("business_type", "")

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
    workspace_context = workspace_meta.get("context_text", "")
    if workspace_context and workspace_context.strip():
        lines.append("")
        lines.append("Contexto del workspace:")
        lines.append(workspace_context.strip())

    document_context = document_meta.get("context_text", "")
    if document_context and document_context.strip():
        lines.append("")
        lines.append("Contexto del documento:")
        lines.append(document_context.strip())

    return "\n".join(lines).strip() + "\n\n"