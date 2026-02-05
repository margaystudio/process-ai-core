"""
Endpoints para gestión de validaciones de documentos.

Este módulo maneja:
- POST /api/v1/documents/{document_id}/validate - Crear validación
- POST /api/v1/validations/{validation_id}/approve - Aprobar validación (y versión asociada)
- POST /api/v1/validations/{validation_id}/reject - Rechazar validación con observaciones (texto libre y/o estructuradas)
- GET /api/v1/documents/{document_id}/validations - Listar validaciones de un documento

Nota: Los endpoints de versiones (submit, clone) están en api/routes/documents.py
"""

from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Validation, Run
from ..dependencies import get_db, get_current_user_id
from process_ai_core.db.helpers import (
    create_validation,
    approve_validation,
    reject_validation,
    create_document_version,
    approve_version,
    reject_version,
)
import logging
import json
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["validations"])


# ============================================================
# Request/Response Models
# ============================================================

class ValidationCreateRequest(BaseModel):
    run_id: Optional[str] = None
    observations: str = ""
    checklist_json: str = "{}"


class ValidationRejectRequest(BaseModel):
    observations: str = ""  # Texto libre para compatibilidad
    structured_observations: Optional[List[dict]] = None  # Lista de observaciones estructuradas


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
        
        # Buscar versión IN_REVIEW existente para asociar la validación
        from process_ai_core.db.models import DocumentVersion
        version_in_review = session.query(DocumentVersion).filter_by(
            document_id=document_id,
            version_status="IN_REVIEW"
        ).first()
        
        # Crear validación
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=request.run_id,
            observations=request.observations,
            checklist_json=request.checklist_json,
        )
        session.flush()  # Flush para obtener el ID de la validación
        
        # Si hay una versión IN_REVIEW, asociarla a la validación
        if version_in_review:
            version_in_review.validation_id = validation.id
            logger.info(f"Validación {validation.id} asociada a versión IN_REVIEW {version_in_review.id}")
        else:
            logger.warning(f"No hay versión IN_REVIEW para el documento {document_id}. La validación {validation.id} no está asociada a ninguna versión.")
        
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
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Aprueba una validación (y su versión asociada).
    
    Cuando se aprueba:
    - La versión IN_REVIEW cambia a APPROVED
    - Se marca como versión actual (is_current=True)
    - La versión anterior APPROVED se marca como OBSOLETE
    - El estado del documento pasa a "approved"
    
    Solo usuarios con permisos para aprobar documentos pueden usar este endpoint.
    
    Args:
        validation_id: ID de la validación
        user_id: ID del usuario que aprueba
        workspace_id: ID del workspace
    
    Returns:
        ValidationResponse con la validación aprobada
    """
    with get_db_session() as session:
        # Verificar permisos
        from process_ai_core.db.permissions import has_permission
        
        if not has_permission(session, user_id, workspace_id, "documents.approve"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para aprobar documentos"
            )
        
        validation = session.query(Validation).filter_by(id=validation_id).first()
        if not validation:
            raise HTTPException(
                status_code=404,
                detail=f"Validación {validation_id} no encontrada"
            )
        
        # Verificar que el documento pertenece al workspace
        doc = session.query(Document).filter_by(id=validation.document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {validation.document_id} no encontrado"
            )
        
        if doc.workspace_id != workspace_id:
            raise HTTPException(
                status_code=403,
                detail="Documento no pertenece a este workspace"
            )
        
        if validation.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"La validación ya está {validation.status}, no se puede aprobar"
            )
        
        # Aprobar versión usando el nuevo helper
        try:
            approved_version = approve_version(
                session=session,
                validation_id=validation_id,
                approver_id=user_id,
            )
            session.commit()
            session.refresh(validation)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
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
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Rechaza una validación (y su versión asociada) con observaciones.
    
    Cuando se rechaza:
    - La versión IN_REVIEW cambia a REJECTED
    - El estado del documento pasa a "rejected"
    - Las observaciones (texto libre y/o estructuradas) se guardan para corrección posterior
    
    Solo usuarios con permisos para rechazar documentos pueden usar este endpoint.
    
    Args:
        validation_id: ID de la validación
        request: Observaciones del rechazo (texto libre y/o estructuradas)
        user_id: ID del usuario que rechaza
        workspace_id: ID del workspace
    
    Returns:
        ValidationResponse con la validación rechazada
    """
    # Verificar permisos
    from process_ai_core.db.permissions import has_permission
    
    # Obtener la validación para encontrar el documento y workspace
    validation = session.query(Validation).filter_by(id=validation_id).first()
    if not validation:
        raise HTTPException(
            status_code=404,
            detail=f"Validación {validation_id} no encontrada"
        )
    
    # Obtener el documento para verificar workspace
    doc = session.query(Document).filter_by(id=validation.document_id).first()
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Documento {validation.document_id} no encontrado"
        )
    
    workspace_id = doc.workspace_id
    
    # Verificar permisos
    if not has_permission(session, user_id, workspace_id, "documents.reject"):
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para rechazar documentos"
        )
    
    if validation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"La validación ya está {validation.status}, no se puede rechazar"
        )
    
    # Intentar encontrar o asociar una versión IN_REVIEW
    from process_ai_core.db.models import DocumentVersion
    version = session.query(DocumentVersion).filter_by(validation_id=validation_id).first()
    
    if not version:
        # Buscar versión IN_REVIEW para este documento
        version_in_review = session.query(DocumentVersion).filter_by(
            document_id=validation.document_id,
            version_status="IN_REVIEW"
        ).first()
        if version_in_review:
            # Asociar la versión a la validación
            version_in_review.validation_id = validation_id
            session.flush()
            version = version_in_review
            logger.info(f"Validación {validation_id} asociada a versión IN_REVIEW {version.id} durante el rechazo")
    
    # Validar formato de observaciones estructuradas si se proporcionan
    structured_obs = None
    if request.structured_observations:
        # Validar que cada observación tenga los campos requeridos
        for obs in request.structured_observations:
            if not isinstance(obs, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Cada observación estructurada debe ser un objeto/diccionario"
                )
            required_fields = ["section", "comment", "severity"]
            missing = [f for f in required_fields if f not in obs]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Observación estructurada incompleta. Faltan campos: {', '.join(missing)}"
                )
            if obs["severity"] not in ("low", "medium", "high", "critical"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Severidad inválida: {obs['severity']}. Debe ser: low, medium, high, critical"
                )
        structured_obs = request.structured_observations
    
    # Si hay versión asociada, usar reject_version (que maneja el rechazo de la versión)
    # Si no hay versión, solo rechazar la validación directamente usando reject_validation
    if version:
        # Hay versión, usar el helper reject_version que maneja todo
        try:
            rejected_version = reject_version(
                session=session,
                validation_id=validation_id,
                rejector_id=user_id,
                observations=request.observations,
                structured_observations=structured_obs,
            )
            session.flush()
            session.refresh(validation)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # No hay versión, solo rechazar la validación (flujo legacy o validación sin versión)
        logger.warning(f"Rechazando validación {validation_id} sin versión asociada (flujo legacy)")
        try:
            # Si hay observaciones estructuradas, guardarlas en checklist_json
            checklist_data = {}
            if validation.checklist_json:
                try:
                    checklist_data = json.loads(validation.checklist_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if structured_obs:
                checklist_data["observations"] = structured_obs
                checklist_data["rejected_at"] = datetime.now(UTC).isoformat()
                checklist_data["rejected_by"] = user_id
            
            # Actualizar checklist_json si hay observaciones estructuradas
            if structured_obs:
                validation.checklist_json = json.dumps(checklist_data)
            
            rejected_validation = reject_validation(
                session=session,
                validation_id=validation_id,
                observations=request.observations,
                user_id=user_id,
            )
            session.flush()
            session.refresh(validation)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
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

