"""
Endpoint para gestionar documentos (procesos, recetas, etc.).

Este endpoint maneja:
- GET /api/v1/documents: Listar documentos de un workspace (opcionalmente filtrados por folder)
- GET /api/v1/documents/{document_id}: Obtener un documento por ID
- PUT /api/v1/documents/{document_id}: Actualizar un documento
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Query, Body, Depends, BackgroundTasks
from typing import List, Optional
import re
import tempfile
import shutil
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion, Process, Recipe, Workspace, Run, Artifact
from process_ai_core.db.helpers import (
    create_run, create_artifact, delete_document,
    submit_version_for_review, get_or_create_draft, approve_version, reject_version,
    get_in_review_version, get_editable_version, create_audit_log, update_document_status,
    cancel_submission,
)
from process_ai_core.config import get_settings
from process_ai_core.domain_models import RawAsset
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.engine import run_process_pipeline
from process_ai_core.prompt_context import build_context_block
from process_ai_core.export import export_pdf, get_export_content, export_pdf_from_content
from process_ai_core.ingest import discover_raw_assets
from fastapi.responses import Response

from ..models.requests import DocumentResponse, DocumentUpdateRequest, ProcessRunResponse
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/pending-approval", response_model=list[DocumentResponse])
async def list_documents_pending_approval(
    workspace_id: str = Query(..., description="ID del workspace"),
    user_id: str = Query(..., description="ID del usuario (para verificar rol)"),
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
        
        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                document_type=doc.document_type,
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("/to-review", response_model=list[DocumentResponse])
async def list_documents_to_review(
    workspace_id: str = Query(..., description="ID del workspace"),
    user_id: str = Query(..., description="ID del usuario creador"),
):
    """
    Lista documentos rechazados que el usuario creador debe revisar y corregir.
    
    Args:
        workspace_id: ID del workspace
        user_id: ID del usuario creador
    
    Returns:
        Lista de documentos con status="rejected" creados por el usuario
    """
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
        
        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                document_type=doc.document_type,
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    workspace_id: Optional[str] = Query(None, description="ID del workspace"),
    folder_id: Optional[str] = Query(None, description="ID de la carpeta (opcional)"),
    document_type: str = Query("process", description="Tipo de documento")
):
    """
    Lista documentos de un workspace.

    Args:
        workspace_id: ID del workspace (query parameter, requerido)
        folder_id: ID de la carpeta (query parameter, opcional - si se especifica, solo documentos de esa carpeta)
                   Si es "null" (string), devuelve solo documentos sin carpeta
        document_type: Tipo de documento (query parameter, default: "process")

    Returns:
        Lista de DocumentResponse
    """
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="workspace_id es requerido"
        )
    
    with get_db_session() as session:
        query = session.query(Document).filter_by(
            workspace_id=workspace_id,
            document_type=document_type
        )
        
        if folder_id:
            if folder_id.lower() == "null":
                # Devolver solo documentos sin carpeta
                query = query.filter(Document.folder_id.is_(None))
            else:
                # Devolver documentos de esa carpeta específica
                query = query.filter_by(folder_id=folder_id)
        # Si folder_id no se especifica, devolver todos los documentos del workspace
        
        documents = query.order_by(Document.created_at.desc()).all()
        
        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                document_type=doc.document_type,
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Obtiene un documento por su ID.

    Args:
        document_id: ID del documento

    Returns:
        DocumentResponse

    Raises:
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

        # Si es un Process, obtener los campos específicos
        if doc.document_type == "process":
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
            document_type=doc.document_type,
            name=doc.name,
            description=doc.description,
            status=doc.status,
            created_at=doc.created_at.isoformat(),
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: str, request: DocumentUpdateRequest):
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
        
        # Verificar inmutabilidad (bloquea solo si hay IN_REVIEW)
        from process_ai_core.db.helpers import check_version_immutable
        is_immutable, reason = check_version_immutable(session, document_id)
        if is_immutable:
            raise HTTPException(
                status_code=400,
                detail=reason
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

        # Actualizar campos específicos según el tipo
        if doc.document_type == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if not process:
                # Si no existe el Process, crearlo (no debería pasar, pero por seguridad)
                process = Process(
                    id=document_id,
                    workspace_id=doc.workspace_id,
                    folder_id=doc.folder_id,
                    document_type="process",
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
        elif doc.document_type == "recipe":
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
        if doc.document_type == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if process:
                session.refresh(process)

        return DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            folder_id=doc.folder_id,
            document_type=doc.document_type,
            name=doc.name,
            description=doc.description,
            status=doc.status,
            created_at=doc.created_at.isoformat(),
        )


@router.delete("/{document_id}")
async def delete_document_endpoint(document_id: str):
    """
    Elimina un documento y todos sus datos asociados.
    
    Elimina:
    - El documento
    - Todos los runs asociados
    - Todos los artifacts asociados
    - Todas las validaciones asociadas
    - Todos los audit logs asociados
    - Todas las versiones asociadas
    
    Args:
        document_id: ID del documento a eliminar
    
    Returns:
        Mensaje de confirmación
    
    Raises:
        404: Si el documento no existe
        500: Error interno del servidor
    """
    import shutil
    from pathlib import Path
    from process_ai_core.config import get_settings
    from process_ai_core.db.models import Run
    
    with get_db_session() as session:
        # Verificar que el documento existe
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        # Obtener runs antes de eliminar para limpiar archivos físicos
        runs = session.query(Run).filter_by(document_id=document_id).all()
        run_ids = [run.id for run in runs]
        
        try:
            # Eliminar el documento y todos sus datos asociados
            delete_document(session, document_id)
            
            # Limpiar archivos físicos de los runs
            settings = get_settings()
            for run_id in run_ids:
                run_dir = Path(settings.output_dir) / run_id
                if run_dir.exists():
                    try:
                        shutil.rmtree(run_dir)
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar directorio {run_dir}: {e}")
            
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
async def get_process_details(document_id: str):
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
        
        if doc.document_type != "process":
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


@router.get("/{document_id}/runs")
async def get_document_runs(document_id: str):
    """
    Obtiene todos los runs asociados a un documento.
    """
    from process_ai_core.db.models import Run, Artifact
    
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        runs = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).all()
        
        result = []
        for run in runs:
            artifacts = session.query(Artifact).filter_by(run_id=run.id).all()
            artifact_dict = {}
            for artifact in artifacts:
                # Construir URL del artifact
                # El path puede ser "output/{run_id}/process.pdf" o solo el filename
                filename = artifact.path.split('/')[-1]
                artifact_url = f"/api/v1/artifacts/{run.id}/{filename}"
                artifact_dict[artifact.type] = artifact_url
            
            result.append({
                "run_id": run.id,
                "created_at": run.created_at.isoformat(),
                "artifacts": artifact_dict,
            })
        
        return result


@router.post("/{document_id}/runs")
async def create_document_run(
    document_id: str,
    audio_files: List[UploadFile] = File(default=[]),
    video_files: List[UploadFile] = File(default=[]),
    image_files: List[UploadFile] = File(default=[]),
    text_files: List[UploadFile] = File(default=[]),
    revision_notes: str = Form(""),
    reuse_previous_files: bool = Form(False),
    user_id: str = Depends(get_current_user_id),
):
    """
    Crea un nuevo run para un documento existente.
    
    Permite generar una nueva versión del documento con archivos nuevos, instrucciones de revisión,
    o reutilizando los archivos del run anterior.
    
    Args:
        document_id: ID del documento
        audio_files: Archivos de audio nuevos (opcional)
        video_files: Archivos de video nuevos (opcional)
        image_files: Archivos de imagen nuevos (opcional)
        text_files: Archivos de texto nuevos (opcional)
        revision_notes: Instrucciones de revisión para el LLM (opcional, ej: "Corregir errores gramaticales")
        reuse_previous_files: Si True, reutiliza archivos del último run (automático si hay revision_notes sin archivos)
    
    Returns:
        ProcessRunResponse con el nuevo run_id y artifacts
    
    Notas:
        - Si se proporcionan revision_notes sin archivos nuevos, se reutilizan automáticamente
          los archivos del último run.
        - Las revision_notes se agregan al contexto del prompt para guiar al LLM en las correcciones.
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        if doc.document_type != "process":
            raise HTTPException(
                status_code=400,
                detail="Este endpoint solo funciona para documentos de tipo 'process'"
            )
        
        # Obtener el Process para acceder a los campos específicos
        process = session.query(Process).filter_by(id=document_id).first()
        if not process:
            raise HTTPException(
                status_code=404,
                detail=f"Process {document_id} no encontrado"
            )
        
        # Obtener el último run para reutilizar archivos si es necesario
        last_run = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).first()
        
        # Validar que haya archivos, instrucciones de revisión, o que se puedan reutilizar
        total_new_files = len(audio_files) + len(video_files) + len(image_files) + len(text_files)
        has_revision_notes = revision_notes and revision_notes.strip()
        
        if total_new_files == 0 and not reuse_previous_files and not has_revision_notes:
            raise HTTPException(
                status_code=400,
                detail="Se requiere al menos un archivo nuevo, instrucciones de revisión, o activar 'reuse_previous_files'"
            )
        
        # Crear nuevo Run
        run = create_run(
            session=session,
            document_id=document_id,
            document_type="process",
            profile=process.audience or "operativo",
        )
        session.flush()
        run_id = run.id
        
        # Guardar valores necesarios antes de salir del contexto
        process_audience = process.audience or "operativo"
        document_name = doc.name
        
        # Construir context_block usando los datos del documento
        # Necesitamos obtener el workspace para build_context_block
        workspace = session.query(Workspace).filter_by(id=doc.workspace_id).first()
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace {doc.workspace_id} no encontrado"
            )
        
        # Usar build_context_block con session, workspace y document
        context_block = build_context_block(
            session=session,
            workspace=workspace,
            document=doc,
        )
        
        # Agregar instrucciones de revisión si existen
        if revision_notes and revision_notes.strip():
            context_block += "\n=== INSTRUCCIONES DE REVISIÓN ===\n"
            context_block += revision_notes.strip()
            context_block += "\n\n"
            context_block += "IMPORTANTE: Aplica estas correcciones y mejoras al generar el documento.\n\n"
    
    settings = get_settings()
    
    # Crear directorio temporal para los uploads
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        raw_assets: List[RawAsset] = []
        
        # Contadores para IDs deterministas
        counters = {"audio": 0, "video": 0, "image": 0, "text": 0}
        
        async def process_files(files: List[UploadFile], kind: str, prefix: str):
            """Procesa una lista de archivos y los agrega a raw_assets."""
            if not files:
                return
            
            for upload_file in files:
                counters[kind] += 1
                asset_id = f"{prefix}{counters[kind]}"
                
                # Guardar archivo en temp_dir
                ext = Path(upload_file.filename).suffix if upload_file.filename else ""
                temp_path = temp_dir / f"{asset_id}{ext}"
                
                # Leer contenido y guardar
                content = await upload_file.read()
                temp_path.write_bytes(content)
                
                # Construir RawAsset
                titulo = (
                    Path(upload_file.filename).stem
                    if upload_file.filename
                    else f"{kind} {counters[kind]}"
                )
                
                raw_assets.append(
                    RawAsset(
                        id=asset_id,
                        kind=kind,  # type: ignore
                        path_or_url=str(temp_path),
                        metadata={"titulo": titulo},
                    )
                )
        
        # Procesar archivos nuevos
        await process_files(audio_files, "audio", "aud")
        await process_files(video_files, "video", "vid")
        await process_files(image_files, "image", "img")
        await process_files(text_files, "text", "txt")
        
        # Si no hay archivos nuevos y se solicita reutilizar, obtener archivos del último run
        if total_new_files == 0 and (reuse_previous_files or has_revision_notes) and last_run:
            # Obtener el directorio del último run para descubrir los archivos originales
            last_run_dir = Path(settings.output_dir) / last_run.id
            
            # Buscar archivos en el directorio del último run (assets/, evidence/, etc.)
            if last_run_dir.exists():
                # Buscar en subdirectorios comunes
                possible_dirs = [
                    last_run_dir / "assets",
                    last_run_dir / "evidence",
                    last_run_dir,
                ]
                
                for search_dir in possible_dirs:
                    if search_dir.exists():
                        discovered = discover_raw_assets(search_dir)
                        if discovered:
                            # Convertir los paths absolutos a relativos o copiar a temp_dir
                            for asset in discovered:
                                # Copiar el archivo al temp_dir para procesarlo
                                source_path = Path(asset.path_or_url)
                                if source_path.exists():
                                    # Mantener el mismo ID y tipo
                                    new_path = temp_dir / f"{asset.id}{source_path.suffix}"
                                    shutil.copy2(source_path, new_path)
                                    raw_assets.append(
                                        RawAsset(
                                            id=asset.id,
                                            kind=asset.kind,
                                            path_or_url=str(new_path),
                                            metadata=asset.metadata,
                                        )
                                    )
                            break
        
        if not raw_assets and not has_revision_notes:
            raise HTTPException(
                status_code=400,
                detail="No se pudo obtener ningún archivo para procesar. Se requieren archivos o instrucciones de revisión."
            )
        
        # Obtener perfil según audience
        profile = get_profile(process_audience)
        
        # Ejecutar pipeline
        try:
            output_dir = Path(settings.output_dir) / run_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            result = run_process_pipeline(
                process_name=document_name,
                raw_assets=raw_assets,
                profile=profile,
                context_block=context_block,
                output_base=output_dir,
            )
            
            # Persistir artefactos
            json_path = output_dir / "process.json"
            md_path = output_dir / "process.md"
            
            json_path.write_text(result["json_str"], encoding="utf-8")
            md_path.write_text(result["markdown"], encoding="utf-8")
            
            # Generar PDF
            pdf_generated = False
            try:
                export_pdf(run_dir=output_dir, md_path=md_path, pdf_name="process.pdf")
                pdf_generated = True
            except Exception as pdf_error:
                pass
            
            # Construir paths relativos a los artefactos
            artifacts = {
                "json": f"/api/v1/artifacts/{run_id}/process.json",
                "markdown": f"/api/v1/artifacts/{run_id}/process.md",
            }
            if pdf_generated:
                artifacts["pdf"] = f"/api/v1/artifacts/{run_id}/process.pdf"
            
            # Persistir Artifacts en la base de datos y crear versión IN_REVIEW automáticamente
            with get_db_session() as db_session:
                from process_ai_core.db.helpers import update_document_status, get_or_create_draft
                from process_ai_core.db.models import DocumentVersion
                import uuid
                
                create_artifact(
                    session=db_session,
                    run_id=run_id,
                    artifact_type="json",
                    file_path=f"output/{run_id}/process.json",
                )
                create_artifact(
                    session=db_session,
                    run_id=run_id,
                    artifact_type="md",
                    file_path=f"output/{run_id}/process.md",
                )
                if pdf_generated:
                    create_artifact(
                        session=db_session,
                        run_id=run_id,
                        artifact_type="pdf",
                        file_path=f"output/{run_id}/process.pdf",
                    )
                
                # Crear versión DRAFT desde el run generado y enviarla automáticamente a revisión
                try:
                    # Leer el contenido generado
                    json_content = json_path.read_text(encoding="utf-8")
                    markdown_content = md_path.read_text(encoding="utf-8")
                    
                    # Obtener número de versión siguiente
                    last_version = (
                        db_session.query(DocumentVersion)
                        .filter_by(document_id=document_id)
                        .order_by(DocumentVersion.version_number.desc())
                        .first()
                    )
                    version_number = (last_version.version_number + 1) if last_version else 1
                    
                    # Verificar que no haya una versión IN_REVIEW existente
                    existing_in_review = (
                        db_session.query(DocumentVersion)
                        .filter_by(document_id=document_id, version_status="IN_REVIEW")
                        .first()
                    )
                    
                    if existing_in_review:
                        # Si ya hay IN_REVIEW, crear solo DRAFT (no enviar a revisión)
                        logger.info(f"Ya existe versión IN_REVIEW para documento {document_id}. Creando solo DRAFT.")
                        draft_version = DocumentVersion(
                            id=str(uuid.uuid4()),
                            document_id=document_id,
                            run_id=run_id,
                            version_number=version_number,
                            version_status="DRAFT",
                            content_type="generated",
                            content_json=json_content,
                            content_markdown=markdown_content,
                            is_current=False,
                            created_by=user_id,  # Setear created_by para segregación de funciones
                        )
                        db_session.add(draft_version)
                        db_session.flush()
                    else:
                        # Crear versión DRAFT; el creador enviará a revisión cuando esté conforme
                        draft_version = DocumentVersion(
                            id=str(uuid.uuid4()),
                            document_id=document_id,
                            run_id=run_id,
                            version_number=version_number,
                            version_status="DRAFT",
                            content_type="generated",
                            content_json=json_content,
                            content_markdown=markdown_content,
                            is_current=False,
                            created_by=user_id,  # Setear created_by para segregación de funciones
                        )
                        db_session.add(draft_version)
                        db_session.flush()
                    
                    # Dejar documento en draft para que el creador pueda revisar/corregir antes de enviar
                    update_document_status(
                        session=db_session,
                        document_id=document_id,
                        status="draft",
                    )
                    
                    db_session.commit()
                except Exception as e:
                    # Si falla la creación de versión, dejar en draft
                    logger.error(f"Error al crear versión desde run: {e}", exc_info=True)
                    update_document_status(
                        session=db_session,
                        document_id=document_id,
                        status="draft",
                    )
                    db_session.commit()
            
            from ..models.requests import ProcessRunResponse
            return ProcessRunResponse(
                run_id=run_id,
                process_name=document_name,
                status="completed",
                artifacts=artifacts,
            )
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando el pipeline: {str(e)}",
            ) from e


@router.put("/{document_id}/content")
async def update_document_content(
    document_id: str,
    content_json: str = Body(..., embed=True),
):
    """
    Edita manualmente el contenido de un documento.
    
    Usa get_or_create_draft() para obtener o crear una versión DRAFT.
    Solo permite editar si no hay versión IN_REVIEW.
    Dos PUT seguidos editan el mismo DRAFT (mismo version_id).
    
    Args:
        document_id: ID del documento
        content_json: JSON del documento editado (ProcessDocument en formato JSON)
    
    Returns:
        DocumentVersion creada o actualizada
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        if doc.document_type != "process":
            raise HTTPException(
                status_code=400,
                detail="Este endpoint solo funciona para documentos de tipo 'process'"
            )
        
        # Verificar inmutabilidad (bloquea solo si hay IN_REVIEW)
        from process_ai_core.db.helpers import check_version_immutable, get_or_create_draft
        is_immutable, reason = check_version_immutable(session, document_id)
        if is_immutable:
            raise HTTPException(
                status_code=400,
                detail=reason
            )
        
        # Obtener o crear DRAFT (si hay IN_REVIEW, esto fallará con ValueError)
        try:
            draft_version = get_or_create_draft(
                session=session,
                document_id=document_id,
                source_version_id=None,  # Usará APPROVED vigente si existe
                user_id=None,  # TODO: obtener del contexto de autenticación
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        
        # Validar y parsear JSON
        try:
            from process_ai_core.domains.processes.builder import ProcessBuilder
            builder = ProcessBuilder()
            process_doc = builder.parse_document(content_json)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"JSON inválido: {str(e)}"
            )
        
        # Renderizar Markdown
        from process_ai_core.domains.processes.renderer import ProcessRenderer
        from process_ai_core.domains.processes.profiles import get_profile
        from process_ai_core.db.models import Process
        
        process = session.query(Process).filter_by(id=document_id).first()
        if not process:
            raise HTTPException(
                status_code=404,
                detail=f"Process {document_id} no encontrado"
            )
        
        profile = get_profile(process.audience or "operativo")
        renderer = ProcessRenderer()
        
        markdown = renderer.render_markdown(
            document=process_doc,
            profile=profile,
            images_by_step={},
            evidence_images=[],
        )
        
        # Actualizar versión DRAFT (mismo version_id en PUTs seguidos)
        draft_version.content_json = content_json
        draft_version.content_markdown = markdown
        draft_version.content_type = "manual_edit"
        
        # Crear audit log
        from process_ai_core.db.helpers import create_audit_log
        create_audit_log(
            session=session,
            document_id=document_id,
            user_id=None,  # TODO: obtener del contexto de autenticación
            action="version.draft_updated",
            entity_type="version",
            entity_id=draft_version.id,
            metadata_json=json.dumps({
                "version_number": draft_version.version_number,
            }),
        )
        
        session.commit()
        
        return {
            "version_id": draft_version.id,
            "version_number": draft_version.version_number,
            "version_status": draft_version.version_status,
            "content_type": draft_version.content_type,
            "created_at": draft_version.created_at.isoformat(),
        }


_LATEX_ARTIFACT_RE = re.compile(
    r"\\(?:FloatBarrier|clearpage|newpage|pagebreak|vspace\{[^}]*\}|hspace\{[^}]*\}|noindent|medskip|bigskip|smallskip)",
    re.IGNORECASE,
)


def _strip_latex_artifacts(text: str) -> str:
    """Elimina comandos LaTeX que no tienen equivalente HTML y quedarían como texto basura."""
    return _LATEX_ARTIFACT_RE.sub("", text)


def _markdown_to_html(md: str) -> str:
    """Convierte Markdown a HTML para precarga del editor manual."""
    # Limpiar artefactos LaTeX antes de convertir (no tienen sentido en HTML)
    md = _strip_latex_artifacts(md or "")
    try:
        import markdown
        return markdown.markdown(md, extensions=["extra", "nl2br", "tables", "sane_lists"])
    except Exception:
        import html as html_mod
        return "".join(f"<p>{html_mod.escape(line)}</p>" for line in md.splitlines())


def _rewrite_img_src_to_absolute(html_content: str, run_id: Optional[str], api_base: str) -> str:
    """
    Reescribe rutas de imágenes relativas en HTML a URLs absolutas.
    - src="assets/..." → {api_base}/api/v1/artifacts/{run_id}/assets/...
    - src="/api/v1/..." o src="http..." → sin cambios
    """
    if not html_content:
        return html_content

    def replace_src(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("http") or src.startswith("/api/v1/"):
            return m.group(0)
        if run_id and (src.startswith("assets/") or src.startswith("./assets/")):
            clean = src.lstrip("./")
            return f'src="{api_base}/api/v1/artifacts/{run_id}/{clean}"'
        return m.group(0)

    return re.sub(r'src="([^"]+)"', replace_src, html_content)


_HTML_BLOCK_RE = re.compile(
    r"<(?:h[1-6]|p|ul|ol|li|strong|em|b|i|table|img|div|span|a|br|hr|blockquote|pre|code)\b",
    re.IGNORECASE,
)


def _is_valid_html(text: str) -> bool:
    """
    Devuelve True si el texto contiene etiquetas HTML de bloque o inline.
    HTML generado por python-markdown o Tiptap siempre las tiene.
    Markdown crudo nunca las tiene.
    """
    return bool(_HTML_BLOCK_RE.search(text or ""))


def _looks_like_markdown(text: str) -> bool:
    """
    Devuelve True si el texto NO contiene etiquetas HTML válidas
    (es decir, probablemente es markdown crudo o texto plano).
    Se mantiene por compatibilidad; internamente usa _is_valid_html.
    """
    return not _is_valid_html(text)


@router.get("/{document_id}/editable")
async def get_editable_content(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Obtiene el contenido editable (HTML) de la versión DRAFT para edición manual.
    Si no hay DRAFT, se obtiene o crea uno. Si no hay content_html, se genera desde content_markdown.
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        if doc.document_type != "process":
            raise HTTPException(status_code=400, detail="Solo documentos de tipo process soportan edición manual")

        from process_ai_core.db.helpers import check_version_immutable
        is_immutable, reason = check_version_immutable(session, document_id)
        if is_immutable:
            raise HTTPException(status_code=400, detail=reason)

        draft = get_editable_version(session, document_id)
        if draft is None:
            draft = get_or_create_draft(
                session=session,
                document_id=document_id,
                source_version_id=None,
                user_id=user_id,
            )

        html_content = getattr(draft, "content_html", None) if draft else None
        # Si content_html parece markdown crudo (guardado por error en versiones anteriores),
        # descartarlo y regenerar desde content_markdown para no mostrar basura en el editor.
        if html_content and _looks_like_markdown(html_content):
            logger.warning(
                "content_html de versión %s parece markdown crudo; regenerando desde content_markdown",
                draft.id if draft else "?",
            )
            html_content = None
        if not html_content and draft and draft.content_markdown:
            # Solo convertir para mostrar en el editor; NO persistir en BD.
            # La BD se actualiza únicamente cuando el usuario guarda (PUT /editable).
            html_content = _markdown_to_html(draft.content_markdown)
        if not html_content:
            html_content = "<p></p>"

        # Limpiar artefactos LaTeX que puedan haber quedado en content_html de versiones anteriores
        html_content = _strip_latex_artifacts(html_content)

        # Reescribir rutas relativas de imágenes a URLs absolutas para que el editor las muestre
        settings = get_settings()
        api_base = settings.api_base_url.rstrip("/")
        draft_run_id = getattr(draft, "run_id", None) if draft else None
        html_content = _rewrite_img_src_to_absolute(html_content, draft_run_id, api_base)

        return {
            "version_id": draft.id,
            "version_number": draft.version_number,
            "html": html_content,
            "run_id": draft_run_id,
            "updated_at": draft.created_at.isoformat(),
        }


def _generate_draft_pdf_background(
    content_html: str,
    run_id: Optional[str],
    document_id: str,
    output_dir: str,
    api_base: str,
) -> None:
    """Genera y guarda draft_preview.pdf en segundo plano. No lanza excepciones."""
    try:
        html_for_pdf = _rewrite_img_src_to_absolute(content_html, run_id, api_base)
        pdf_dir: Optional[Path] = None
        if run_id:
            candidate = Path(output_dir) / run_id
            if candidate.exists():
                pdf_dir = candidate
        if pdf_dir is None:
            pdf_dir = Path(output_dir) / "documents" / document_id
            pdf_dir.mkdir(parents=True, exist_ok=True)
        export_pdf_from_content(
            content=html_for_pdf,
            format="html",
            run_dir=pdf_dir,
            pdf_name="draft_preview.pdf",
            base_url=api_base,
        )
        logger.info("PDF del borrador guardado en %s/draft_preview.pdf", pdf_dir)
        tmp_html = pdf_dir / "content.html"
        if tmp_html.exists():
            try:
                tmp_html.unlink()
            except OSError:
                pass
    except Exception as exc:
        logger.warning("No se pudo guardar el PDF del borrador en background: %s", exc)


@router.put("/{document_id}/editable")
async def save_editable_content(
    document_id: str,
    background_tasks: BackgroundTasks,
    content_html: str = Body(..., embed=True),
    user_id: str = Depends(get_current_user_id),
):
    """
    Guarda el HTML del editor manual en la versión DRAFT (borrador).
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        if doc.document_type != "process":
            raise HTTPException(status_code=400, detail="Solo documentos de tipo process")

        from process_ai_core.db.helpers import check_version_immutable
        is_immutable, reason = check_version_immutable(session, document_id)
        if is_immutable:
            raise HTTPException(status_code=400, detail=reason)

        draft = get_editable_version(session, document_id)
        if draft is None:
            draft = get_or_create_draft(
                session=session,
                document_id=document_id,
                source_version_id=None,
                user_id=user_id,
            )

        # Validación defensiva: rechazar si el contenido parece markdown crudo
        if _looks_like_markdown(content_html):
            logger.warning(
                "PUT /editable recibió contenido que parece markdown, no HTML. document_id=%s",
                document_id,
            )
            raise HTTPException(
                status_code=400,
                detail="Se esperaba HTML; el contenido parece markdown o texto crudo. Guarda desde el editor visual.",
            )

        draft.content_html = content_html
        draft.content_type = "manual_edit"
        draft_run_id = getattr(draft, "run_id", None)
        draft_id = draft.id
        draft_version_number = draft.version_number
        create_audit_log(
            session=session,
            document_id=document_id,
            user_id=user_id,
            action="manual_edit_saved",
            entity_type="version",
            entity_id=draft_id,
            metadata_json=json.dumps({"version_number": draft_version_number}),
        )
        session.commit()
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()

        # Generar PDF en segundo plano para no bloquear la respuesta
        settings = get_settings()
        background_tasks.add_task(
            _generate_draft_pdf_background,
            content_html=content_html,
            run_id=draft_run_id,
            document_id=document_id,
            output_dir=settings.output_dir,
            api_base=settings.api_base_url.rstrip("/"),
        )

        return {
            "version_id": draft_id,
            "version_number": draft_version_number,
            "updated_at": now_iso,
        }


@router.post("/{document_id}/upload-editor-image")
async def upload_editor_image(
    document_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Sube una imagen para el editor manual. Guarda en output/editor-uploads/{document_id}/.
    Devuelve la URL pública para insertar en el editor.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de imagen")

    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

    settings = get_settings()
    uploads_dir = Path(settings.output_dir) / "editor-uploads" / document_id
    uploads_dir.mkdir(parents=True, exist_ok=True)

    import uuid
    ext = Path(file.filename or "image").suffix or ".png"
    if ext.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        ext = ".png"
    name = f"{uuid.uuid4().hex}{ext}"
    path = uploads_dir / name

    try:
        contents = await file.read()
        path.write_bytes(contents)
    except Exception as e:
        logger.exception("Error guardando imagen del editor")
        raise HTTPException(status_code=500, detail="Error al guardar la imagen") from e

    url = f"/api/v1/documents/{document_id}/editor-images/{name}"
    return {"url": url}


@router.get("/{document_id}/editor-images/{filename}")
async def get_editor_image(document_id: str, filename: str):
    """Sirve una imagen subida por el editor manual."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")
    settings = get_settings()
    base = Path(settings.output_dir) / "editor-uploads" / document_id
    file_path = base / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    try:
        file_path.resolve().relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    from fastapi.responses import FileResponse
    return FileResponse(path=str(file_path), filename=filename)


@router.post("/{document_id}/patch")
async def patch_document_with_ai(
    document_id: str,
    observations: str = Body(..., embed=True),
    run_id: str | None = Body(None, embed=True),
    user_id: str = Depends(get_current_user_id),
):
    """
    Aplica un patch por IA usando observaciones de validación.
    
    Toma el documento actual (última versión aprobada o último run) y aplica
    las correcciones indicadas en las observaciones usando el LLM.
    
    Args:
        document_id: ID del documento
        observations: Observaciones del validador con correcciones a aplicar
        run_id: ID del run a corregir (opcional, si no se especifica usa el último run)
    
    Returns:
        ProcessRunResponse con el nuevo run_id y artifacts
    """
    try:
        logger.info(f"Patch por IA iniciado para documento {document_id}, run_id={run_id}")
        
        with get_db_session() as session:
            doc = session.query(Document).filter_by(id=document_id).first()
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Documento {document_id} no encontrado"
                )
            
            if doc.document_type != "process":
                raise HTTPException(
                    status_code=400,
                    detail="Este endpoint solo funciona para documentos de tipo 'process'"
                )
            
            # Obtener el documento actual para corregir
            # Prioridad: último run > última versión aprobada
            from process_ai_core.db.models import Process, Run, DocumentVersion
            
            process = session.query(Process).filter_by(id=document_id).first()
            if not process:
                raise HTTPException(
                    status_code=404,
                    detail=f"Process {document_id} no encontrado"
                )
            
            # Guardar valores necesarios antes de salir del contexto
            process_audience = process.audience or "operativo"
            document_name = doc.name
            logger.info(f"Documento encontrado: {document_name}, audience: {process_audience}")
            
            # Determinar qué documento usar como base
            base_json = None
            base_markdown = None
            
            if run_id:
                # Usar el run específico
                run = session.query(Run).filter_by(id=run_id, document_id=document_id).first()
                if not run:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Run {run_id} no encontrado"
                    )
                
                from process_ai_core.config import get_settings
                from pathlib import Path
                settings = get_settings()
                run_dir = Path(settings.output_dir) / run_id
                json_path = run_dir / "process.json"
                
                if not json_path.exists():
                    raise HTTPException(
                        status_code=404,
                        detail=f"JSON del run {run_id} no encontrado"
                    )
                
                base_json = json_path.read_text(encoding="utf-8")
            else:
                # Usar último run o última versión aprobada
                last_run = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).first()
                
                if last_run:
                    from process_ai_core.config import get_settings
                    from pathlib import Path
                    settings = get_settings()
                    run_dir = Path(settings.output_dir) / last_run.id
                    json_path = run_dir / "process.json"
                    
                    if json_path.exists():
                        base_json = json_path.read_text(encoding="utf-8")
                        run_id = last_run.id
                else:
                    # Usar última versión aprobada
                    last_version = (
                        session.query(DocumentVersion)
                        .filter_by(document_id=document_id, is_current=True)
                        .first()
                    )
                    
                    if last_version:
                        base_json = last_version.content_json
                        base_markdown = last_version.content_markdown
            
            if not base_json:
                logger.error(f"No se encontró documento base para {document_id}")
                raise HTTPException(
                    status_code=404,
                    detail="No se encontró documento base para corregir. Crea un run primero."
                )
            
            logger.info(f"Documento base encontrado, tamaño: {len(base_json)} caracteres")
        
        # Construir prompt para patch (fuera del contexto de sesión)
        patch_prompt = f"""=== DOCUMENTO ACTUAL ===
{base_json}

=== OBSERVACIONES DE VALIDACIÓN ===
{observations}

=== INSTRUCCIONES ===
Aplica las correcciones indicadas en las observaciones al documento actual.
Mantén la estructura JSON y solo modifica los campos necesarios según las observaciones.
Responde SOLO con el JSON corregido, sin texto adicional.
"""
        
        logger.info("Llamando al LLM para generar documento corregido...")
        
        # Llamar al LLM para generar el documento corregido
        from process_ai_core.llm_client import generate_document_json
        from process_ai_core.domains.processes.builder import ProcessBuilder
        
        builder = ProcessBuilder()
        system_prompt = builder.get_system_prompt()
        
        try:
            corrected_json = generate_document_json(
                prompt=patch_prompt,
                system_prompt=system_prompt,
            )
            logger.info("Documento corregido generado exitosamente")
        except Exception as e:
            logger.error(f"Error al generar documento corregido: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error al generar documento corregido: {str(e)}"
            )
        
        # Parsear y renderizar el documento corregido
        try:
            process_doc = builder.parse_document(corrected_json)
            logger.info("JSON parseado exitosamente")
        except Exception as e:
            logger.error(f"Error al parsear JSON corregido: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error al parsear JSON corregido: {str(e)}"
            )
        
        from process_ai_core.domains.processes.renderer import ProcessRenderer
        from process_ai_core.domains.processes.profiles import get_profile
        from process_ai_core.db.helpers import create_run, create_artifact, update_document_status
        from process_ai_core.config import get_settings
        from process_ai_core.export import export_pdf
        import uuid
        import shutil
        
        # Generar run_id antes de crear en BD
        new_run_id = str(uuid.uuid4())
        settings = get_settings()
        new_run_dir = Path(settings.output_dir) / new_run_id
        new_run_dir.mkdir(parents=True, exist_ok=True)
        
        # Obtener imágenes del run original si existe
        images_by_step = {}
        evidence_images = []
        
        if run_id:
            original_run_dir = Path(settings.output_dir) / run_id
            original_assets_dir = original_run_dir / "assets"
            
            if original_assets_dir.exists():
                logger.info(f"Copiando imágenes del run original {run_id}...")
                # Copiar directorio de assets completo al nuevo run
                new_assets_dir = new_run_dir / "assets"
                if original_assets_dir.exists():
                    shutil.copytree(original_assets_dir, new_assets_dir, dirs_exist_ok=True)
                    logger.info(f"Imágenes copiadas a {new_assets_dir}")
                
                # Intentar leer el resultado del run original para obtener metadatos de imágenes
                # Si no está disponible, al menos las imágenes físicas están copiadas
                try:
                    # Buscar imágenes en el directorio copiado
                    evidence_dir = new_assets_dir / "evidence"
                    if evidence_dir.exists():
                        for img_file in evidence_dir.glob("*"):
                            if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                                rel_path = f"assets/evidence/{img_file.name}"
                                evidence_images.append({
                                    "path": rel_path,
                                    "title": img_file.stem
                                })
                    
                    # Buscar imágenes por paso (estructura: assets/step_N/...)
                    for step_dir in new_assets_dir.glob("step_*"):
                        if step_dir.is_dir():
                            try:
                                step_num = int(step_dir.name.split("_")[1])
                                step_images = []
                                for img_file in step_dir.glob("*"):
                                    if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                                        rel_path = f"assets/{step_dir.name}/{img_file.name}"
                                        step_images.append({
                                            "path": rel_path,
                                            "title": img_file.stem
                                        })
                                if step_images:
                                    images_by_step[step_num] = step_images
                            except (ValueError, IndexError):
                                continue
                except Exception as e:
                    logger.warning(f"No se pudieron leer metadatos de imágenes del run original: {e}")
                    # Las imágenes están copiadas, pero no tenemos metadatos
                    # El renderer puede funcionar sin metadatos si las imágenes están en las rutas correctas
        
        profile = get_profile(process_audience)
        renderer = ProcessRenderer()
        
        logger.info(f"Renderizando markdown con {len(images_by_step)} pasos con imágenes y {len(evidence_images)} imágenes de evidencia...")
        markdown = renderer.render_markdown(
            document=process_doc,
            profile=profile,
            images_by_step=images_by_step,
            evidence_images=evidence_images,
            output_base=new_run_dir,
        )
        
        logger.info("Creando nuevo run...")
        
        # Guardar artifacts en disco primero
        settings = get_settings()
        output_dir = Path(settings.output_dir) / new_run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        json_path = output_dir / "process.json"
        md_path = output_dir / "process.md"
        
        json_path.write_text(corrected_json, encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        
        logger.info(f"Artifacts guardados en {output_dir}")
        
        # Generar PDF
        pdf_generated = False
        try:
            export_pdf(run_dir=output_dir, md_path=md_path, pdf_name="process.pdf")
            pdf_generated = True
            logger.info("PDF generado exitosamente")
        except Exception as pdf_error:
            logger.warning(f"Error al generar PDF (opcional): {pdf_error}")
        
        # Crear Run y Artifacts en BD (transacción atómica)
        with get_db_session() as session:
            from datetime import datetime, UTC
            from process_ai_core.db.models import DocumentVersion, Validation
            # Bloquear solo si existe IN_REVIEW (no por DRAFT)
            in_review = get_in_review_version(session, document_id)
            doc = session.query(Document).filter_by(id=document_id).first()
            # Si el documento ya está "rejected" pero hay IN_REVIEW, es inconsistencia (ej. rechazo no persistido): reconciliar y seguir
            if doc and doc.status == "rejected" and in_review:
                logger.warning(
                    f"Reconciliando inconsistencia: documento {document_id} está rejected pero versión {in_review.id} sigue IN_REVIEW; marcando como REJECTED para permitir patch."
                )
                in_review.version_status = "REJECTED"
                in_review.rejected_at = datetime.now(UTC)
                if in_review.validation_id:
                    val = session.query(Validation).filter_by(id=in_review.validation_id).first()
                    if val and val.status == "pending":
                        val.status = "rejected"
                        val.completed_at = datetime.now(UTC)
                in_review = None  # permitir seguir con el patch
            if in_review:
                raise HTTPException(
                    status_code=409,
                    detail="Ya hay una versión pendiente de validación. Aprobá o rechazá esa versión antes de aplicar un nuevo patch."
                )
            
            new_run = create_run(
                session=session,
                document_id=document_id,
                document_type="process",
                profile=process_audience,
                run_id=new_run_id,  # Usar el ID pre-generado
            )
            session.flush()
            
            # Crear artifacts en BD
            create_artifact(
                session=session,
                run_id=new_run_id,
                artifact_type="json",
                file_path=f"output/{new_run_id}/process.json",
            )
            create_artifact(
                session=session,
                run_id=new_run_id,
                artifact_type="md",
                file_path=f"output/{new_run_id}/process.md",
            )
            if pdf_generated:
                create_artifact(
                    session=session,
                    run_id=new_run_id,
                    artifact_type="pdf",
                    file_path=f"output/{new_run_id}/process.pdf",
                )
            
            try:
                # Leer el contenido generado del disco
                json_path = output_dir / "process.json"
                md_path = output_dir / "process.md"
                json_content = json_path.read_text(encoding="utf-8")
                markdown_content = md_path.read_text(encoding="utf-8")
                
                # Resolver DRAFT: reutilizar existente o crear uno
                draft = get_editable_version(session, document_id)
                draft_was_created = False
                if draft is None:
                    # Selección source_version_id: REJECTED más reciente > APPROVED vigente > None
                    rejected = (
                        session.query(DocumentVersion)
                        .filter_by(document_id=document_id, version_status="REJECTED")
                        .order_by(DocumentVersion.created_at.desc())
                        .first()
                    )
                    approved = (
                        session.query(DocumentVersion)
                        .filter_by(document_id=document_id, version_status="APPROVED", is_current=True)
                        .first()
                    )
                    source_version_id = rejected.id if rejected else (approved.id if approved else None)
                    draft = get_or_create_draft(
                        session=session,
                        document_id=document_id,
                        source_version_id=source_version_id,
                        user_id=user_id,
                    )
                    draft_was_created = True
                
                # Aplicar patch al DRAFT (creado o reutilizado)
                draft.run_id = new_run_id
                draft.content_json = json_content
                draft.content_markdown = markdown_content
                draft.content_type = "ai_patch"
                session.flush()
                
                # Audit log
                create_audit_log(
                    session=session,
                    document_id=document_id,
                    user_id=user_id,
                    action="version.draft_created_by_ai_patch" if draft_was_created else "version.draft_updated_by_ai_patch",
                    entity_type="version",
                    entity_id=draft.id,
                    metadata_json=json.dumps({
                        "run_id": new_run_id,
                        "draft_version_id": draft.id,
                        "draft_version_number": draft.version_number,
                        "source_version_id": draft.supersedes_version_id,
                        "observations_preview": (observations[:200] + "...") if observations and len(observations) > 200 else (observations or None),
                    }),
                )
                
                # Dejar documento en draft: el creador envía a revisión cuando esté conforme
                update_document_status(
                    session=session,
                    document_id=document_id,
                    status="draft",
                )
                
                session.commit()
            except HTTPException:
                session.rollback()
                raise
            except Exception as e:
                logger.error(f"Error al crear/actualizar versión en patch: {e}", exc_info=True)
                session.rollback()
                try:
                    update_document_status(
                        session=session,
                        document_id=document_id,
                        status="draft",
                    )
                    session.commit()
                except Exception as update_err:
                    logger.warning(f"No se pudo actualizar estado del documento tras fallo de patch: {update_err}")
                    session.rollback()
                raise
            
            logger.info(f"Run {new_run_id} creado exitosamente")
            # Commit se hace automáticamente al salir del with
        
        # Construir respuesta
        artifacts = {
            "json": f"/api/v1/artifacts/{new_run_id}/process.json",
            "markdown": f"/api/v1/artifacts/{new_run_id}/process.md",
        }
        if pdf_generated:
            artifacts["pdf"] = f"/api/v1/artifacts/{new_run_id}/process.pdf"
        
        logger.info(f"Patch completado exitosamente, run_id: {new_run_id}")
        
        from ..models.requests import ProcessRunResponse
        return ProcessRunResponse(
            run_id=new_run_id,
            process_name=document_name,
            status="completed",
            artifacts=artifacts,
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error inesperado en patch_document_with_ai: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al aplicar patch: {str(e)}"
        ) from e


@router.get("/{document_id}/versions")
async def get_document_versions(document_id: str):
    """
    Obtiene todas las versiones de un documento.
    
    Args:
        document_id: ID del documento
    
    Returns:
        Lista de versiones ordenadas por número (más recientes primero)
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        from process_ai_core.db.models import DocumentVersion
        
        versions = (
            session.query(DocumentVersion)
            .filter_by(document_id=document_id)
            .order_by(DocumentVersion.version_number.desc())
            .all()
        )
        
        return [
            {
                "id": v.id,
                "version_number": v.version_number,
                "version_status": v.version_status,
                "content_type": v.content_type,
                "run_id": v.run_id,
                "validation_id": v.validation_id,
                "approved_at": v.approved_at.isoformat() if v.approved_at else None,
                "approved_by": v.approved_by,
                "rejected_at": v.rejected_at.isoformat() if v.rejected_at else None,
                "rejected_by": v.rejected_by,
                "is_current": v.is_current,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]


@router.get("/{document_id}/versions/{version_id}/preview-pdf")
async def get_version_preview_pdf(document_id: str, version_id: str):
    """
    Genera y devuelve el PDF de una versión usando la fuente de verdad
    (content_html si existe, si no content_markdown).
    Si la versión tiene run_id, usa el mismo directorio del run (con assets/)
    para generar el PDF igual que el original; si no, usa un temp dir.
    No modifica process.pdf ni artefactos del run.
    """
    settings = get_settings()
    api_base = settings.api_base_url.rstrip("/")
    with get_db_session() as session:
        version = (
            session.query(DocumentVersion)
            .filter_by(id=version_id, document_id=document_id)
            .first()
        )
        if not version:
            raise HTTPException(
                status_code=404,
                detail="Versión no encontrada o no pertenece al documento",
            )
        try:
            content, fmt = get_export_content(version)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        version_run_id = version.run_id
        version_status = version.version_status

    # Servir draft_preview.pdf desde disco si existe.
    # Aplica a DRAFT, IN_REVIEW y APPROVED: el contenido no cambia al transicionar entre estos estados,
    # y generar on-demand bloquea el event loop (Pandoc no puede bajar imágenes del mismo servidor).
    draft_pdf_path: Optional[Path] = None
    if version_status in ("DRAFT", "IN_REVIEW", "APPROVED"):
        if version_run_id:
            candidate = Path(settings.output_dir) / version_run_id / "draft_preview.pdf"
            if candidate.exists():
                draft_pdf_path = candidate
        if draft_pdf_path is None:
            candidate = Path(settings.output_dir) / "documents" / document_id / "draft_preview.pdf"
            if candidate.exists():
                draft_pdf_path = candidate

    if draft_pdf_path is not None:
        logger.info("Sirviendo draft_preview.pdf desde disco: %s", draft_pdf_path)
        return Response(
            content=draft_pdf_path.read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'inline; filename="draft_preview.pdf"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    # Post-procesar HTML: limpiar artefactos LaTeX y reescribir URLs de imágenes
    if fmt == "html":
        content = _strip_latex_artifacts(content)
        content = _rewrite_img_src_to_absolute(content, version_run_id, api_base)

    # Mismo directorio que el original cuando la versión tiene run_id (assets/, etc.)
    run_dir = None
    if version_run_id:
        run_dir = Path(settings.output_dir) / version_run_id
        if not run_dir.exists():
            run_dir = None
    if run_dir is None:
        run_dir = Path(tempfile.mkdtemp())

    # Ejecutar Pandoc en un thread pool para no bloquear el event loop.
    # Si Pandoc corre en el hilo principal (sync), el event loop se congela y
    # el servidor no puede responder los pedidos de imágenes que hace Pandoc → deadlock.
    import asyncio
    import concurrent.futures

    _run_dir_for_cleanup = run_dir
    _is_temp_dir = not version_run_id

    def _generate_sync() -> bytes:
        pdf_path = export_pdf_from_content(
            content=content,
            format=fmt,
            run_dir=_run_dir_for_cleanup,
            pdf_name="preview.pdf",
            base_url=api_base if fmt == "html" else None,
        )
        pdf_bytes = pdf_path.read_bytes()
        content_file = _run_dir_for_cleanup / ("content.html" if fmt == "html" else "content.md")
        if content_file.exists():
            try:
                content_file.unlink()
            except OSError:
                pass
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except OSError:
                pass
        return pdf_bytes

    try:
        loop = asyncio.get_event_loop()
        pdf_bytes = await loop.run_in_executor(None, _generate_sync)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline; filename=\"preview.pdf\"",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except (FileNotFoundError, RuntimeError) as e:
        logger.warning("Error generando PDF de versión: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo generar el PDF: {e}",
        ) from e
    finally:
        if _is_temp_dir and _run_dir_for_cleanup:
            shutil.rmtree(_run_dir_for_cleanup, ignore_errors=True)


@router.get("/{document_id}/current-version")
async def get_current_document_version(document_id: str):
    """
    Obtiene la versión actual aprobada del documento.
    
    Esta es la "verdad" visible para operarios y para RAG.
    
    Args:
        document_id: ID del documento
    
    Returns:
        Versión actual con JSON y Markdown
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        from process_ai_core.db.models import DocumentVersion
        
        current_version = (
            session.query(DocumentVersion)
            .filter_by(document_id=document_id, is_current=True)
            .first()
        )
        
        if not current_version:
            raise HTTPException(
                status_code=404,
                detail=f"No hay versión aprobada para el documento {document_id}"
            )
        
        return {
            "id": current_version.id,
            "version_number": current_version.version_number,
            "content_type": current_version.content_type,
            "run_id": current_version.run_id,
            "content_json": current_version.content_json,
            "content_markdown": current_version.content_markdown,
            "approved_at": current_version.approved_at.isoformat(),
            "approved_by": current_version.approved_by,
            "created_at": current_version.created_at.isoformat(),
        }


@router.get("/{document_id}/audit-log")
async def get_document_audit_log(document_id: str):
    """
    Obtiene el historial completo de cambios (audit log) de un documento.
    
    Args:
        document_id: ID del documento
    
    Returns:
        Lista de registros de auditoría ordenados por fecha (más recientes primero)
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        from process_ai_core.db.models import AuditLog
        
        audit_logs = (
            session.query(AuditLog)
            .filter_by(document_id=document_id)
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        
        return [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "run_id": log.run_id,
                "user_id": log.user_id,
                "changes_json": log.changes_json,
                "metadata_json": log.metadata_json,
                "created_at": log.created_at.isoformat(),
            }
            for log in audit_logs
        ]


@router.post("/{document_id}/versions/{version_id}/submit")
async def submit_version_for_review_endpoint(
    document_id: str,
    version_id: str,
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Envía una versión DRAFT a revisión (cambia a IN_REVIEW y crea Validation).
    
    Solo usuarios con permisos para editar documentos pueden enviar a revisión.
    
    Args:
        document_id: ID del documento
        version_id: ID de la versión DRAFT a enviar
        user_id: ID del usuario que envía
        workspace_id: ID del workspace
    
    Returns:
        Versión actualizada y validación creada
    """
    with get_db_session() as session:
        # Verificar permisos
        from process_ai_core.db.permissions import has_permission
        
        if not has_permission(session, user_id, workspace_id, "documents.edit"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para enviar documentos a revisión"
            )
        
        # Verificar que el documento existe y pertenece al workspace
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
        
        # Verificar que la versión existe y pertenece al documento
        from process_ai_core.db.models import DocumentVersion
        version = session.query(DocumentVersion).filter_by(
            id=version_id,
            document_id=document_id
        ).first()
        
        if not version:
            raise HTTPException(
                status_code=404,
                detail=f"Versión {version_id} no encontrada para el documento {document_id}"
            )
        
        # Enviar a revisión
        try:
            updated_version, validation = submit_version_for_review(
                session=session,
                version_id=version_id,
                submitter_id=user_id,
            )
            session.commit()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        return {
            "message": "Versión enviada a revisión exitosamente",
            "version": {
                "id": updated_version.id,
                "version_number": updated_version.version_number,
                "version_status": updated_version.version_status,
                "validation_id": updated_version.validation_id,
            },
            "validation": {
                "id": validation.id,
                "status": validation.status,
                "document_id": validation.document_id,
                "created_at": validation.created_at.isoformat(),
            },
        }


@router.post("/{document_id}/versions/{version_id}/cancel-submission")
async def cancel_submission_endpoint(
    document_id: str,
    version_id: str,
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Cancela el envío a revisión y vuelve la versión a borrador.
    Solo el creador de la versión (quien la envió) puede cancelar.
    """
    with get_db_session() as session:
        from process_ai_core.db.permissions import has_permission

        if not has_permission(session, user_id, workspace_id, "documents.edit"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para editar documentos"
            )
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        if doc.workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Documento no pertenece a este workspace")
        try:
            updated_version = cancel_submission(
                session=session,
                document_id=document_id,
                version_id=version_id,
                user_id=user_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {
            "message": "Envío cancelado. El documento volvió a borrador.",
            "version": {
                "id": updated_version.id,
                "version_number": updated_version.version_number,
                "version_status": updated_version.version_status,
            },
        }


@router.post("/{document_id}/versions/{version_id}/clone")
async def clone_version_to_draft(
    document_id: str,
    version_id: str,
    user_id: str = Body(..., embed=True),
    workspace_id: str = Body(..., embed=True),
):
    """
    Crea un nuevo DRAFT clonando una versión APPROVED o REJECTED.
    
    Solo usuarios con permisos para editar documentos pueden clonar versiones.
    
    Args:
        document_id: ID del documento
        version_id: ID de la versión a clonar (debe ser APPROVED o REJECTED)
        user_id: ID del usuario que clona
        workspace_id: ID del workspace
    
    Returns:
        Nueva versión DRAFT creada
    """
    with get_db_session() as session:
        # Verificar permisos
        from process_ai_core.db.permissions import has_permission
        
        if not has_permission(session, user_id, workspace_id, "documents.edit"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para crear borradores"
            )
        
        # Verificar que el documento existe y pertenece al workspace
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
        
        # Verificar que la versión existe y pertenece al documento
        from process_ai_core.db.models import DocumentVersion
        source_version = session.query(DocumentVersion).filter_by(
            id=version_id,
            document_id=document_id
        ).first()
        
        if not source_version:
            raise HTTPException(
                status_code=404,
                detail=f"Versión {version_id} no encontrada para el documento {document_id}"
            )
        
        # Verificar que la versión es clonable (APPROVED o REJECTED)
        if source_version.version_status not in ("APPROVED", "REJECTED"):
            raise HTTPException(
                status_code=400,
                detail=f"No se puede clonar una versión con estado {source_version.version_status}. "
                       f"Solo se pueden clonar versiones APPROVED o REJECTED."
            )
        
        # Crear nuevo DRAFT desde la versión fuente
        try:
            draft_version = get_or_create_draft(
                session=session,
                document_id=document_id,
                source_version_id=version_id,
                user_id=user_id,
            )
            session.commit()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        return {
            "message": "Borrador creado exitosamente",
            "version": {
                "id": draft_version.id,
                "version_number": draft_version.version_number,
                "version_status": draft_version.version_status,
                "supersedes_version_id": draft_version.supersedes_version_id,
                "created_at": draft_version.created_at.isoformat(),
            },
        }

