"""
Endpoints para gestionar planes de suscripción y suscripciones de workspaces.

Endpoints:
- GET /api/v1/subscription-plans: Listar planes disponibles
- GET /api/v1/workspaces/{workspace_id}/subscription: Obtener suscripción actual
- POST /api/v1/workspaces/{workspace_id}/subscription: Crear/cambiar suscripción
- GET /api/v1/workspaces/{workspace_id}/limits: Obtener límites y uso actual
"""

from datetime import datetime, timedelta, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import (
    list_subscription_plans,
    get_subscription_plan,
    get_active_subscription,
    get_subscription,
    create_workspace_subscription,
    check_workspace_limit,
)
from process_ai_core.db.models import Workspace, SubscriptionPlan

router = APIRouter(prefix="/api/v1", tags=["subscriptions"])


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


class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    status: str = "active"  # "active" | "trial"
    period_days: int = 30


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/subscription-plans", response_model=list[SubscriptionPlanResponse])
async def list_plans(
    plan_type: Optional[str] = None,  # "b2b" | "b2c"
    session: Session = Depends(get_db_session),
):
    """
    Lista planes de suscripción disponibles.
    
    Args:
        plan_type: Filtrar por tipo de plan (b2b o b2c)
    """
    plans = list_subscription_plans(session, plan_type=plan_type, active_only=True)
    return [SubscriptionPlanResponse.model_validate(plan) for plan in plans]


@router.get("/workspaces/{workspace_id}/subscription", response_model=WorkspaceSubscriptionResponse)
async def get_workspace_subscription(
    workspace_id: str,
    session: Session = Depends(get_db_session),
):
    """
    Obtiene la suscripción actual de un workspace.
    """
    subscription = get_subscription(session, workspace_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Workspace sin suscripción")
    
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


@router.post("/workspaces/{workspace_id}/subscription", response_model=WorkspaceSubscriptionResponse)
async def create_or_update_subscription(
    workspace_id: str,
    request: CreateSubscriptionRequest,
    session: Session = Depends(get_db_session),
):
    """
    Crea o actualiza la suscripción de un workspace.
    """
    # Verificar que el workspace existe
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
    
    # Verificar que el plan existe
    plan = get_subscription_plan(session, request.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan de suscripción no encontrado")
    
    # Verificar si ya existe una suscripción
    existing = get_subscription(session, workspace_id)
    if existing:
        # Actualizar suscripción existente
        existing.plan_id = request.plan_id
        existing.status = request.status
        existing.current_period_start = datetime.now(UTC)
        existing.current_period_end = datetime.now(UTC) + timedelta(days=request.period_days)
        existing.updated_at = datetime.now(UTC)
        subscription = existing
    else:
        # Crear nueva suscripción
        subscription = create_workspace_subscription(
            session=session,
            workspace_id=workspace_id,
            plan_id=request.plan_id,
            status=request.status,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=request.period_days),
        )
    
    session.commit()
    
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


@router.get("/workspaces/{workspace_id}/limits", response_model=WorkspaceLimitsResponse)
async def get_workspace_limits(
    workspace_id: str,
    session: Session = Depends(get_db_session),
):
    """
    Obtiene los límites y uso actual de un workspace.
    """
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Workspace sin suscripción activa")
    
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


