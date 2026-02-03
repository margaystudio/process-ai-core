"""
Endpoints para superadmin (B2B).

Este módulo maneja operaciones que solo pueden realizar superadmins:
- Crear workspaces B2B
- Asignar planes de suscripción
- Invitar admins a workspaces
- Ver todos los workspaces
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from ..dependencies import get_db
from process_ai_core.db.helpers import (
    create_organization_workspace,
    get_workspace_by_slug,
    create_workspace_subscription,
    get_subscription_plan,
    get_subscription_plan_by_name,
    create_workspace_invitation,
    add_user_to_workspace_helper,
)
from process_ai_core.db.models import Workspace, Role
from ..dependencies import require_superadmin, get_current_user_id
from ..models.requests import WorkspaceResponse

router = APIRouter(prefix="/api/v1/superadmin", tags=["superadmin"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateB2BWorkspaceRequest(BaseModel):
    name: str
    slug: str
    country: str = "UY"
    business_type: Optional[str] = None
    language_style: str = "es_uy_formal"
    default_audience: str = "operativo"
    context_text: Optional[str] = None
    plan_name: str = "b2b_trial"  # Plan inicial
    admin_email: EmailStr  # Email del admin a invitar


class InviteAdminRequest(BaseModel):
    workspace_id: str
    email: EmailStr
    message: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/workspaces", response_model=WorkspaceResponse)
async def create_b2b_workspace(
    request: CreateB2BWorkspaceRequest,
    superadmin_id: str = Depends(require_superadmin),
    session: Session = Depends(get_db),
):
    """
    Crea un nuevo workspace B2B (organización) y asigna plan de suscripción.
    También invita automáticamente al admin de la organización.
    
    Solo accesible para superadmins.
    """
    # Verificar que el slug no exista
    existing = get_workspace_by_slug(session, request.slug)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un workspace con el slug '{request.slug}'"
        )
    
    # Verificar que el plan existe
    plan = get_subscription_plan_by_name(session, request.plan_name)
    if not plan:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{request.plan_name}' no encontrado"
        )
    
    if plan.plan_type != "b2b":
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{request.plan_name}' no es un plan B2B"
        )
    
    # Crear workspace
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
    
    # Asignar plan de suscripción
    subscription = create_workspace_subscription(
        session=session,
        workspace_id=workspace.id,
        plan_id=plan.id,
        status="trial" if "trial" in request.plan_name.lower() else "active",
    )
    
    # Obtener rol "owner" para el admin
    owner_role = session.query(Role).filter_by(name="owner").first()
    if not owner_role:
        raise HTTPException(
            status_code=500,
            detail="Rol 'owner' no encontrado en el sistema"
        )
    
    # Crear invitación para el admin
    invitation = create_workspace_invitation(
        session=session,
        workspace_id=workspace.id,
        invited_by_user_id=superadmin_id,
        email=request.admin_email,
        role_id=owner_role.id,
        expires_in_days=7,
        message=request.message or f"Has sido invitado como administrador de {request.name}",
    )
    
    session.commit()
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        workspace_type=workspace.workspace_type,
        created_at=workspace.created_at.isoformat(),
    )


@router.post("/workspaces/{workspace_id}/invite-admin")
async def invite_admin_to_workspace(
    workspace_id: str,
    request: InviteAdminRequest,
    superadmin_id: str = Depends(require_superadmin),
    session: Session = Depends(get_db),
):
    """
    Invita a un admin a unirse a un workspace B2B.
    
    Solo accesible para superadmins.
    """
    # Verificar que el workspace existe y es B2B
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    
    if workspace.workspace_type != "organization":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden invitar admins a workspaces B2B"
        )
    
    # Obtener rol "owner" o "admin"
    admin_role = session.query(Role).filter_by(name="owner").first()
    if not admin_role:
        admin_role = session.query(Role).filter_by(name="admin").first()
    
    if not admin_role:
        raise HTTPException(
            status_code=500,
            detail="Rol 'owner' o 'admin' no encontrado"
        )
    
    # Crear invitación
    invitation = create_workspace_invitation(
        session=session,
        workspace_id=workspace_id,
        invited_by_user_id=superadmin_id,
        email=request.email,
        role_id=admin_role.id,
        expires_in_days=7,
        message=request.message,
    )
    
    session.commit()
    
    return {
        "message": "Invitación creada exitosamente",
        "invitation_id": invitation.id,
        "token": invitation.token,  # Para enviar por email
    }


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_all_workspaces(
    workspace_type: Optional[str] = None,  # "organization" | "user"
    superadmin_id: str = Depends(require_superadmin),
    session: Session = Depends(get_db),
):
    """
    Lista todos los workspaces del sistema.
    
    Solo accesible para superadmins.
    """
    query = session.query(Workspace)
    if workspace_type:
        query = query.filter_by(workspace_type=workspace_type)
    
    workspaces = query.order_by(Workspace.created_at.desc()).all()
    
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


