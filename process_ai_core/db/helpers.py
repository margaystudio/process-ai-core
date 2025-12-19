"""
Funciones helper para trabajar con los modelos genéricos (Workspace/Document).

Estas funciones facilitan:
- Crear workspaces/documents con metadata apropiada
- Obtener workspaces/documents por dominio
- Trabajar con metadata JSON
"""

from __future__ import annotations

import json
from typing import Dict, Any

from sqlalchemy.orm import Session

from .models import Workspace, Document, User, WorkspaceMembership


def create_organization_workspace(
    session: Session,
    name: str,
    slug: str,
    country: str = "UY",
    business_type: str = "",
    language_style: str = "es_uy_formal",
    default_audience: str = "operativo",
    default_formality: str = "media",
    default_detail_level: str = "estandar",
    context_text: str = "",
) -> Workspace:
    """
    Crea un Workspace de tipo "organization" (equivalente a Client).
    
    Args:
        session: Sesión de base de datos
        name: Nombre de la organización
        slug: Slug único
        country: Código de país (ISO2)
        business_type: Tipo de negocio
        language_style: Estilo de idioma
        default_audience: Audiencia por defecto
        default_formality: Formalidad por defecto
        default_detail_level: Nivel de detalle por defecto
        context_text: Contexto libre del negocio
    
    Returns:
        Workspace creado
    """
    metadata = {
        "country": country,
        "business_type": business_type,
        "language_style": language_style,
        "default_audience": default_audience,
        "default_formality": default_formality,
        "default_detail_level": default_detail_level,
        "context_text": context_text,
    }

    workspace = Workspace(
        slug=slug,
        name=name,
        workspace_type="organization",
        metadata_json=json.dumps(metadata),
    )
    session.add(workspace)
    return workspace


def create_user_workspace(
    session: Session,
    name: str,
    slug: str,
    preferences: Dict[str, Any] | None = None,
) -> Workspace:
    """
    Crea un Workspace de tipo "user" (para recetas personales, etc.).
    
    Args:
        session: Sesión de base de datos
        name: Nombre del usuario
        slug: Slug único
        preferences: Preferencias del usuario (cuisine, diet, etc.)
    
    Returns:
        Workspace creado
    """
    metadata = {"preferences": preferences or {}}

    workspace = Workspace(
        slug=slug,
        name=name,
        workspace_type="user",
        metadata_json=json.dumps(metadata),
    )
    session.add(workspace)
    return workspace


def create_process_document(
    session: Session,
    workspace_id: str,
    name: str,
    description: str = "",
    process_type: str = "",
    audience: str = "",
    formality: str = "",
    detail_level: str = "",
    context_text: str = "",
) -> Document:
    """
    Crea un Document de tipo "process" (equivalente a Process).
    
    Args:
        session: Sesión de base de datos
        workspace_id: ID del workspace
        name: Nombre del proceso
        description: Descripción breve
        process_type: Tipo de proceso
        audience: Audiencia (si vacío, usa default del workspace)
        formality: Formalidad (si vacío, usa default del workspace)
        detail_level: Nivel de detalle (si vacío, usa default del workspace)
        context_text: Contexto específico del proceso
    
    Returns:
        Document creado
    """
    metadata = {
        "process_type": process_type,
        "audience": audience,
        "formality": formality,
        "detail_level": detail_level,
        "context_text": context_text,
    }

    document = Document(
        workspace_id=workspace_id,
        domain="process",
        name=name,
        description=description,
        domain_metadata_json=json.dumps(metadata),
    )
    session.add(document)
    return document


def get_workspace_metadata(workspace: Workspace) -> Dict[str, Any]:
    """
    Obtiene la metadata de un workspace como dict.
    """
    try:
        return json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except:
        return {}


def get_document_metadata(document: Document) -> Dict[str, Any]:
    """
    Obtiene la metadata de un document como dict.
    """
    try:
        return json.loads(document.domain_metadata_json) if document.domain_metadata_json else {}
    except:
        return {}


def get_workspace_by_slug(session: Session, slug: str) -> Workspace | None:
    """
    Obtiene un workspace por su slug.
    """
    return session.query(Workspace).filter_by(slug=slug).first()


def get_documents_by_domain(session: Session, workspace_id: str, domain: str) -> list[Document]:
    """
    Obtiene todos los documentos de un dominio específico en un workspace.
    """
    return (
        session.query(Document)
        .filter_by(workspace_id=workspace_id, domain=domain)
        .order_by(Document.created_at.desc())
        .all()
    )

