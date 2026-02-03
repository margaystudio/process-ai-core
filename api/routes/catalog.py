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
from ..dependencies import get_current_user_id, get_db

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


class CreateCatalogOptionRequest(BaseModel):
    """Request para crear una nueva opción de catálogo."""
    domain: str
    value: Optional[str] = None  # Si no se proporciona, se genera desde label
    label: str
    prompt_text: Optional[str] = None
    sort_order: Optional[int] = None


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


@router.post("", response_model=dict)
async def create_catalog_option(
    request: CreateCatalogOptionRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Crea una nueva opción de catálogo.
    
    Args:
        request: Datos de la opción a crear
        user_id: ID del usuario actual (requerido para autenticación)
        session: Sesión de base de datos
    
    Returns:
        Opción creada con value, label y sort_order
    """
    try:
        # Verificar si ya existe una opción con el mismo domain y value
        # Primero necesitamos generar el value si no se proporciona
        value = request.value
        if not value:
            # Generar value desde label: lowercase, sin acentos, espacios a guiones
            import unicodedata
            import re
            value = unicodedata.normalize('NFD', request.label)
            value = re.sub(r'[\u0300-\u036f]', '', value)  # Eliminar acentos
            value = value.lower().strip()
            value = re.sub(r'[^a-z0-9\s-]', '', value)  # Solo letras, números, espacios y guiones
            value = re.sub(r'\s+', '-', value)  # Espacios a guiones
            value = re.sub(r'-+', '-', value)  # Múltiples guiones a uno
            value = value.strip('-')  # Eliminar guiones al inicio/final
        
        existing = session.execute(
            select(CatalogOption).where(
                CatalogOption.domain == request.domain,
                CatalogOption.value == value,
            )
        ).scalar_one_or_none()
        
        if existing:
            # Si existe pero está inactiva, reactivarla
            if not existing.is_active:
                existing.is_active = True
                if request.label:
                    existing.label = request.label
                if request.prompt_text:
                    existing.prompt_text = request.prompt_text
                if request.sort_order is not None:
                    existing.sort_order = request.sort_order
                session.commit()
                return {
                    "value": existing.value,
                    "label": existing.label,
                    "sort_order": existing.sort_order,
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe una opción con el valor '{value}' para el dominio '{request.domain}'"
                )
        
        # Obtener el máximo sort_order para este dominio
        max_sort = session.execute(
            select(CatalogOption.sort_order)
            .where(CatalogOption.domain == request.domain)
            .order_by(CatalogOption.sort_order.desc())
        ).scalar_one_or_none()
        
        # Crear nueva opción
        new_option = CatalogOption(
            domain=request.domain,
            value=value,
            label=request.label,
            prompt_text=request.prompt_text or f"Tipo de negocio: {request.label}",
            sort_order=request.sort_order if request.sort_order is not None else (max_sort + 10 if max_sort else 10),
            is_active=True,
        )
        
        session.add(new_option)
        session.commit()
        
        return {
            "value": new_option.value,
            "label": new_option.label,
            "sort_order": new_option.sort_order,
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear opción de catálogo: {str(e)}"
        ) from e



