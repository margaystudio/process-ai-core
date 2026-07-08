"""
Endpoints de la capa semántica (relaciones y knowledge objects).

Contratos (brief "Capa de relaciones y conocimiento" §5):
- GET   /api/v1/documents/{id}/relations           → relaciones agrupadas por tipo
- POST  /api/v1/documents/{id}/relations/suggest   → dispara extracción + candidatas
- POST  /api/v1/relations/{id}/confirm             → candidate → confirmed
- POST  /api/v1/relations/{id}/reject              → candidate → rejected
- PATCH /api/v1/relations/{id}                     → editar una relación incorrecta
- POST  /api/v1/knowledge-objects                  → crear entidad nueva
- GET   /api/v1/knowledge-objects?type=&q=         → búsqueda / autocompletar
- POST  /api/v1/knowledge-objects/{id}/merge       → unir duplicados
- GET   /api/v1/documents/{id}/impact              → impacto si cambia el documento

Gobernanza (ADR-006): confirmar/rechazar exige permiso documents.approve y
segregación de funciones (el creador de la versión fuente no valida sus
propias relaciones). La IA solo propone; nada es oficial sin humano.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from process_ai_core.db.models import Document, DocumentVersion
from process_ai_core.db.models_semantic import (
    DocumentRelation,
    KnowledgeObject,
    KNOWLEDGE_OBJECT_TYPES,
)
from process_ai_core.db.permissions import has_permission
from process_ai_core.semantic import RelationService, normalize_name
from process_ai_core.semantic.pipeline import run_semantic_pipeline

from ..dependencies import get_db, get_current_user_id
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["semantic"],
    dependencies=[Depends(sync_workspace_access)],
)


# ============================================================
# Request/Response models
# ============================================================

class RelationTargetResponse(BaseModel):
    id: str
    type: str
    name: str


class RelationItemResponse(BaseModel):
    id: str
    target: RelationTargetResponse
    confidence: Optional[float] = None
    status: str
    evidence_text: Optional[str] = None
    created_by_ai: bool
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    possible_duplicate_of: Optional[RelationTargetResponse] = None


class RelationGroupResponse(BaseModel):
    relation_type: str
    items: list[RelationItemResponse]


class DocumentRelationsResponse(BaseModel):
    document_id: str
    groups: list[RelationGroupResponse]


class SuggestResponse(BaseModel):
    document_id: str
    version_id: str
    candidates_created: int
    chunks_indexed: int


class RelationDecisionRequest(BaseModel):
    # El backend usa SIEMPRE el usuario del JWT; el campo existe por contrato.
    confirmed_by: Optional[str] = None


class RelationPatchRequest(BaseModel):
    relation_type: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None


class KnowledgeObjectCreateRequest(BaseModel):
    type: str
    canonical_name: str
    description: Optional[str] = None


class KnowledgeObjectResponse(BaseModel):
    id: str
    type: str
    canonical_name: str
    normalized_name: str
    description: Optional[str] = None
    aliases: list[str] = []


class MergeRequest(BaseModel):
    into_id: str


# ============================================================
# Helpers
# ============================================================

def _get_document_or_404(session: Session, document_id: str, workspace_id: str) -> Document:
    doc = session.query(Document).filter_by(id=document_id).first()
    if not doc or doc.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado")
    return doc


def _get_relation_or_404(session: Session, relation_id: str, workspace_id: str) -> DocumentRelation:
    relation = session.query(DocumentRelation).filter_by(id=relation_id).first()
    if not relation or relation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail=f"Relación {relation_id} no encontrada")
    return relation


def _get_knowledge_object_or_404(session: Session, ko_id: str, workspace_id: str) -> KnowledgeObject:
    ko = session.query(KnowledgeObject).filter_by(id=ko_id).first()
    if not ko or ko.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail=f"Knowledge object {ko_id} no encontrado")
    return ko


def _target_response(session: Session, relation: DocumentRelation) -> RelationTargetResponse:
    if relation.target_type == "document":
        doc = session.query(Document).filter_by(id=relation.target_id).first()
        name = doc.name if doc else "(documento eliminado)"
        return RelationTargetResponse(id=relation.target_id, type="documento", name=name)
    ko = session.query(KnowledgeObject).filter_by(id=relation.target_id).first()
    name = ko.canonical_name if ko else "(entidad eliminada)"
    return RelationTargetResponse(id=relation.target_id, type=relation.target_type, name=name)


def _ko_response(ko: KnowledgeObject) -> KnowledgeObjectResponse:
    try:
        aliases = json.loads(ko.metadata_json or "{}").get("aliases", [])
    except (json.JSONDecodeError, TypeError):
        aliases = []
    return KnowledgeObjectResponse(
        id=ko.id,
        type=ko.type,
        canonical_name=ko.canonical_name,
        normalized_name=ko.normalized_name,
        description=ko.description,
        aliases=aliases,
    )


# ============================================================
# Relaciones
# ============================================================

@router.get("/documents/{document_id}/relations", response_model=DocumentRelationsResponse)
async def get_document_relations(
    document_id: str,
    include_all: bool = False,
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Relaciones del documento agrupadas por relation_type.

    Por defecto devuelve candidate + confirmed (lo que la UI de confirmación
    necesita); con include_all=true incluye también rejected y obsolete.
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    doc = _get_document_or_404(session, document_id, workspace_id)

    query = session.query(DocumentRelation).filter_by(document_id=doc.id)
    if not include_all:
        query = query.filter(DocumentRelation.status.in_(["candidate", "confirmed"]))
    relations = query.order_by(DocumentRelation.created_at).all()

    service = RelationService()
    groups: dict[str, list[RelationItemResponse]] = {}
    for rel in relations:
        possible_duplicate = None
        if rel.status == "candidate" and rel.target_type != "document":
            ko = session.query(KnowledgeObject).filter_by(id=rel.target_id).first()
            if ko is not None:
                dup = service.find_possible_duplicate(session, ko)
                if dup is not None:
                    possible_duplicate = RelationTargetResponse(
                        id=dup.id, type=dup.type, name=dup.canonical_name
                    )
        groups.setdefault(rel.relation_type, []).append(
            RelationItemResponse(
                id=rel.id,
                target=_target_response(session, rel),
                confidence=rel.confidence,
                status=rel.status,
                evidence_text=rel.evidence_text,
                created_by_ai=rel.created_by_ai,
                confirmed_by=rel.confirmed_by,
                confirmed_at=rel.confirmed_at.isoformat() if rel.confirmed_at else None,
                possible_duplicate_of=possible_duplicate,
            )
        )

    return DocumentRelationsResponse(
        document_id=doc.id,
        groups=[
            RelationGroupResponse(relation_type=rt, items=items)
            for rt, items in sorted(groups.items())
        ],
    )


@router.post("/documents/{document_id}/relations/suggest", response_model=SuggestResponse)
async def suggest_document_relations(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Dispara extracción + propuesta de relaciones (filas status=candidate).

    Corre sobre la versión APPROVED vigente del documento (ADR-002: la fuente
    del pipeline es siempre contenido aprobado).
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    doc = _get_document_or_404(session, document_id, workspace_id)

    if not has_permission(session, user_id, workspace_id, "documents.create"):
        raise HTTPException(status_code=403, detail="No tiene permisos para generar sugerencias")

    version = (
        session.query(DocumentVersion)
        .filter_by(document_id=doc.id, version_status="APPROVED", is_current=True)
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=400,
            detail="El documento no tiene una versión aprobada vigente; el pipeline semántico solo corre sobre contenido aprobado.",
        )

    try:
        summary = run_semantic_pipeline(session, document=doc, version=version)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Fallo el pipeline semántico para %s", document_id)
        raise HTTPException(status_code=502, detail=f"El pipeline semántico falló: {type(exc).__name__}")

    return SuggestResponse(
        document_id=doc.id,
        version_id=version.id,
        candidates_created=summary["candidates_created"],
        chunks_indexed=summary["chunks_indexed"],
    )


@router.post("/relations/{relation_id}/confirm", response_model=RelationItemResponse)
async def confirm_relation(
    relation_id: str,
    request: RelationDecisionRequest = Body(default=RelationDecisionRequest()),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """candidate → confirmed (la relación pasa a formar la red oficial)."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    relation = _get_relation_or_404(session, relation_id, workspace_id)

    if not has_permission(session, user_id, workspace_id, "documents.approve"):
        raise HTTPException(status_code=403, detail="No tiene permisos para confirmar relaciones")

    try:
        RelationService().confirm(session, relation, user_id)
        session.commit()
    except PermissionError as exc:
        session.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return RelationItemResponse(
        id=relation.id,
        target=_target_response(session, relation),
        confidence=relation.confidence,
        status=relation.status,
        evidence_text=relation.evidence_text,
        created_by_ai=relation.created_by_ai,
        confirmed_by=relation.confirmed_by,
        confirmed_at=relation.confirmed_at.isoformat() if relation.confirmed_at else None,
    )


@router.post("/relations/{relation_id}/reject", response_model=RelationItemResponse)
async def reject_relation(
    relation_id: str,
    request: RelationDecisionRequest = Body(default=RelationDecisionRequest()),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """candidate → rejected (se conserva para no re-proponerla)."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    relation = _get_relation_or_404(session, relation_id, workspace_id)

    if not has_permission(session, user_id, workspace_id, "documents.approve"):
        raise HTTPException(status_code=403, detail="No tiene permisos para rechazar relaciones")

    try:
        RelationService().reject(session, relation, user_id)
        session.commit()
    except PermissionError as exc:
        session.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return RelationItemResponse(
        id=relation.id,
        target=_target_response(session, relation),
        confidence=relation.confidence,
        status=relation.status,
        evidence_text=relation.evidence_text,
        created_by_ai=relation.created_by_ai,
        confirmed_by=relation.confirmed_by,
        confirmed_at=relation.confirmed_at.isoformat() if relation.confirmed_at else None,
    )


@router.patch("/relations/{relation_id}", response_model=RelationItemResponse)
async def edit_relation(
    relation_id: str,
    request: RelationPatchRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Edita una relación incorrecta (ADR-003: metadatos derivados, editables)."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    relation = _get_relation_or_404(session, relation_id, workspace_id)

    if not has_permission(session, user_id, workspace_id, "documents.create"):
        raise HTTPException(status_code=403, detail="No tiene permisos para editar relaciones")

    try:
        RelationService().edit(
            session,
            relation,
            relation_type=request.relation_type,
            target_type=request.target_type,
            target_id=request.target_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return RelationItemResponse(
        id=relation.id,
        target=_target_response(session, relation),
        confidence=relation.confidence,
        status=relation.status,
        evidence_text=relation.evidence_text,
        created_by_ai=relation.created_by_ai,
        confirmed_by=relation.confirmed_by,
        confirmed_at=relation.confirmed_at.isoformat() if relation.confirmed_at else None,
    )


# ============================================================
# Knowledge objects
# ============================================================

@router.post("/knowledge-objects", response_model=KnowledgeObjectResponse)
async def create_knowledge_object(
    request: KnowledgeObjectCreateRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Crea una entidad semántica manualmente (acción "crear entidad" de la UX)."""
    workspace_id = resolve_tenant_workspace_id(ctx)

    if not has_permission(session, user_id, workspace_id, "documents.create"):
        raise HTTPException(status_code=403, detail="No tiene permisos para crear entidades")

    ko_type = request.type.strip().lower()
    if ko_type not in KNOWLEDGE_OBJECT_TYPES or ko_type == "documento":
        raise HTTPException(status_code=400, detail=f"Tipo de entidad inválido: {request.type}")

    canonical = request.canonical_name.strip()
    if not canonical or len(canonical) > 300:
        raise HTTPException(status_code=400, detail="canonical_name es obligatorio (máx. 300 caracteres)")

    normalized = normalize_name(canonical)
    existing = (
        session.query(KnowledgeObject)
        .filter_by(workspace_id=workspace_id, type=ko_type, normalized_name=normalized)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una entidad {ko_type} con ese nombre: {existing.canonical_name}",
        )

    ko = KnowledgeObject(
        workspace_id=workspace_id,
        type=ko_type,
        canonical_name=canonical,
        normalized_name=normalized,
        description=(request.description or "").strip() or None,
        metadata_json=json.dumps({"created_by_ai": False}),
    )
    session.add(ko)
    session.commit()
    return _ko_response(ko)


@router.get("/knowledge-objects", response_model=list[KnowledgeObjectResponse])
async def search_knowledge_objects(
    type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 20,
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Búsqueda para autocompletar / detectar duplicados."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    results = RelationService().search_knowledge_objects(
        session, workspace_id, type=type, q=q, limit=min(max(limit, 1), 100)
    )
    return [_ko_response(ko) for ko in results]


@router.post("/knowledge-objects/{ko_id}/merge", response_model=KnowledgeObjectResponse)
async def merge_knowledge_object(
    ko_id: str,
    request: MergeRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Une {ko_id} dentro de {into_id}: reapunta document_relations y elimina el duplicado."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    source = _get_knowledge_object_or_404(session, ko_id, workspace_id)
    into = _get_knowledge_object_or_404(session, request.into_id, workspace_id)

    if not has_permission(session, user_id, workspace_id, "documents.approve"):
        raise HTTPException(status_code=403, detail="No tiene permisos para unir entidades")

    try:
        RelationService().merge_knowledge_objects(session, source=source, into=into)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return _ko_response(into)


# ============================================================
# Impacto
# ============================================================

@router.get("/documents/{document_id}/impact")
async def get_document_impact(
    document_id: str,
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """Documentos y entidades afectadas si cambia este documento (red confirmada)."""
    workspace_id = resolve_tenant_workspace_id(ctx)
    doc = _get_document_or_404(session, document_id, workspace_id)
    return RelationService().impact(session, doc)
