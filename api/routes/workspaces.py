"""
Endpoint para gestionar workspaces (clientes/organizaciones).

Este endpoint maneja:
- POST /api/v1/workspaces: Crear un nuevo workspace
- GET /api/v1/workspaces: Listar workspaces
- GET /api/v1/workspaces/{workspace_id}: Obtener un workspace
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from process_ai_core.db.database import get_db_session
from ..dependencies import get_db
from process_ai_core.db.helpers import (
    create_organization_workspace, 
    get_workspace_by_slug,
    create_workspace_subscription,
    get_subscription_plan_by_name,
    add_user_to_workspace_helper,
)
from process_ai_core.db.models import Workspace
from ..dependencies import get_current_user_id, require_superadmin
from ..models.requests import WorkspaceCreateRequest, WorkspaceResponse

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse)
async def create_workspace(
    request: WorkspaceCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Crea un nuevo workspace.
    
    - Si workspace_type es "organization" (B2B): requiere superadmin
    - Si workspace_type es "user" (B2C): cualquier usuario autenticado puede crear su propio workspace

    Args:
        request: Datos del workspace a crear
        user_id: ID del usuario actual (de JWT)
        session: Sesión de base de datos

    Returns:
        WorkspaceResponse con los datos del workspace creado

    Raises:
        400: Si el slug ya existe
        403: Si no tiene permisos (B2B requiere superadmin)
        500: Error interno del servidor
    """
    from ..dependencies import is_superadmin
    
    # Verificar permisos según tipo de workspace
    if request.workspace_type == "organization":
        # B2B: requiere superadmin
        if not is_superadmin(user_id, session):
            raise HTTPException(
                status_code=403,
                detail="Superadmin access required to create organization workspaces"
            )
    elif request.workspace_type == "user":
        # B2C: cualquier usuario puede crear su propio workspace
        # El workspace será asociado automáticamente al usuario
        pass
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workspace_type: {request.workspace_type}"
        )
    
    try:
        # Verificar que el slug no exista
        existing = get_workspace_by_slug(session, request.slug)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un workspace con el slug '{request.slug}'"
            )

        # Crear el workspace según tipo
        if request.workspace_type == "organization":
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
            
            # Asignar plan de suscripción (por defecto trial para B2B)
            plan = get_subscription_plan_by_name(session, "b2b_trial")
            if plan:
                create_workspace_subscription(
                    session=session,
                    workspace_id=workspace.id,
                    plan_id=plan.id,
                    status="trial",
                )
            
            # Asociar el usuario que crea el workspace como admin (si es superadmin)
            # Esto permite que el superadmin vea y gestione el workspace que creó
            if is_superadmin(user_id, session):
                add_user_to_workspace_helper(session, user_id, workspace.id, "admin")
        else:
            # B2C: crear workspace de usuario
            from process_ai_core.db.helpers import create_user_workspace
            workspace = create_user_workspace(
                session=session,
                name=request.name,
                slug=request.slug,
            )
            
            # Asignar plan de suscripción (por defecto free para B2C)
            plan = get_subscription_plan_by_name(session, "b2c_free")
            if plan:
                create_workspace_subscription(
                    session=session,
                    workspace_id=workspace.id,
                    plan_id=plan.id,
                    status="active",
                )
            
            # Asociar usuario como owner
            add_user_to_workspace_helper(session, user_id, workspace.id, "owner")

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

