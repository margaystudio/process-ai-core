"""
CRUD de documentos: listar, obtener, actualizar, eliminar y detalles de Process.

Incluye los listados especializados (pendientes de aprobación, a revisar).
"""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion, Process, Recipe, Run
from process_ai_core.db.helpers import delete_document
from process_ai_core.db.permissions import has_permission, can_view_folder

from api.models.requests import DocumentResponse, DocumentUpdateRequest
from api.dependencies import get_current_user_id
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
)

from ._helpers import _assert_doc_in_active_workspace

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_open_questions_metadata(session, doc: Document) -> Optional[dict[str, Any]]:
    """
    Extrae metadata de "preguntas_abiertas" desde una versión aprobada del documento.

    Esta metadata se usa para mostrar preguntas pendientes en la UI fuera del PDF.
    """
    approved_version = None

    if doc.approved_version_id:
        approved_version = (
            session.query(DocumentVersion)
            .filter(
                DocumentVersion.id == doc.approved_version_id,
                DocumentVersion.document_id == doc.id,
                DocumentVersion.content_json.isnot(None),
            )
            .first()
        )

    if approved_version is None:
        approved_version = (
            session.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.version_status == "APPROVED",
                DocumentVersion.content_json.isnot(None),
            )
            .order_by(DocumentVersion.version_number.desc(), DocumentVersion.created_at.desc())
            .first()
        )

    if not approved_version or not approved_version.content_json:
        return None

    try:
        parsed = json.loads(approved_version.content_json)
    except (json.JSONDecodeError, TypeError):
        return None

    open_questions = parsed.get("preguntas_abiertas")
    if not isinstance(open_questions, str):
        return None

    open_questions = open_questions.strip()
    if not open_questions:
        return None

    return {
        "preguntas_abiertas": open_questions,
    }


@router.get("/pending-approval", response_model=list[DocumentResponse])
async def list_documents_pending_approval(
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Lista documentos pendientes de aprobación para un usuario con rol de aprobador.

    Solo usuarios con rol "owner", "admin" o "approver" pueden ver esta lista.

    Args:
        workspace_id: ID del workspace
        user_id: ID del usuario

    Returns:
        Lista de documentos con status="pending_validation"
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    with get_db_session() as session:
        # Verificar permisos usando el sistema de permisos
        from process_ai_core.db.permissions import has_permission

        if not has_permission(session, user_id, workspace_id, "documents.approve"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para ver documentos pendientes de aprobación"
            )

        # Documentos pendientes de validación que el usuario SÍ puede revisar:
        # excluir aquellos cuya versión IN_REVIEW fue creada por este usuario (segregación).
        from sqlalchemy import or_
        documents = (
            session.query(Document)
            .join(
                DocumentVersion,
                (DocumentVersion.document_id == Document.id)
                & (DocumentVersion.version_status == "IN_REVIEW"),
            )
            .filter(
                Document.workspace_id == workspace_id,
                Document.status == "pending_validation",
                or_(
                    DocumentVersion.created_by.is_(None),
                    DocumentVersion.created_by != user_id,
                ),
            )
            .order_by(Document.created_at.asc())
            .distinct()
            .all()
        )
        # Solo documentos en carpetas donde el usuario puede aprobar (roles operativos)
        from process_ai_core.db.permissions import can_approve_in_folder
        documents = [d for d in documents if can_approve_in_folder(session, user_id, workspace_id, d.folder_id)]

        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                domain=doc.domain,
                document_type=getattr(doc, "document_type", "procedimiento"),
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("/to-review", response_model=list[DocumentResponse])
async def list_documents_to_review(
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Lista documentos rechazados que el usuario creador debe revisar y corregir.

    Args:
        workspace_id: ID del workspace
        user_id: ID del usuario creador

    Returns:
        Lista de documentos con status="rejected" creados por el usuario
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    with get_db_session() as session:
        # Verificar que el usuario puede ver documentos
        from process_ai_core.db.permissions import has_permission

        if not has_permission(session, user_id, workspace_id, "documents.view"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para ver documentos"
            )

        # Obtener documentos rechazados del workspace
        # Por ahora, todos los documentos rechazados (luego podemos filtrar por creador)
        documents = session.query(Document).filter_by(
            workspace_id=workspace_id,
            status="rejected",
        ).order_by(Document.created_at.desc()).all()
        documents = [d for d in documents if can_view_folder(session, user_id, workspace_id, d.folder_id)]

        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                domain=doc.domain,
                document_type=getattr(doc, "document_type", "procedimiento"),
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    folder_id: Optional[str] = Query(None, description="ID de la carpeta (opcional)"),
    domain: str = Query("process", description="Tipo de documento"),
    status: Optional[str] = Query(None, description="Filtrar por estado (draft|pending_validation|approved|rejected|archived)"),
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Lista documentos de un workspace.

    Requiere autenticación. Si el usuario tiene rol "viewer", solo se devuelven
    documentos con status "approved", independientemente del parámetro status.

    Args:
        workspace_id: ID del workspace (query parameter, requerido)
        folder_id: ID de la carpeta (query parameter, opcional - si se especifica, solo documentos de esa carpeta)
                   Si es "null" (string), devuelve solo documentos sin carpeta
        domain: Tipo de documento (query parameter, default: "process")
        status: Filtrar por estado (query parameter, opcional)
        user_id: ID del usuario autenticado (desde token JWT)

    Returns:
        Lista de DocumentResponse
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    with get_db_session() as session:
        # Verificar permiso documents.view en el workspace
        if not has_permission(session, user_id, workspace_id, "documents.view"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para ver documentos en este workspace"
            )

        # Si el usuario es viewer, forzar status=approved por seguridad
        from process_ai_core.db.permissions import get_user_role
        user_role = get_user_role(session, user_id, workspace_id)
        if user_role and user_role.name == "viewer":
            status = "approved"

        query = session.query(Document).filter_by(
            workspace_id=workspace_id,
            domain=domain
        )

        if folder_id:
            if folder_id.lower() == "null":
                query = query.filter(Document.folder_id.is_(None))
            else:
                query = query.filter_by(folder_id=folder_id)

        if status:
            query = query.filter(Document.status == status)

        documents = query.order_by(Document.created_at.desc()).all()
        # Filtrar por acceso a carpeta (roles operativos)
        documents = [d for d in documents if can_view_folder(session, user_id, workspace_id, d.folder_id)]

        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                domain=doc.domain,
                document_type=getattr(doc, "document_type", "procedimiento"),
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Obtiene un documento por su ID.

    Requiere autenticación y permiso documents.view en el workspace del documento.

    Args:
        document_id: ID del documento

    Returns:
        DocumentResponse

    Raises:
        401: Si no hay token de autenticación
        403: Si el usuario no tiene permiso documents.view
        404: Si el documento no existe
    """
    with get_db_session() as session:
        # Usar polymorphic_identity para obtener el tipo correcto
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        # Verificar permiso documents.view en el workspace del documento
        if not has_permission(session, user_id, doc.workspace_id, "documents.view"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para ver este documento"
            )

        # Verificar acceso a la carpeta del documento (roles operativos)
        if not can_view_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso a la carpeta de este documento"
            )

        # Si el usuario es viewer, solo puede ver documentos aprobados
        from process_ai_core.db.permissions import get_user_role
        user_role = get_user_role(session, user_id, doc.workspace_id)
        if user_role and user_role.name == "viewer" and doc.status != "approved":
            raise HTTPException(
                status_code=403,
                detail="Solo puede ver documentos aprobados"
            )

        # Si es un Process, obtener los campos específicos
        if doc.domain == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if process:
                # Retornar con campos extendidos (aunque DocumentResponse no los incluye,
                # los podemos agregar en metadata o crear un response extendido)
                # Por ahora, solo retornamos los campos básicos
                pass

        return DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            folder_id=doc.folder_id,
            domain=doc.domain,
            document_type=getattr(doc, "document_type", "procedimiento"),
            name=doc.name,
            description=doc.description,
            status=doc.status,
            metadata=_extract_open_questions_metadata(session, doc),
            created_at=doc.created_at.isoformat(),
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Actualiza un documento.

    Args:
        document_id: ID del documento
        request: Datos a actualizar

    Returns:
        DocumentResponse actualizado

    Raises:
        404: Si el documento no existe
        400: Si el documento tiene versiones inmutables (IN_REVIEW)
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        if not has_permission(session, user_id, doc.workspace_id, "documents.edit"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para editar documentos en este workspace"
            )

        from process_ai_core.db.permissions import can_view_folder
        if not can_view_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso a la carpeta de este documento"
            )

        # Verificar inmutabilidad (bloquea solo si hay IN_REVIEW)
        from process_ai_core.db.helpers import check_version_immutable
        is_immutable, reason = check_version_immutable(session, document_id)
        if is_immutable:
            raise HTTPException(
                status_code=400,
                detail=reason
            )

        # Si se quiere mover a otra carpeta, verificar acceso a la carpeta destino
        if request.folder_id is not None and request.folder_id != doc.folder_id:
            from process_ai_core.db.permissions import can_create_in_folder
            if not can_create_in_folder(session, user_id, doc.workspace_id, request.folder_id):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene acceso para mover documentos a la carpeta destino"
                )

        # Actualizar campos básicos
        if request.name is not None:
            doc.name = request.name
        if request.description is not None:
            doc.description = request.description
        if request.status is not None:
            doc.status = request.status
        if request.folder_id is not None:
            doc.folder_id = request.folder_id
        if request.document_type is not None:
            doc.document_type = request.document_type

        # Actualizar campos específicos según el tipo
        if doc.domain == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if not process:
                # Si no existe el Process, crearlo (no debería pasar, pero por seguridad)
                process = Process(
                    id=document_id,
                    workspace_id=doc.workspace_id,
                    folder_id=doc.folder_id,
                    domain="process",
                    name=doc.name,
                    description=doc.description,
                    status=doc.status,
                )
                session.add(process)

            if request.audience is not None:
                process.audience = request.audience
            if request.detail_level is not None:
                process.detail_level = request.detail_level
            if request.context_text is not None:
                process.context_text = request.context_text
        elif doc.domain == "recipe":
            recipe = session.query(Recipe).filter_by(id=document_id).first()
            if recipe:
                if request.cuisine is not None:
                    recipe.cuisine = request.cuisine
                if request.difficulty is not None:
                    recipe.difficulty = request.difficulty
                if request.servings is not None:
                    recipe.servings = request.servings
                if request.prep_time is not None:
                    recipe.prep_time = request.prep_time
                if request.cook_time is not None:
                    recipe.cook_time = request.cook_time

        session.commit()
        session.refresh(doc)

        # Si es Process, refrescar también el Process
        if doc.domain == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if process:
                session.refresh(process)

        return DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            folder_id=doc.folder_id,
            domain=doc.domain,
            document_type=getattr(doc, "document_type", "procedimiento"),
            name=doc.name,
            description=doc.description,
            status=doc.status,
            created_at=doc.created_at.isoformat(),
        )


@router.delete("/{document_id}")
async def delete_document_endpoint(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Elimina un documento y todos sus datos asociados.

    Requiere el permiso documents.delete en el workspace del documento.

    Elimina:
    - El documento
    - Todos los runs asociados
    - Todos los artifacts asociados
    - Todas las validaciones asociadas
    - Todos los audit logs asociados
    - Todas las versiones asociadas

    Política de códigos de respuesta:
    - 404: El documento no existe.
    - 403: El documento existe pero el usuario no tiene permiso documents.delete
      en el workspace.
    Se distingue entre ambos para permitir mensajes de error claros al usuario.
    Si se prefiriera no revelar existencia del recurso, se podría devolver 404
    en ambos casos (comprobando permiso antes de existencia).

    Args:
        document_id: ID del documento a eliminar

    Returns:
        Mensaje de confirmación

    Raises:
        401: Si no hay token de autenticación
        403: Si el usuario no tiene permiso documents.delete
        404: Si el documento no existe
        500: Error interno del servidor
    """
    with get_db_session() as session:
        # Verificar que el documento existe
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        # Verificar permiso documents.delete en el workspace del documento
        if not has_permission(session, user_id, doc.workspace_id, "documents.delete"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para eliminar documentos en este workspace"
            )

        if not can_view_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso a la carpeta de este documento"
            )

        # Obtener runs antes de eliminar para limpiar archivos físicos
        runs = session.query(Run).filter_by(document_id=document_id).all()
        run_ids = [run.id for run in runs]
        doc_workspace_id = doc.workspace_id  # capturar antes del delete (doc se expira)

        try:
            # Eliminar el documento y todos sus datos asociados
            delete_document(session, document_id)

            # Liberar el storage del documento: sus runs y sus PDFs aprobados (en el
            # bucket y en disco local — delete_prefix funciona para ambos backends).
            from process_ai_core.storage import get_storage, run_prefix, workspace_prefix
            storage = get_storage()
            for run_id in run_ids:
                try:
                    storage.delete_prefix(run_prefix(doc_workspace_id, run_id))
                except Exception as e:
                    logger.warning(f"No se pudo borrar storage del run {run_id}: {e}")
            try:
                storage.delete_prefix(f"{workspace_prefix(doc_workspace_id)}/documents/{document_id}")
            except Exception as e:
                logger.warning(f"No se pudo borrar storage del documento {document_id}: {e}")

            # Recalcular uso de storage del tenant (best-effort).
            from process_ai_core.db.helpers import update_workspace_storage_usage
            update_workspace_storage_usage(session, doc_workspace_id)

            session.commit()

            return {
                "message": f"Documento {document_id} eliminado exitosamente",
                "deleted_runs": len(run_ids),
            }

        except ValueError as e:
            session.rollback()
            raise HTTPException(
                status_code=404,
                detail=str(e)
            ) from e
        except Exception as e:
            session.rollback()
            logger.exception(f"Error eliminando documento {document_id}")
            raise HTTPException(
                status_code=500,
                detail=f"Error interno al eliminar documento: {str(e)}"
            ) from e


@router.get("/{document_id}/process")
async def get_process_details(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Obtiene los campos específicos de un Process.

    Solo funciona para documentos de tipo "process".
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        from process_ai_core.db.permissions import can_view_folder
        if not can_view_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso a la carpeta de este documento"
            )

        if doc.domain != "process":
            raise HTTPException(
                status_code=400,
                detail=f"El documento {document_id} no es un proceso"
            )

        process = session.query(Process).filter_by(id=document_id).first()
        if not process:
            # Si no existe el Process, devolver valores vacíos
            return {
                "audience": "",
                "detail_level": "",
                "context_text": "",
            }

        return {
            "audience": process.audience or "",
            "detail_level": process.detail_level or "",
            "context_text": process.context_text or "",
        }
