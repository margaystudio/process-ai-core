"""
Endpoints para gestión de validaciones de documentos.

Este módulo maneja:
- POST /api/v1/documents/{document_id}/validate - Crear validación
- POST /api/v1/validations/{validation_id}/approve - Aprobar validación
- POST /api/v1/validations/{validation_id}/reject - Rechazar validación con observaciones
- GET /api/v1/documents/{document_id}/validations - Listar validaciones de un documento
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Optional
from pydantic import BaseModel

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Validation, Run
from process_ai_core.db.helpers import (
    create_validation,
    approve_validation,
    reject_validation,
    create_document_version,
)

router = APIRouter(prefix="/api/v1", tags=["validations"])


# ============================================================
# Request/Response Models
# ============================================================

class ValidationCreateRequest(BaseModel):
    run_id: Optional[str] = None
    observations: str = ""
    checklist_json: str = "{}"


class ValidationRejectRequest(BaseModel):
    observations: str


class ValidationResponse(BaseModel):
    id: str
    document_id: str
    run_id: Optional[str] = None
    validator_user_id: Optional[str] = None
    status: str
    observations: str
    checklist_json: str
    created_at: str
    completed_at: Optional[str] = None


# ============================================================
# Endpoints
# ============================================================

@router.post("/documents/{document_id}/approve")
async def approve_document_direct(
    document_id: str,
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Aprueba un documento directamente (sin crear validación explícita).
    
    Solo usuarios con rol "owner", "admin" o "approver" pueden aprobar.
    
    Args:
        document_id: ID del documento
        user_id: ID del usuario que aprueba
        workspace_id: ID del workspace
    
    Returns:
        Mensaje de confirmación y versión creada
    """
    with get_db_session() as session:
        # Verificar permisos usando el sistema de permisos
        from process_ai_core.db.permissions import has_permission
        from process_ai_core.db.models import Document, Run
        
        if not has_permission(session, user_id, workspace_id, "documents.approve"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para aprobar documentos"
            )
        
        # Obtener documento
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        if doc.workspace_id != workspace_id:
            raise HTTPException(
                status_code=403,
                detail="Documento no pertenece a este workspace"
            )
        
        # Obtener último run del documento
        last_run = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).first()
        if not last_run:
            raise HTTPException(
                status_code=400,
                detail="No hay runs asociados al documento para aprobar"
            )
        
        # Aprobar usando la función existente
        from process_ai_core.db.helpers import approve_validation, create_validation
        
        # Crear validación automática y aprobarla
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=last_run.id,
            validator_user_id=user_id,
        )
        session.flush()
        
        # Aprobar la validación
        approved_validation = approve_validation(
            session=session,
            validation_id=validation.id,
            user_id=user_id,
        )
        
        return {
            "message": "Documento aprobado exitosamente",
            "validation_id": approved_validation.id,
            "version_id": doc.approved_version_id,
        }


@router.post("/documents/{document_id}/reject")
async def reject_document_direct(
    document_id: str,
    observations: str = Body(..., embed=True),
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Rechaza un documento directamente con observaciones (sin crear validación explícita).
    
    Solo usuarios con rol "owner", "admin" o "approver" pueden rechazar.
    
    Args:
        document_id: ID del documento
        observations: Observaciones del rechazo
        user_id: ID del usuario que rechaza
        workspace_id: ID del workspace
    
    Returns:
        Mensaje de confirmación
    """
    with get_db_session() as session:
        # Verificar permisos usando el sistema de permisos
        from process_ai_core.db.permissions import has_permission
        from process_ai_core.db.models import Document, Run
        
        if not has_permission(session, user_id, workspace_id, "documents.reject"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para rechazar documentos"
            )
        
        # Obtener documento
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        if doc.workspace_id != workspace_id:
            raise HTTPException(
                status_code=403,
                detail="Documento no pertenece a este workspace"
            )
        
        # Obtener último run del documento
        last_run = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).first()
        if not last_run:
            raise HTTPException(
                status_code=400,
                detail="No hay runs asociados al documento para rechazar"
            )
        
        # Crear validación y rechazarla
        from process_ai_core.db.helpers import create_validation, reject_validation
        
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=last_run.id,
            validator_user_id=user_id,
            observations=observations,
        )
        session.flush()
        
        # Rechazar la validación
        rejected_validation = reject_validation(
            session=session,
            validation_id=validation.id,
            observations=observations,
            user_id=user_id,
        )
        
        return {
            "message": "Documento rechazado con observaciones",
            "validation_id": rejected_validation.id,
        }


@router.post("/documents/{document_id}/validate", response_model=ValidationResponse)
async def create_document_validation(
    document_id: str,
    request: ValidationCreateRequest = Body(...),
):
    """
    Crea una nueva validación para un documento.
    
    Args:
        document_id: ID del documento
        request: Datos de la validación (run_id opcional, observations, checklist_json)
    
    Returns:
        ValidationResponse con la validación creada
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        # Validar run_id si se proporciona
        if request.run_id:
            run = session.query(Run).filter_by(id=request.run_id, document_id=document_id).first()
            if not run:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run {request.run_id} no encontrado para el documento {document_id}"
                )
        
        # Crear validación
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=request.run_id,
            observations=request.observations,
            checklist_json=request.checklist_json,
        )
        
        # Actualizar estado del documento a pending_validation si no lo está
        if doc.status != "pending_validation":
            doc.status = "pending_validation"
        
        session.commit()
        
        return ValidationResponse(
            id=validation.id,
            document_id=validation.document_id,
            run_id=validation.run_id,
            validator_user_id=validation.validator_user_id,
            status=validation.status,
            observations=validation.observations,
            checklist_json=validation.checklist_json,
            created_at=validation.created_at.isoformat(),
            completed_at=validation.completed_at.isoformat() if validation.completed_at else None,
        )


@router.post("/validations/{validation_id}/approve", response_model=ValidationResponse)
async def approve_document_validation(
    validation_id: str,
):
    """
    Aprueba una validación.
    
    Cuando se aprueba:
    - El estado del documento pasa a "approved"
    - Si hay un run asociado, se marca como aprobado
    - Se crea un DocumentVersion con is_current=True
    
    Args:
        validation_id: ID de la validación
    
    Returns:
        ValidationResponse con la validación aprobada
    """
    with get_db_session() as session:
        validation = session.query(Validation).filter_by(id=validation_id).first()
        if not validation:
            raise HTTPException(
                status_code=404,
                detail=f"Validación {validation_id} no encontrada"
            )
        
        if validation.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"La validación ya está {validation.status}, no se puede aprobar"
            )
        
        # Aprobar validación
        validation = approve_validation(
            session=session,
            validation_id=validation_id,
        )
        
        # Si hay un run asociado, crear DocumentVersion desde el run
        if validation.run_id:
            run = session.query(Run).filter_by(id=validation.run_id).first()
            if run:
                # Leer el JSON y Markdown del run
                from process_ai_core.config import get_settings
                import json
                from pathlib import Path
                
                settings = get_settings()
                run_dir = Path(settings.output_dir) / run.id
                json_path = run_dir / "process.json"
                md_path = run_dir / "process.md"
                
                if json_path.exists() and md_path.exists():
                    content_json = json_path.read_text(encoding="utf-8")
                    content_markdown = md_path.read_text(encoding="utf-8")
                    
                    # Crear versión aprobada
                    create_document_version(
                        session=session,
                        document_id=validation.document_id,
                        run_id=validation.run_id,
                        content_type="generated",
                        content_json=content_json,
                        content_markdown=content_markdown,
                        validation_id=validation_id,
                    )
        
        session.commit()
        
        return ValidationResponse(
            id=validation.id,
            document_id=validation.document_id,
            run_id=validation.run_id,
            validator_user_id=validation.validator_user_id,
            status=validation.status,
            observations=validation.observations,
            checklist_json=validation.checklist_json,
            created_at=validation.created_at.isoformat(),
            completed_at=validation.completed_at.isoformat() if validation.completed_at else None,
        )


@router.post("/validations/{validation_id}/reject", response_model=ValidationResponse)
async def reject_document_validation(
    validation_id: str,
    request: ValidationRejectRequest = Body(...),
):
    """
    Rechaza una validación con observaciones.
    
    Cuando se rechaza:
    - El estado del documento pasa a "rejected"
    - Las observaciones se guardan para corrección posterior
    
    Args:
        validation_id: ID de la validación
        request: Observaciones del rechazo
    
    Returns:
        ValidationResponse con la validación rechazada
    """
    with get_db_session() as session:
        validation = session.query(Validation).filter_by(id=validation_id).first()
        if not validation:
            raise HTTPException(
                status_code=404,
                detail=f"Validación {validation_id} no encontrada"
            )
        
        if validation.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"La validación ya está {validation.status}, no se puede rechazar"
            )
        
        # Rechazar validación
        validation = reject_validation(
            session=session,
            validation_id=validation_id,
            observations=request.observations,
        )
        
        session.commit()
        
        return ValidationResponse(
            id=validation.id,
            document_id=validation.document_id,
            run_id=validation.run_id,
            validator_user_id=validation.validator_user_id,
            status=validation.status,
            observations=validation.observations,
            checklist_json=validation.checklist_json,
            created_at=validation.created_at.isoformat(),
            completed_at=validation.completed_at.isoformat() if validation.completed_at else None,
        )


@router.get("/documents/{document_id}/validations", response_model=list[ValidationResponse])
async def get_document_validations(document_id: str):
    """
    Obtiene todas las validaciones de un documento.
    
    Args:
        document_id: ID del documento
    
    Returns:
        Lista de ValidationResponse ordenadas por fecha de creación (más recientes primero)
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        validations = (
            session.query(Validation)
            .filter_by(document_id=document_id)
            .order_by(Validation.created_at.desc())
            .all()
        )
        
        return [
            ValidationResponse(
                id=v.id,
                document_id=v.document_id,
                run_id=v.run_id,
                validator_user_id=v.validator_user_id,
                status=v.status,
                observations=v.observations,
                checklist_json=v.checklist_json,
                created_at=v.created_at.isoformat(),
                completed_at=v.completed_at.isoformat() if v.completed_at else None,
            )
            for v in validations
        ]

