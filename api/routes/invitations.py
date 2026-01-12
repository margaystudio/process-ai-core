"""
Endpoints para gestionar invitaciones a workspaces (B2B).

Endpoints:
- POST /api/v1/workspaces/{workspace_id}/invitations: Crear invitación
- GET /api/v1/workspaces/{workspace_id}/invitations: Listar invitaciones
- POST /api/v1/invitations/{invitation_id}/accept: Aceptar invitación
- DELETE /api/v1/invitations/{invitation_id}: Cancelar invitación
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import (
    create_workspace_invitation,
    list_workspace_invitations,
    get_invitation_by_token,
    accept_invitation,
)
from process_ai_core.db.models import Workspace, WorkspaceInvitation, Role
from ..dependencies import get_current_user_id

router = APIRouter(prefix="/api/v1", tags=["invitations"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role_id: Optional[str] = None  # ID del rol (opcional)
    role_name: Optional[str] = None  # Nombre del rol (opcional, se usa si role_id no está)
    expires_in_days: int = 7
    message: Optional[str] = None


class InvitationResponse(BaseModel):
    id: str
    workspace_id: str
    invited_by_user_id: str
    email: str
    role_id: str
    role_name: str
    status: str
    expires_at: str
    accepted_at: Optional[str]
    message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class AcceptInvitationRequest(BaseModel):
    user_id: str  # ID del usuario que acepta (debe coincidir con el email)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/workspaces/{workspace_id}/invitations", response_model=InvitationResponse)
async def create_invitation(
    workspace_id: str,
    request: CreateInvitationRequest,
    invited_by_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db_session),
):
    """
    Crea una invitación para unirse a un workspace.
    
    Args:
        workspace_id: ID del workspace
        request: Datos de la invitación
        invited_by_user_id: ID del usuario que invita (temporal, luego del JWT)
    """
    # Verificar que el workspace existe
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    
    # Obtener el rol (por ID o por nombre)
    role = None
    if request.role_id:
        role = session.query(Role).filter_by(id=request.role_id).first()
    elif request.role_name:
        role = session.query(Role).filter_by(name=request.role_name).first()
    
    if not role:
        raise HTTPException(status_code=400, detail="Rol no encontrado. Proporcione role_id o role_name")
    
    # Crear invitación
    invitation = create_workspace_invitation(
        session=session,
        workspace_id=workspace_id,
        invited_by_user_id=invited_by_user_id,
        email=request.email,
        role_id=request.role_id,
        expires_in_days=request.expires_in_days,
        message=request.message,
    )
    
    session.commit()
    
    return InvitationResponse(
        id=invitation.id,
        workspace_id=invitation.workspace_id,
        invited_by_user_id=invitation.invited_by_user_id,
        email=invitation.email,
        role_id=invitation.role_id,
        role_name=role.name,
        status=invitation.status,
        expires_at=invitation.expires_at.isoformat(),
        accepted_at=invitation.accepted_at.isoformat() if invitation.accepted_at else None,
        message=invitation.message,
        created_at=invitation.created_at.isoformat(),
    )


@router.get("/workspaces/{workspace_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    workspace_id: str,
    status: Optional[str] = None,  # "pending" | "accepted" | "expired" | "cancelled"
    session: Session = Depends(get_db_session),
):
    """
    Lista invitaciones de un workspace.
    """
    invitations = list_workspace_invitations(session, workspace_id, status=status)
    
    result = []
    for invitation in invitations:
        role = session.query(Role).filter_by(id=invitation.role_id).first()
        result.append(InvitationResponse(
            id=invitation.id,
            workspace_id=invitation.workspace_id,
            invited_by_user_id=invitation.invited_by_user_id,
            email=invitation.email,
            role_id=invitation.role_id,
            role_name=role.name if role else "unknown",
            status=invitation.status,
            expires_at=invitation.expires_at.isoformat(),
            accepted_at=invitation.accepted_at.isoformat() if invitation.accepted_at else None,
            message=invitation.message,
            created_at=invitation.created_at.isoformat(),
        ))
    
    return result


@router.post("/invitations/{invitation_id}/accept")
async def accept_invitation_endpoint(
    invitation_id: str,
    request: AcceptInvitationRequest,
    session: Session = Depends(get_db_session),
):
    """
    Acepta una invitación y crea la membresía del usuario.
    """
    try:
        invitation = accept_invitation(
            session=session,
            invitation_id=invitation_id,
            user_id=request.user_id,
        )
        session.commit()
        
        return {
            "message": "Invitación aceptada exitosamente",
            "workspace_id": invitation.workspace_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error al aceptar invitación: {str(e)}")


@router.post("/invitations/token/{token}/accept")
async def accept_invitation_by_token(
    token: str,
    request: AcceptInvitationRequest,
    session: Session = Depends(get_db_session),
):
    """
    Acepta una invitación usando el token (para uso público).
    """
    invitation = get_invitation_by_token(session, token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    
    try:
        invitation = accept_invitation(
            session=session,
            invitation_id=invitation.id,
            user_id=request.user_id,
        )
        session.commit()
        
        return {
            "message": "Invitación aceptada exitosamente",
            "workspace_id": invitation.workspace_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error al aceptar invitación: {str(e)}")


@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    invitation_id: str,
    session: Session = Depends(get_db_session),
):
    """
    Cancela una invitación pendiente.
    """
    invitation = session.query(WorkspaceInvitation).filter_by(id=invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail=f"Invitación ya procesada (status: {invitation.status})")
    
    invitation.status = "cancelled"
    session.commit()
    
    return {"message": "Invitación cancelada exitosamente"}

