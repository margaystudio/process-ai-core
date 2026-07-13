"""Endpoints de tipos documentales (entidad por-tenant).

Ver docs/PLAN_DOCUMENT_TYPES.md. Cada workspace es dueño de su set de tipos; solo
owner/admin del propio workspace (o superadmin) los edita. Aislamiento estricto:
un tipo de otro workspace responde 404.

Contratos:
- GET   /api/v1/document-types            → tipos del workspace activo
- POST  /api/v1/document-types            → crear tipo propio (origin="custom")
- PATCH /api/v1/document-types/{id}       → editar label/prompt/behaviors/is_active/icon/color
"""

from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from process_ai_core.db.models import DocumentType
from process_ai_core.db.permissions import get_user_role
from process_ai_core.domains.document_types import normalize_behaviors

from ..dependencies import get_current_user_id, get_db
from ..workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)

router = APIRouter(
    prefix="/api/v1/document-types",
    tags=["document-types"],
    dependencies=[Depends(sync_workspace_access)],
)


def _require_ws_admin(
    session: Session, user_id: str, workspace_id: str, ctx: WorkspaceSessionContext
) -> None:
    """Solo superadmin o owner/admin del propio workspace pueden editar los tipos."""
    if "superadmin" in (ctx.platform_roles or []):
        return
    role = get_user_role(session, user_id, workspace_id)
    if not role or role.name not in ("owner", "admin"):
        raise HTTPException(
            status_code=403, detail="Se requiere rol owner o admin del workspace"
        )


def _to_response(dt: DocumentType) -> dict:
    return {
        "id": dt.id,
        "key": dt.key,
        "label": dt.label,
        "prompt_text": dt.prompt_text,
        "behaviors": normalize_behaviors(json.loads(dt.behaviors_json or "{}")),
        "is_active": dt.is_active,
        "sort_order": dt.sort_order,
        "origin": dt.origin,
        "icon": dt.icon,
        "color": dt.color,
    }


class DocumentTypeUpdate(BaseModel):
    label: Optional[str] = None
    prompt_text: Optional[str] = None
    behaviors: Optional[dict] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class DocumentTypeCreate(BaseModel):
    key: Optional[str] = None  # si no viene, se deriva del label
    label: str
    prompt_text: str = ""
    behaviors: Optional[dict] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0


def _slugify(text: str) -> str:
    import unicodedata

    value = unicodedata.normalize("NFD", text)
    value = re.sub(r"[̀-ͯ]", "", value).lower().strip()
    value = re.sub(r"[^a-z0-9\s_-]", "", value)
    value = re.sub(r"\s+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


@router.get("")
async def list_document_types(
    include_inactive: bool = False,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Tipos documentales del workspace activo (ordenados)."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    query = session.query(DocumentType).filter_by(workspace_id=workspace_id)
    if not include_inactive:
        query = query.filter(DocumentType.is_active.is_(True))
    rows = query.order_by(DocumentType.sort_order, DocumentType.label).all()
    return [_to_response(dt) for dt in rows]


@router.patch("/{type_id}")
async def update_document_type(
    type_id: str,
    request: DocumentTypeUpdate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Edita un tipo del propio workspace. behaviors se valida contra la allowlist."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    _require_ws_admin(session, user_id, workspace_id, ctx)

    dt = session.query(DocumentType).filter_by(id=type_id).first()
    # Aislamiento: inexistente o de otro workspace → 404 (no filtra existencia).
    if not dt or dt.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Tipo documental no encontrado")

    if request.label is not None:
        dt.label = request.label
    if request.prompt_text is not None:
        dt.prompt_text = request.prompt_text
    if request.behaviors is not None:
        dt.behaviors_json = json.dumps(normalize_behaviors(request.behaviors))
    if request.is_active is not None:
        dt.is_active = request.is_active
    if request.sort_order is not None:
        dt.sort_order = request.sort_order
    if request.icon is not None:
        dt.icon = request.icon
    if request.color is not None:
        dt.color = request.color

    session.commit()
    session.refresh(dt)
    return _to_response(dt)


@router.post("")
async def create_document_type(
    request: DocumentTypeCreate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Crea un tipo propio del tenant (origin="custom")."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    _require_ws_admin(session, user_id, workspace_id, ctx)

    key = _slugify(request.key or request.label)
    if not key:
        raise HTTPException(status_code=400, detail="key/label inválido")

    existing = (
        session.query(DocumentType)
        .filter_by(workspace_id=workspace_id, key=key)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya existe un tipo con key '{key}'")

    dt = DocumentType(
        workspace_id=workspace_id,
        key=key,
        label=request.label.strip(),
        prompt_text=request.prompt_text or "",
        behaviors_json=json.dumps(normalize_behaviors(request.behaviors or {})),
        is_active=True,
        sort_order=request.sort_order,
        origin="custom",
        icon=request.icon,
        color=request.color,
    )
    session.add(dt)
    session.commit()
    session.refresh(dt)
    return _to_response(dt)
