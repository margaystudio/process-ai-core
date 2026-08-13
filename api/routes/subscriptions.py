"""
Endpoints para gestionar planes de suscripción y suscripciones de workspaces.

Endpoints:
- GET /api/v1/subscription-plans: Listar planes disponibles
- GET /api/v1/workspaces/{workspace_id}/subscription: Obtener suscripción actual
- POST /api/v1/workspaces/{workspace_id}/subscription: Crear/cambiar suscripción
- GET /api/v1/workspaces/{workspace_id}/limits: Obtener límites y uso actual
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..dependencies import get_db, get_current_user_id
from ..request_identity import capture_request_identity
from ..workspace_client import require_process_ai_access, sync_workspace_access
from process_ai_core.db.helpers import (
    list_subscription_plans,
    get_subscription_plan,
    get_active_subscription,
    get_subscription,
    check_workspace_limit,
)
from process_ai_core.db.models import Workspace, SubscriptionPlan
from process_ai_core.db.permissions import get_membership_base_access

router = APIRouter(
    prefix="/api/v1",
    tags=["subscriptions"],
    dependencies=[
        Depends(sync_workspace_access),
        Depends(capture_request_identity),
        Depends(require_process_ai_access),
    ],
)


def _require_workspace_member(session: Session, user_id: str, workspace_id: str) -> None:
    """Lanza 403 si el usuario no es miembro del workspace (mismo patrón que folders)."""
    if get_membership_base_access(session, user_id, workspace_id) is None:
        raise HTTPException(
            status_code=403,
            detail="No es miembro de este workspace",
        )


# ============================================================================
# Request/Response Models
# ============================================================================

class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    plan_type: str
    price_monthly: float
    price_yearly: float
    max_users: Optional[int]
    max_documents: Optional[int]
    max_documents_per_month: Optional[int]
    max_storage_gb: Optional[float]
    features_json: str
    is_active: bool
    sort_order: int

    class Config:
        from_attributes = True


class WorkspaceSubscriptionResponse(BaseModel):
    id: str
    workspace_id: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str
    current_users_count: int
    current_documents_count: int
    current_documents_this_month: int
    current_storage_gb: float
    plan: SubscriptionPlanResponse

    class Config:
        from_attributes = True


class WorkspaceLimitsResponse(BaseModel):
    workspace_id: str
    plan_name: str
    plan_display_name: str
    limits: dict
    current_usage: dict
    can_create_users: bool
    can_create_documents: bool
    can_create_documents_this_month: bool


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/subscription-plans", response_model=list[SubscriptionPlanResponse])
def list_plans(
    plan_type: Optional[str] = None,  # "b2b" | "b2c"
    session: Session = Depends(get_db),
):
    """
    Lista planes de suscripción disponibles.
    
    Args:
        plan_type: Filtrar por tipo de plan (b2b o b2c)
    """
    plans = list_subscription_plans(session, plan_type=plan_type, active_only=True)
    return [SubscriptionPlanResponse.model_validate(plan) for plan in plans]


@router.get(
    "/workspaces/{workspace_id}/subscription",
    response_model=WorkspaceSubscriptionResponse | None,
)
def get_workspace_subscription(
    workspace_id: str,
    session: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Obtiene la suscripción actual de un workspace.
    Devuelve null (200) si el workspace aún no tiene suscripción asignada.
    """
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    _require_workspace_member(session, user_id, workspace_id)

    subscription = get_subscription(session, workspace_id)
    if not subscription:
        return None

    return WorkspaceSubscriptionResponse(
        id=subscription.id,
        workspace_id=subscription.workspace_id,
        plan_id=subscription.plan_id,
        status=subscription.status,
        current_period_start=subscription.current_period_start.isoformat(),
        current_period_end=subscription.current_period_end.isoformat(),
        current_users_count=subscription.current_users_count,
        current_documents_count=subscription.current_documents_count,
        current_documents_this_month=subscription.current_documents_this_month,
        current_storage_gb=subscription.current_storage_gb,
        plan=SubscriptionPlanResponse.model_validate(subscription.plan),
    )


# NO existe `POST /workspaces/{id}/subscription`, a propósito.
#
# Dejaba que el admin del propio tenant se asignara `plan_id` y
# `status="active"` arbitrarios, sin ninguna verificación de pago: auto-upgrade
# al plan más caro y todos los límites de storage/documentos levantados gratis.
# Ninguna pantalla lo usaba.
#
# Asignar un plan es una decisión COMERCIAL, no una preferencia del workspace:
# vive en el control plane / billing, no en un endpoint que el propio
# beneficiario puede llamar. Los GET de plan y límites siguen acá porque leer
# el propio plan sí es del módulo.
@router.get("/workspaces/{workspace_id}/limits", response_model=WorkspaceLimitsResponse)
def get_workspace_limits(
    workspace_id: str,
    session: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Obtiene los límites y uso actual de un workspace.

    Para workspaces de tipo "system" (superadmins), devuelve límites ilimitados.
    """
    # Verificar si es un workspace de tipo "system"
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    _require_workspace_member(session, user_id, workspace_id)
    
    # Workspaces de tipo "system" no requieren suscripción y tienen límites ilimitados
    if workspace.workspace_type == "system":
        return WorkspaceLimitsResponse(
            workspace_id=workspace_id,
            plan_name="system",
            plan_display_name="Sistema (Ilimitado)",
            limits={
                "max_users": None,  # Ilimitado
                "max_documents": None,  # Ilimitado
                "max_documents_per_month": None,  # Ilimitado
                "max_storage_gb": None,  # Ilimitado
            },
            current_usage={
                "current_users_count": 0,
                "current_documents_count": 0,
                "current_documents_this_month": 0,
                "current_storage_gb": 0.0,
            },
            can_create_users=True,
            can_create_documents=True,
            can_create_documents_this_month=True,
        )
    
    # Para otros tipos de workspace, buscar suscripción
    from process_ai_core.db.helpers import get_subscription
    subscription = get_subscription(session, workspace_id)
    if not subscription or subscription.status not in ("active", "trial"):
        return WorkspaceLimitsResponse(
            workspace_id=workspace_id,
            plan_name="none",
            plan_display_name="Sin suscripción activa",
            limits={
                "max_users": None,
                "max_documents": None,
                "max_documents_per_month": None,
                "max_storage_gb": None,
            },
            current_usage={
                "current_users_count": 0,
                "current_documents_count": 0,
                "current_documents_this_month": 0,
                "current_storage_gb": 0.0,
            },
            can_create_users=True,
            can_create_documents=True,
            can_create_documents_this_month=True,
        )
    
    plan = subscription.plan
    
    # Verificar qué acciones están permitidas
    can_create_users, _ = check_workspace_limit(session, workspace_id, "users")
    can_create_documents, _ = check_workspace_limit(session, workspace_id, "documents")
    can_create_documents_this_month, _ = check_workspace_limit(session, workspace_id, "documents_per_month")
    
    return WorkspaceLimitsResponse(
        workspace_id=workspace_id,
        plan_name=plan.name,
        plan_display_name=plan.display_name,
        limits={
            "max_users": plan.max_users,
            "max_documents": plan.max_documents,
            "max_documents_per_month": plan.max_documents_per_month,
            "max_storage_gb": plan.max_storage_gb,
        },
        current_usage={
            "current_users_count": subscription.current_users_count,
            "current_documents_count": subscription.current_documents_count,
            "current_documents_this_month": subscription.current_documents_this_month,
            "current_storage_gb": subscription.current_storage_gb,
        },
        can_create_users=can_create_users,
        can_create_documents=can_create_documents,
        can_create_documents_this_month=can_create_documents_this_month,
    )


