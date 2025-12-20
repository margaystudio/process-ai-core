"""
Endpoint para consultar el catálogo de opciones.

Este endpoint permite obtener las opciones disponibles para cada dominio
(audience, formality, detail_level, language_style, business_type, etc.)
desde la base de datos.
"""

from fastapi import APIRouter
from sqlalchemy import select

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models_catalog import CatalogOption

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/{domain}")
async def get_catalog_options(domain: str):
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
async def list_domains():
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

