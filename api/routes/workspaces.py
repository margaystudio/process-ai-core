"""
Endpoint para gestionar workspaces (clientes/organizaciones).

Este endpoint maneja:
- POST /api/v1/workspaces: Crear un nuevo workspace
- GET /api/v1/workspaces: Listar workspaces
- GET /api/v1/workspaces/{workspace_id}: Obtener un workspace
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import create_organization_workspace, get_workspace_by_slug
from process_ai_core.db.models import Workspace

from ..models.requests import WorkspaceCreateRequest, WorkspaceResponse

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(request: WorkspaceCreateRequest):
    """
    Crea un nuevo workspace (cliente/organización).

    Args:
        request: Datos del workspace a crear

    Returns:
        WorkspaceResponse con los datos del workspace creado

    Raises:
        400: Si el slug ya existe
        500: Error interno del servidor
    """
    with get_db_session() as session:
        try:
            # Verificar que el slug no exista
            existing = get_workspace_by_slug(session, request.slug)
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un workspace con el slug '{request.slug}'"
                )

            # Crear el workspace
            workspace = create_organization_workspace(
                session=session,
                name=request.name,
                slug=request.slug,
                country=request.country,
                business_type=request.business_type or "",
                language_style=request.language_style,
                default_audience=request.default_audience,
                context_text=request.context_text or "",
            )

            session.commit()

            return WorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                workspace_type=workspace.workspace_type,
                created_at=workspace.created_at.isoformat(),
            )

        except HTTPException:
            raise
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Error al crear workspace: {str(e)}"
            ) from e
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error interno: {str(e)}"
            ) from e


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces():
    """
    Lista todos los workspaces (clientes/organizaciones).

    Returns:
        Lista de WorkspaceResponse
    """
    with get_db_session() as session:
        workspaces = session.query(Workspace).filter_by(workspace_type="organization").all()
        return [
            WorkspaceResponse(
                id=w.id,
                name=w.name,
                slug=w.slug,
                workspace_type=w.workspace_type,
                created_at=w.created_at.isoformat(),
            )
            for w in workspaces
        ]


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str):
    """
    Obtiene un workspace por su ID.

    Args:
        workspace_id: ID del workspace

    Returns:
        WorkspaceResponse

    Raises:
        404: Si el workspace no existe
    """
    with get_db_session() as session:
        workspace = session.query(Workspace).filter_by(id=workspace_id).first()
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace {workspace_id} no encontrado"
            )

        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            workspace_type=workspace.workspace_type,
            created_at=workspace.created_at.isoformat(),
        )

