"""
Endpoint para consultar el catálogo de opciones.

Este endpoint permite obtener las opciones disponibles para cada dominio
(audience, formality, detail_level, language_style, business_type, etc.)
desde la base de datos.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Generator

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models_catalog import CatalogOption
from ..dependencies import get_db
from ..request_identity import capture_request_identity
from ..workspace_client import require_process_ai_access, sync_workspace_access

# El catálogo es data de PLATAFORMA (no está scopeado por workspace) y su
# `prompt_text` entra a los prompts de generación de TODOS los tenants. Estaba
# sin auth: cualquiera podía leerlo, y cualquier usuario autenticado de
# cualquier tenant podía escribirlo — prompt-injection cruzado. Ahora se lee
# con sesión y acceso al módulo; escribir se hace por migración, no por HTTP
# (ver el comentario del POST eliminado más abajo).
router = APIRouter(
    prefix="/api/v1/catalog",
    tags=["catalog"],
    dependencies=[
        Depends(sync_workspace_access),
        Depends(capture_request_identity),
        Depends(require_process_ai_access),
    ],
)


class CreateCatalogOptionRequest(BaseModel):
    """Request para crear una nueva opción de catálogo."""
    domain: str
    value: Optional[str] = None  # Si no se proporciona, se genera desde label
    label: str
    prompt_text: Optional[str] = None
    sort_order: Optional[int] = None


@router.get("/{domain}")
def get_catalog_options(domain: str):
    """
    Obtiene todas las opciones activas para un dominio del catálogo.

    Args:
        domain: Dominio del catálogo (ej: "audience", "formality", "detail_level", "language_style", "business_type")

    Returns:
        Lista de opciones con label, value y sort_order
    """
    with get_db_session() as session:
        stmt = (
            select(CatalogOption)
            .where(
                CatalogOption.domain == domain,
                CatalogOption.is_active.is_(True),
            )
            .order_by(CatalogOption.sort_order, CatalogOption.label)
        )
        options = session.execute(stmt).scalars().all()

        return [
            {
                "value": opt.value,
                "label": opt.label,
                "sort_order": opt.sort_order,
            }
            for opt in options
        ]


@router.get("")
def list_domains():
    """
    Lista todos los dominios disponibles en el catálogo.

    Returns:
        Lista de dominios únicos
    """
    with get_db_session() as session:
        stmt = select(CatalogOption.domain).distinct().where(
            CatalogOption.is_active.is_(True)
        )
        domains = session.execute(stmt).scalars().all()
        return {"domains": list(domains)}


# NO existe `POST /api/v1/catalog`, a propósito.
#
# Creaba opciones de catálogo —una tabla GLOBAL, no scopeada por workspace— con
# solo estar autenticado, sin ningún rol. El campo `prompt_text` de esas
# opciones se inyecta en los prompts de generación de todos los tenants: un
# usuario de un tenant podía influir en lo que la IA genera para los demás.
# Ninguna pantalla lo usaba.
#
# El catálogo se siembra por migración/seed, que es lo que corresponde a un
# dato de plataforma.
