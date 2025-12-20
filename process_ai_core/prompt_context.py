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
from process_ai_core.db.models import Workspace, Document, Process, Recipe, Folder
from process_ai_core.db.helpers import get_workspace_metadata


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
    Para audience / detail_level:
    - Si el documento es Process y tiene valores, se usan esos.
    - Si está vacío, se usa el default del workspace.

    Para formality:
    - Se obtiene del workspace (ya no es campo del documento).

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
    # Obtener metadata desde JSON del workspace
    workspace_meta = get_workspace_metadata(workspace)

    # Obtener valores del documento según su tipo
    audience = ""
    detail_level = ""
    document_context_text = ""
    
    if isinstance(document, Process):
        # Si es Process, usar campos específicos
        audience = document.audience or workspace_meta.get("default_audience", "")
        detail_level = document.detail_level or workspace_meta.get("default_detail_level", "")
        document_context_text = document.context_text or ""
    elif isinstance(document, Recipe):
        # Si es Recipe, no tiene audience/detail_level, usar defaults del workspace
        audience = workspace_meta.get("default_audience", "")
        detail_level = workspace_meta.get("default_detail_level", "")
        # Recipes no tienen context_text por ahora
        document_context_text = ""
    else:
        # Fallback para Document genérico (no debería pasar, pero por seguridad)
        audience = workspace_meta.get("default_audience", "")
        detail_level = workspace_meta.get("default_detail_level", "")
        document_context_text = ""
    
    # Formality ya no es campo del documento, solo del workspace
    formality = workspace_meta.get("default_formality", "")

    # Atributos propios del documento / workspace
    language_style = workspace_meta.get("language_style", "")
    business_type = workspace_meta.get("business_type", "")
    
    # Información de la carpeta (reemplaza process_type)
    folder_context = ""
    if document.folder_id:
        folder = session.query(Folder).filter_by(id=document.folder_id).first()
        if folder:
            # Usar el path completo de la carpeta como contexto
            folder_context = folder.path or folder.name

    lines: list[str] = []
    lines.append("=== CONTEXTO Y PREFERENCIAS (CATÁLOGOS) ===")

    for domain, val in [
        ("business_type", business_type),
        ("language_style", language_style),
        ("audience", audience),
        ("detail_level", detail_level),
        ("formality", formality),
    ]:
        txt = _prompt_for(session, domain, val)
        if txt:
            lines.append(f"- {txt}")
    
    # Agregar contexto de la carpeta si existe
    if folder_context:
        lines.append(f"- Ubicación del proceso: {folder_context}. Considera el contexto de esta ubicación al generar el documento.")

    # Contextos libres
    workspace_context = workspace_meta.get("context_text", "")
    if workspace_context and workspace_context.strip():
        lines.append("")
        lines.append("Contexto del workspace:")
        lines.append(workspace_context.strip())

    if document_context_text and document_context_text.strip():
        lines.append("")
        lines.append("Contexto del documento:")
        lines.append(document_context_text.strip())

    return "\n".join(lines).strip() + "\n\n"