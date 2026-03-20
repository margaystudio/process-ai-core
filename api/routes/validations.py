"""
Endpoints para gestion de validaciones de documentos.

Este modulo maneja:
- POST /api/v1/documents/{document_id}/validate - Crear validacion
- POST /api/v1/validations/{validation_id}/approve - Aprobar validacion (y version asociada)
- POST /api/v1/validations/{validation_id}/reject - Rechazar validacion con observaciones (texto libre y/o estructuradas)
- GET /api/v1/documents/{document_id}/validations - Listar validaciones de un documento

Nota: Los endpoints de versiones (submit, clone) estan en api/routes/documents.py
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
    reject_validation,
    approve_version,
    reject_version,
    get_in_review_version,
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

@router.post("/documents/{document_id}/validate", response_model=ValidationResponse)
async def create_document_validation(
    document_id: str,
    request: ValidationCreateRequest = Body(...),
):
    """
    Crea una nueva validacion para un documento.
    
    Args:
        document_id: ID del documento
        request: Datos de la validacion (run_id opcional, observations, checklist_json)
    
    Returns:
        ValidationResponse con la validacion creada
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
        
        # Buscar version IN_REVIEW existente para asociar la validacion
        from process_ai_core.db.models import DocumentVersion
        version_in_review = session.query(DocumentVersion).filter_by(
            document_id=document_id,
            version_status="IN_REVIEW"
        ).first()
        
        # Crear validacion
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=request.run_id,
            observations=request.observations,
            checklist_json=request.checklist_json,
        )
        session.flush()  # Flush para obtener el ID de la validacion
        
        # Si hay una version IN_REVIEW, asociarla a la validacion
        if version_in_review:
            version_in_review.validation_id = validation.id
            logger.info(f"Validacion {validation.id} asociada a version IN_REVIEW {version_in_review.id}")
        else:
            logger.warning(f"No hay version IN_REVIEW para el documento {document_id}. La validacion {validation.id} no esta asociada a ninguna version.")
        
        # Actualizar estado del documento a pending_validation si no lo esta
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


class ValidationApproveRequest(BaseModel):
    observations: Optional[str] = ""


class ValidationRejectDirectRequest(BaseModel):
    observations: str  # REQUIRED para rechazo


class ValidationDecisionResponse(BaseModel):
    version_id: str
    version_status: str
    validation_id: str
    document_status: str


@router.post("/documents/{document_id}/validate/approve", response_model=ValidationDecisionResponse)
async def approve_document_validation_direct(
    document_id: str,
    request: ValidationApproveRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Aprueba directamente una version IN_REVIEW del documento (one-shot validation).
    
    Este endpoint:
    1. Busca la version IN_REVIEW del documento
    2. Si no existe, devuelve 400
    3. Usa el validation_id asociado a la version (creado en submit)
    4. Ejecuta approve_version que cambia la version a APPROVED
    
    Solo usuarios con permisos para aprobar documentos pueden usar este endpoint.
    
    Args:
        document_id: ID del documento
        request: Observaciones opcionales
        user_id: ID del usuario (extraido del JWT)
    
    Returns:
        ValidationDecisionResponse con version_id, version_status, validation_id, document_status
    """
    from process_ai_core.db.permissions import has_permission
    from process_ai_core.db.models import Document, DocumentVersion, Validation
    
    # Obtener documento para verificar workspace
    doc = session.query(Document).filter_by(id=document_id).first()
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Documento {document_id} no encontrado"
        )
    
    workspace_id = doc.workspace_id
    
    # Verificar permisos
    if not has_permission(session, user_id, workspace_id, "documents.approve"):
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para aprobar documentos"
        )
    from process_ai_core.db.permissions import can_approve_in_folder
    if not can_approve_in_folder(session, user_id, workspace_id, doc.folder_id):
        raise HTTPException(
            status_code=403,
            detail="No tiene acceso para aprobar documentos en la carpeta de este documento"
        )
    
    # Buscar version IN_REVIEW
    version = get_in_review_version(session, document_id)
    if not version:
        raise HTTPException(
            status_code=400,
            detail=f"No hay version IN_REVIEW para el documento {document_id}. El documento debe estar en estado 'pending_validation' con una version enviada a revision."
        )
    
    # Validar segregacion de funciones: el creador no puede aprobar su propia version
    if version.created_by and version.created_by == user_id:
        raise HTTPException(
            status_code=403,
            detail="No puedes aprobar una version que creaste. Debe validarla otro usuario."
        )
    
    # Loggear warning si created_by es NULL (versiones antiguas)
    if not version.created_by:
        logger.warning(f"Version {version.id} no tiene created_by. Permitir validacion pero registrar en logs.")
    
    # Verificar que la version tenga validation_id asociado (deberia existir desde submit)
    if not version.validation_id:
        # Si no tiene validation_id, crear una validacion pendiente y asociarla
        logger.warning(f"Version {version.id} no tiene validation_id asociado, creando validacion")
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=version.run_id,
            observations=request.observations or "",
            checklist_json="{}",
        )
        session.flush()
        version.validation_id = validation.id
        session.flush()
    else:
        # Actualizar observaciones si se proporcionan
        validation = session.query(Validation).filter_by(id=version.validation_id).first()
        if validation and request.observations:
            validation.observations = request.observations
    
    # Aprobar version usando el helper existente
    try:
        approved_version = approve_version(
            session=session,
            validation_id=version.validation_id,
            approver_id=user_id,
        )
        session.commit()
        session.refresh(doc)
        
        return ValidationDecisionResponse(
            version_id=approved_version.id,
            version_status=approved_version.version_status,
            validation_id=version.validation_id,
            document_status=doc.status,
        )
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/{document_id}/validate/reject", response_model=ValidationDecisionResponse)
async def reject_document_validation_direct(
    document_id: str,
    request: ValidationRejectDirectRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
):
    """
    Rechaza directamente una version IN_REVIEW del documento (one-shot validation).
    
    Este endpoint:
    1. Busca la version IN_REVIEW del documento
    2. Si no existe, devuelve 400
    3. Usa el validation_id asociado a la version (creado en submit)
    4. Ejecuta reject_version que cambia la version a REJECTED
    
    Las observaciones son OBLIGATORIAS para rechazar.
    
    Solo usuarios con permisos para rechazar documentos pueden usar este endpoint.
    
    Args:
        document_id: ID del documento
        request: Observaciones (REQUIRED)
        user_id: ID del usuario (extraido del JWT)
    
    Returns:
        ValidationDecisionResponse con version_id, version_status, validation_id, document_status
    """
    from process_ai_core.db.permissions import has_permission
    from process_ai_core.db.models import Document, DocumentVersion, Validation
    
    # Validar que observations no este vacio
    if not request.observations or not request.observations.strip():
        raise HTTPException(
            status_code=400,
            detail="Las observaciones son obligatorias para rechazar un documento"
        )
    
    # Obtener documento para verificar workspace
    doc = session.query(Document).filter_by(id=document_id).first()
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Documento {document_id} no encontrado"
        )
    
    workspace_id = doc.workspace_id
    
    # Verificar permisos
    if not has_permission(session, user_id, workspace_id, "documents.reject"):
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para rechazar documentos"
        )
    from process_ai_core.db.permissions import can_approve_in_folder
    if not can_approve_in_folder(session, user_id, workspace_id, doc.folder_id):
        raise HTTPException(
            status_code=403,
            detail="No tiene acceso para rechazar documentos en la carpeta de este documento"
        )
    
    # Buscar version IN_REVIEW
    version = get_in_review_version(session, document_id)
    if not version:
        raise HTTPException(
            status_code=400,
            detail=f"No hay version IN_REVIEW para el documento {document_id}. El documento debe estar en estado 'pending_validation' con una version enviada a revision."
        )
    
    # Validar segregacion de funciones: el creador no puede rechazar su propia version
    if version.created_by and version.created_by == user_id:
        raise HTTPException(
            status_code=403,
            detail="No puedes rechazar una version que creaste. Debe validarla otro usuario."
        )
    
    # Loggear warning si created_by es NULL (versiones antiguas)
    if not version.created_by:
        logger.warning(f"Version {version.id} no tiene created_by. Permitir validacion pero registrar en logs.")
    
    # Verificar que la version tenga validation_id asociado (deberia existir desde submit)
    if not version.validation_id:
        # Si no tiene validation_id, crear una validacion pendiente y asociarla
        logger.warning(f"Version {version.id} no tiene validation_id asociado, creando validacion")
        validation = create_validation(
            session=session,
            document_id=document_id,
            run_id=version.run_id,
            observations=request.observations,
            checklist_json="{}",
        )
        session.flush()
        version.validation_id = validation.id
        session.flush()
    
    # Rechazar version usando el helper existente
    try:
        rejected_version = reject_version(
            session=session,
            validation_id=version.validation_id,
            rejector_id=user_id,
            observations=request.observations,
            structured_observations=None,
        )
        session.commit()
        session.refresh(doc)
        
        return ValidationDecisionResponse(
            version_id=rejected_version.id,
            version_status=rejected_version.version_status,
            validation_id=version.validation_id,
            document_status=doc.status,
        )
    except ValueError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validations/{validation_id}/approve", response_model=ValidationResponse)
async def approve_document_validation(
    validation_id: str,
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Aprueba una validacion (y su version asociada).
    
    Cuando se aprueba:
    - La version IN_REVIEW cambia a APPROVED
    - Se marca como version actual (is_current=True)
    - La version anterior APPROVED se marca como OBSOLETE
    - El estado del documento pasa a "approved"
    
    Solo usuarios con permisos para aprobar documentos pueden usar este endpoint.
    
    Args:
        validation_id: ID de la validacion
        user_id: ID del usuario que aprueba
        workspace_id: ID del workspace
    
    Returns:
        ValidationResponse con la validacion aprobada
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
                detail=f"Validacion {validation_id} no encontrada"
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
        from process_ai_core.db.permissions import can_approve_in_folder
        if not can_approve_in_folder(session, user_id, workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso para aprobar documentos en la carpeta de este documento"
            )
        
        if validation.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"La validacion ya esta {validation.status}, no se puede aprobar"
            )
        
        # Aprobar version usando el nuevo helper
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
    Rechaza una validacion (y su version asociada) con observaciones.
    
    Cuando se rechaza:
    - La version IN_REVIEW cambia a REJECTED
    - El estado del documento pasa a "rejected"
    - Las observaciones (texto libre y/o estructuradas) se guardan para correccion posterior
    
    Solo usuarios con permisos para rechazar documentos pueden usar este endpoint.
    
    Args:
        validation_id: ID de la validacion
        request: Observaciones del rechazo (texto libre y/o estructuradas)
        user_id: ID del usuario que rechaza
        workspace_id: ID del workspace
    
    Returns:
        ValidationResponse con la validacion rechazada
    """
    # Verificar permisos
    from process_ai_core.db.permissions import has_permission
    
    # Obtener la validacion para encontrar el documento y workspace
    validation = session.query(Validation).filter_by(id=validation_id).first()
    if not validation:
        raise HTTPException(
            status_code=404,
            detail=f"Validacion {validation_id} no encontrada"
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
    from process_ai_core.db.permissions import can_approve_in_folder
    if not can_approve_in_folder(session, user_id, workspace_id, doc.folder_id):
        raise HTTPException(
            status_code=403,
            detail="No tiene acceso para rechazar documentos en la carpeta de este documento"
        )
    
    if validation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"La validacion ya esta {validation.status}, no se puede rechazar"
        )
    
    # Intentar encontrar o asociar una version IN_REVIEW
    from process_ai_core.db.models import DocumentVersion
    version = session.query(DocumentVersion).filter_by(validation_id=validation_id).first()
    
    if not version:
        # Buscar version IN_REVIEW para este documento
        version_in_review = session.query(DocumentVersion).filter_by(
            document_id=validation.document_id,
            version_status="IN_REVIEW"
        ).first()
        if version_in_review:
            # Asociar la version a la validacion
            version_in_review.validation_id = validation_id
            session.flush()
            version = version_in_review
            logger.info(f"Validacion {validation_id} asociada a version IN_REVIEW {version.id} durante el rechazo")
    
    # Validar formato de observaciones estructuradas si se proporcionan
    structured_obs = None
    if request.structured_observations:
        # Validar que cada observacion tenga los campos requeridos
        for obs in request.structured_observations:
            if not isinstance(obs, dict):
                raise HTTPException(
                    status_code=400,
                    detail="Cada observacion estructurada debe ser un objeto/diccionario"
                )
            required_fields = ["section", "comment", "severity"]
            missing = [f for f in required_fields if f not in obs]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Observacion estructurada incompleta. Faltan campos: {', '.join(missing)}"
                )
            if obs["severity"] not in ("low", "medium", "high", "critical"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Severidad invalida: {obs['severity']}. Debe ser: low, medium, high, critical"
                )
        structured_obs = request.structured_observations
    
    # Si hay version asociada, usar reject_version (que maneja el rechazo de la version)
    # Si no hay version, solo rechazar la validacion directamente usando reject_validation
    if version:
        # Hay version, usar el helper reject_version que maneja todo
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
        # No hay version, solo rechazar la validacion (flujo legacy o validacion sin version)
        logger.warning(f"Rechazando validacion {validation_id} sin version asociada (flujo legacy)")
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
        Lista de ValidationResponse ordenadas por fecha de creacion (mas recientes primero)
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

