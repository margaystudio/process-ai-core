"""
Endpoints para gestionar invitaciones a workspaces (B2B).

Endpoints:
- POST /api/v1/workspaces/{workspace_id}/invitations: Crear invitación
- GET /api/v1/workspaces/{workspace_id}/invitations: Listar invitaciones
- POST /api/v1/invitations/{invitation_id}/accept: Aceptar invitación
- DELETE /api/v1/invitations/{invitation_id}: Cancelar invitación
"""

from typing import Optional
import logging
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from ..dependencies import get_db
from process_ai_core.db.helpers import (
    create_workspace_invitation,
    list_workspace_invitations,
    get_invitation_by_token,
    accept_invitation,
    get_pending_invitations_by_email,
)
from process_ai_core.db.models import Workspace, WorkspaceInvitation, Role, User, WorkspaceMembership
import uuid
from ..dependencies import get_current_user_id

logger = logging.getLogger(__name__)

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
    invitation_url: Optional[str] = None  # URL para aceptar la invitación
    token: Optional[str] = None  # Token de la invitación (para uso directo)

    class Config:
        from_attributes = True


class AcceptInvitationRequest(BaseModel):
    user_id: Optional[str] = None  # ID del usuario que acepta (opcional, se creará si no existe)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/workspaces/{workspace_id}/invitations", response_model=InvitationResponse)
async def create_invitation(
    workspace_id: str,
    request: CreateInvitationRequest,
    invited_by_user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
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
        role_id=role.id,  # Usar el ID del rol obtenido, no request.role_id
        expires_in_days=request.expires_in_days,
        message=request.message,
    )
    
    session.commit()
    
    # Generar URL de invitación
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    invitation_url = f"{frontend_url}/invitations/accept/{invitation.token}"
    
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
        invitation_url=invitation_url,
        token=invitation.token,  # Incluir el token directamente
    )


@router.get("/workspaces/{workspace_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    workspace_id: str,
    status: Optional[str] = None,  # "pending" | "accepted" | "expired" | "cancelled"
    session: Session = Depends(get_db),
):
    """
    Lista invitaciones de un workspace.
    """
    invitations = list_workspace_invitations(session, workspace_id, status=status)
    
    # Generar URL base para invitaciones
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    result = []
    for invitation in invitations:
        role = session.query(Role).filter_by(id=invitation.role_id).first()
        invitation_url = f"{frontend_url}/invitations/accept/{invitation.token}" if invitation.status == "pending" else None
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
            invitation_url=invitation_url,
            token=invitation.token,  # Incluir el token directamente
        ))
    
    return result


@router.get("/invitations/token/{token}", response_model=InvitationResponse)
async def get_invitation_by_token_endpoint(
    token: str,
    session: Session = Depends(get_db),
):
    """
    Obtiene información de una invitación por token (público, sin autenticación).
    """
    invitation = get_invitation_by_token(session, token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    
    # Verificar que la invitación esté pendiente y no haya expirado
    from datetime import datetime, UTC
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail=f"Invitación ya procesada (status: {invitation.status})")
    
    # Comparar datetimes: convertir ambos a naive para comparar
    # SQLite almacena datetimes como naive, así que convertimos datetime.now(UTC) a naive
    now_naive = datetime.now(UTC).replace(tzinfo=None)
    if invitation.expires_at < now_naive:
        raise HTTPException(status_code=400, detail="Invitación expirada")
    
    role = session.query(Role).filter_by(id=invitation.role_id).first()
    workspace = session.query(Workspace).filter_by(id=invitation.workspace_id).first()
    
    return InvitationResponse(
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
        invitation_url=None,  # No necesario en la respuesta
        token=invitation.token,  # Incluir el token directamente
    )


@router.post("/invitations/token/{token}/accept")
async def accept_invitation_by_token(
    token: str,
    request: AcceptInvitationRequest,
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_db),
):
    """
    Acepta una invitación usando el token (para uso público).
    
    ETAPA A: Implementación simplificada con UNA sola sesión y UNA transacción.
    
    Flujo:
    1. Validar token y obtener Invitation
    2. Resolver usuario local (crear si no existe)
    3. Crear WorkspaceMembership si no existe (idempotente)
    4. Marcar Invitation como accepted
    5. Crear AuditLogs
    6. Retornar respuesta completa
    
    Todo en una sola transacción: si algo falla, se hace rollback de todo.
    """
    logger.info(f"=== INICIO accept_invitation_by_token (ETAPA A) ===")
    logger.info(f"Token: {token}")
    logger.info(f"Request user_id: {request.user_id}")
    logger.info(f"Authorization header: {authorization is not None}")
    
    # Usar transacción explícita: todo o nada
    # Nota: get_db() hace commit automático al final, pero usamos begin() para control explícito
    try:
        # Iniciar transacción explícita
        trans = session.begin()
        try:
            # ============================================================
            # 1. Validar token y obtener Invitation
            # ============================================================
            invitation = get_invitation_by_token(session, token)
            if not invitation:
                raise HTTPException(status_code=404, detail="Invitación no encontrada")
            
            logger.info(f"Invitación encontrada: {invitation.id}, email: {invitation.email}, status: {invitation.status}")
            
            # Verificar si ya fue aceptada (idempotencia - ETAPA B)
            if invitation.status == "accepted":
                logger.info(f"Invitación ya aceptada, buscando membresía existente")
                
                # Extraer información del JWT para buscar el usuario correcto
                supabase_user_id_temp = None
                if authorization and authorization.startswith("Bearer "):
                    try:
                        import jwt as pyjwt
                        jwt_token = authorization.replace("Bearer ", "").strip()
                        decoded = pyjwt.decode(jwt_token, options={"verify_signature": False})
                        supabase_user_id_temp = decoded.get("sub")
                    except Exception:
                        pass
                
                # Buscar usuario por email de la invitación o por user_id del request
                user_for_check = None
                if request.user_id:
                    user_for_check = session.query(User).filter_by(id=request.user_id).first()
                if not user_for_check:
                    from process_ai_core.db.helpers import get_user_by_email
                    user_for_check = get_user_by_email(session, invitation.email)
                if not user_for_check and supabase_user_id_temp:
                    user_for_check = session.query(User).filter_by(external_id=supabase_user_id_temp).first()
                
                if user_for_check:
                    # Buscar membresía existente
                    existing_membership = session.query(WorkspaceMembership).filter_by(
                        workspace_id=invitation.workspace_id,
                        user_id=user_for_check.id
                    ).first()
                    
                    if existing_membership:
                        role = session.query(Role).filter_by(id=existing_membership.role_id).first()
                        logger.info(f"Retornando membresía existente: {existing_membership.id}")
                        # No hacer commit, solo retornar
                        trans.rollback()  # Rollback porque no hay cambios
                        return {
                            "message": "Invitación ya aceptada",
                            "status": "already_accepted",
                            "user_id": existing_membership.user_id,
                            "workspace_id": invitation.workspace_id,
                            "membership_id": existing_membership.id,
                            "role": role.name if role else None,
                        }
                
                # Si no hay membresía pero la invitación está aceptada, retornar 200 con estado
                logger.warning(f"Invitación aceptada pero membresía no encontrada")
                trans.rollback()  # Rollback porque no hay cambios
                return {
                    "message": "Invitación ya aceptada",
                    "status": "already_accepted",
                    "workspace_id": invitation.workspace_id,
                }
            
            # Verificar que esté pendiente
            if invitation.status != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invitación no está pendiente (status: {invitation.status})"
                )
            
            # Verificar expiración
            from datetime import datetime, UTC
            now_naive = datetime.now(UTC).replace(tzinfo=None)
            if now_naive > invitation.expires_at:
                invitation.status = "expired"
                session.flush()
                raise HTTPException(status_code=400, detail="Invitación expirada")
            
            # ============================================================
            # 2. Extraer información del JWT si está disponible
            # ============================================================
            supabase_user_id = None
            supabase_email = None
            
            if authorization and authorization.startswith("Bearer "):
                try:
                    import jwt as pyjwt
                    jwt_token = authorization.replace("Bearer ", "").strip()
                    decoded = pyjwt.decode(jwt_token, options={"verify_signature": False})
                    supabase_user_id = decoded.get("sub")
                    supabase_email = decoded.get("email")
                    logger.info(f"JWT decodificado: supabase_user_id={supabase_user_id}, email={supabase_email}")
                except Exception as e:
                    logger.warning(f"Error decodificando JWT: {e}")
            
            # Validar que el email del JWT coincida con el email de la invitación (ETAPA B)
            if supabase_email and supabase_email.lower() != invitation.email.lower():
                raise HTTPException(
                    status_code=403,
                    detail=f"El email autenticado ({supabase_email}) no coincide con el email de la invitación ({invitation.email})"
                )
            
            # ============================================================
            # 3. Resolver usuario local
            # ============================================================
            user = None
            user_created = False
            user_linked = False
            
            # Si viene user_id, intentar cargarlo
            if request.user_id:
                user = session.query(User).filter_by(id=request.user_id).first()
                if user:
                    logger.info(f"Usuario encontrado por user_id: {user.id} (email: {user.email})")
                else:
                    logger.info(f"Usuario {request.user_id} no encontrado, se buscará por email")
            
            # Si no se encontró por user_id, buscar por email
            if not user:
                from process_ai_core.db.helpers import get_user_by_email
                user = get_user_by_email(session, invitation.email)
                logger.info(f"Búsqueda por email {invitation.email}: {'encontrado' if user else 'no encontrado'}")
            
            # Si no existe, crearlo
            if not user:
                if not supabase_user_id:
                    raise HTTPException(
                        status_code=400,
                        detail="No se pudo obtener el ID de Supabase. Por favor, asegúrate de estar autenticado."
                    )
                
                logger.info(f"Creando usuario: {invitation.email} (Supabase ID: {supabase_user_id})")
                user = User(
                    id=str(uuid.uuid4()),
                    email=invitation.email,
                    name=invitation.email.split("@")[0],  # Nombre por defecto desde email
                    external_id=supabase_user_id,
                    auth_provider="supabase",
                )
                session.add(user)
                session.flush()  # Flush para obtener el ID
                user_created = True
                logger.info(f"✅ Usuario creado: {user.id}")
            else:
                # Usuario existe, verificar si necesita vincular con Supabase
                if user.external_id != supabase_user_id and supabase_user_id:
                    logger.info(f"Vinculando usuario {user.id} con Supabase ID {supabase_user_id}")
                    user.external_id = supabase_user_id
                    user.auth_provider = "supabase"
                    user_linked = True
                    logger.info(f"✅ Usuario vinculado con Supabase")
            
            # Validar que el email del usuario coincida con el de la invitación
            if user.email.lower() != invitation.email.lower():
                raise HTTPException(
                    status_code=403,
                    detail=f"El email del usuario ({user.email}) no coincide con el email de la invitación ({invitation.email})"
                )
            
            user_id = user.id
            
            # ============================================================
            # 4. Verificar límite de usuarios del workspace
            # ============================================================
            from process_ai_core.db.helpers import check_workspace_limit
            allowed, error_msg = check_workspace_limit(session, invitation.workspace_id, "users")
            if not allowed:
                raise HTTPException(status_code=400, detail=error_msg)
            
            # ============================================================
            # 5. Crear WorkspaceMembership si no existe (idempotente)
            # ============================================================
            membership = session.query(WorkspaceMembership).filter_by(
                workspace_id=invitation.workspace_id,
                user_id=user_id
            ).first()
            
            membership_created = False
            if not membership:
                # Obtener el rol de la invitación
                role = session.query(Role).filter_by(id=invitation.role_id).first()
                if not role:
                    raise HTTPException(status_code=400, detail=f"Rol con ID {invitation.role_id} no encontrado")
                
                logger.info(f"Creando membresía: user_id={user_id}, workspace_id={invitation.workspace_id}, role={role.name}")
                membership = WorkspaceMembership(
                    id=str(uuid.uuid4()),
                    workspace_id=invitation.workspace_id,
                    user_id=user_id,
                    role_id=invitation.role_id,
                    role=role.name,  # Compatibilidad
                )
                session.add(membership)
                session.flush()  # Flush para obtener el ID
                membership_created = True
                logger.info(f"✅ Membresía creada: {membership.id}")
                
                # Incrementar contador de usuarios
                from process_ai_core.db.helpers import increment_workspace_counter
                increment_workspace_counter(session, invitation.workspace_id, "users")
            else:
                logger.info(f"Membresía ya existe: {membership.id}, no se duplica")
                role = session.query(Role).filter_by(id=membership.role_id).first()
            
            # ============================================================
            # 6. Marcar Invitation como accepted
            # ============================================================
            invitation.status = "accepted"
            invitation.accepted_at = now_naive
            invitation.accepted_by_user_id = user_id
            logger.info(f"✅ Invitación marcada como aceptada")
            
            # ============================================================
            # 7. Crear AuditLogs
            # ============================================================
            from process_ai_core.db.helpers import create_audit_log
            import json
            
            # Audit log para aceptación de invitación
            # Nota: create_audit_log requiere document_id, pero para invitaciones no hay documento
            # Por ahora, crearemos un log más simple o usaremos metadata_json
            # TODO: Considerar crear un tipo de audit log más genérico
            
            # Por ahora, solo logueamos (los audit logs están diseñados para documentos)
            logger.info(f"Audit: invitation.accepted - invitation_id={invitation.id}, user_id={user_id}")
            if user_created:
                logger.info(f"Audit: user.created - user_id={user_id}, email={user.email}")
            if user_linked:
                logger.info(f"Audit: user.linked - user_id={user_id}, external_id={supabase_user_id}")
            if membership_created:
                logger.info(f"Audit: membership.created - membership_id={membership.id}, workspace_id={invitation.workspace_id}, role={role.name if role else 'N/A'}")
            
            # Commit explícito de la transacción
            trans.commit()
            logger.info(f"✅ Transacción commiteada exitosamente")
            
            # Retornar respuesta completa
            return {
                "message": "Invitación aceptada exitosamente",
                "status": "accepted",
                "user_id": user_id,
                "workspace_id": invitation.workspace_id,
                "membership_id": membership.id,
                "role": role.name if role else None,
            }
        except Exception as inner_e:
            # Rollback explícito si hay error dentro de la transacción
            trans.rollback()
            raise inner_e
            
    except HTTPException:
        # Re-raise HTTPExceptions sin modificar
        raise
    except ValueError as e:
        logger.error(f"Error aceptando invitación (ValueError): {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error inesperado aceptando invitación: {e}")
        # get_db() hará rollback automático si hay excepción
        raise HTTPException(status_code=500, detail=f"Error al aceptar invitación: {str(e)}")


@router.delete("/invitations/{invitation_id}")
async def cancel_invitation(
    invitation_id: str,
    session: Session = Depends(get_db),
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


@router.get("/invitations/pending/{email}", response_model=list[InvitationResponse])
async def get_pending_invitations_by_email_endpoint(
    email: str,
    session: Session = Depends(get_db),
):
    """
    Obtiene todas las invitaciones pendientes para un email (público, sin autenticación).
    """
    from datetime import datetime, UTC
    from process_ai_core.db.helpers import get_pending_invitations_by_email
    
    invitations = get_pending_invitations_by_email(session, email)
    
    # Generar URL base para invitaciones
    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    result = []
    for invitation in invitations:
        role = session.query(Role).filter_by(id=invitation.role_id).first()
        invitation_url = f"{frontend_url}/invitations/accept/{invitation.token}"
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
            invitation_url=invitation_url,
            token=invitation.token,  # Incluir el token directamente
        ))
    
    return result

