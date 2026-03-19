"""
Endpoints para roles operativos por workspace y asignación a usuarios.

- GET/POST /api/v1/workspaces/{workspace_id}/operational-roles
- PUT/DELETE /api/v1/operational-roles/{operational_role_id}
- POST/DELETE /api/v1/workspace-memberships/{membership_id}/operational-roles
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import re
import uuid

from process_ai_core.db.models import (
    Workspace, OperationalRole, UserOperationalRole, WorkspaceMembership,
)
from api.dependencies import get_db, get_current_user_id
from process_ai_core.db.permissions import get_user_role

from ..models.requests import (
    OperationalRoleCreateRequest,
    OperationalRoleUpdateRequest,
    OperationalRoleResponse,
    OperationalRoleAssignRequest,
)

router = APIRouter(prefix="/api/v1", tags=["operational-roles"])


def _slugify(name: str) -> str:
    """Genera slug a partir del nombre."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "_", s)
    return s[:100] or "rol"


def _require_workspace_admin(session: Session, user_id: str, workspace_id: str) -> None:
    """Lanza 403 si el usuario no es owner/admin del workspace."""
    role = get_user_role(session, user_id, workspace_id)
    if not role or role.name not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Se requiere rol owner o admin en el workspace",
        )


@router.get("/workspaces/{workspace_id}/operational-roles", response_model=list[OperationalRoleResponse])
async def list_operational_roles(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """Lista los roles operativos del workspace."""
    _require_workspace_admin(session, user_id, workspace_id)
    ws = session.query(Workspace).filter_by(id=workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    roles = session.query(OperationalRole).filter_by(workspace_id=workspace_id).order_by(OperationalRole.name).all()
    return [
        OperationalRoleResponse(
            id=r.id,
            workspace_id=r.workspace_id,
            name=r.name,
            slug=r.slug,
            description=r.description or "",
            is_active=r.is_active,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in roles
    ]


@router.post("/workspaces/{workspace_id}/operational-roles", response_model=OperationalRoleResponse)
async def create_operational_role(
    workspace_id: str,
    request: OperationalRoleCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """Crea un rol operativo en el workspace."""
    _require_workspace_admin(session, user_id, workspace_id)
    ws = session.query(Workspace).filter_by(id=workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    slug = request.slug or _slugify(request.name)
    existing = session.query(OperationalRole).filter_by(workspace_id=workspace_id, slug=slug).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un rol operativo con slug '{slug}' en este workspace")
    role = OperationalRole(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=request.name,
        slug=slug,
        description=request.description or "",
        is_active=True,
    )
    session.add(role)
    session.flush()
    return OperationalRoleResponse(
        id=role.id,
        workspace_id=role.workspace_id,
        name=role.name,
        slug=role.slug,
        description=role.description or "",
        is_active=role.is_active,
        created_at=role.created_at.isoformat(),
        updated_at=role.updated_at.isoformat(),
    )


@router.put("/operational-roles/{operational_role_id}", response_model=OperationalRoleResponse)
async def update_operational_role(
    operational_role_id: str,
    request: OperationalRoleUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """Actualiza un rol operativo."""
    role = session.query(OperationalRole).filter_by(id=operational_role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol operativo no encontrado")
    _require_workspace_admin(session, user_id, role.workspace_id)
    if request.name is not None:
        role.name = request.name
    if request.description is not None:
        role.description = request.description
    if request.is_active is not None:
        role.is_active = request.is_active
    session.flush()
    return OperationalRoleResponse(
        id=role.id,
        workspace_id=role.workspace_id,
        name=role.name,
        slug=role.slug,
        description=role.description or "",
        is_active=role.is_active,
        created_at=role.created_at.isoformat(),
        updated_at=role.updated_at.isoformat(),
    )


@router.delete("/operational-roles/{operational_role_id}")
async def delete_operational_role(
    operational_role_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """Elimina un rol operativo."""
    role = session.query(OperationalRole).filter_by(id=operational_role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rol operativo no encontrado")
    _require_workspace_admin(session, user_id, role.workspace_id)
    session.delete(role)
    return {"message": "Rol operativo eliminado", "id": operational_role_id}


@router.post("/workspace-memberships/{membership_id}/operational-roles")
async def assign_operational_roles_to_membership(
    membership_id: str,
    request: OperationalRoleAssignRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """Asigna roles operativos a un usuario (membership). Reemplaza la asignación actual."""
    membership = session.query(WorkspaceMembership).filter_by(id=membership_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membresía no encontrada")
    _require_workspace_admin(session, user_id, membership.workspace_id)
    # Verificar que los roles pertenecen al mismo workspace
    for rid in request.operational_role_ids:
        r = session.query(OperationalRole).filter_by(id=rid, workspace_id=membership.workspace_id).first()
        if not r:
            raise HTTPException(status_code=400, detail=f"Rol operativo {rid} no existe o no pertenece al workspace")
    # Eliminar asignaciones actuales
    session.query(UserOperationalRole).filter_by(workspace_membership_id=membership_id).delete()
    # Asignar nuevos
    for rid in request.operational_role_ids:
        uor = UserOperationalRole(
            id=str(uuid.uuid4()),
            workspace_membership_id=membership_id,
            operational_role_id=rid,
            assigned_by=user_id,
        )
        session.add(uor)
    session.flush()
    return {"message": "Roles operativos asignados", "membership_id": membership_id}


@router.delete("/workspace-memberships/{membership_id}/operational-roles/{role_id}")
async def remove_operational_role_from_membership(
    membership_id: str,
    role_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """Quita un rol operativo de un usuario (membership)."""
    membership = session.query(WorkspaceMembership).filter_by(id=membership_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membresía no encontrada")
    _require_workspace_admin(session, user_id, membership.workspace_id)
    uor = (
        session.query(UserOperationalRole)
        .filter_by(workspace_membership_id=membership_id, operational_role_id=role_id)
        .first()
    )
    if not uor:
        raise HTTPException(status_code=404, detail="Asignación de rol no encontrada")
    session.delete(uor)
    return {"message": "Rol operativo quitado", "membership_id": membership_id, "role_id": role_id}
