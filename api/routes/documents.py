"""
Endpoint para gestionar documentos (procesos, recetas, etc.).

Este endpoint maneja:
- GET /api/v1/documents: Listar documentos de un workspace (opcionalmente filtrados por folder)
- GET /api/v1/documents/{document_id}: Obtener un documento por ID
- PUT /api/v1/documents/{document_id}: Actualizar un documento
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Query, Body
from typing import List, Optional
import tempfile
import shutil
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Process, Recipe, Workspace, Run, Artifact
from process_ai_core.db.helpers import create_run, create_artifact, delete_document
from process_ai_core.config import get_settings
from process_ai_core.domain_models import RawAsset
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.engine import run_process_pipeline
from process_ai_core.prompt_context import build_context_block
from process_ai_core.export import export_pdf
from process_ai_core.ingest import discover_raw_assets

from ..models.requests import DocumentResponse, DocumentUpdateRequest, ProcessRunResponse

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
        
        # Obtener documentos pendientes de validación
        documents = session.query(Document).filter_by(
            workspace_id=workspace_id,
            status="pending_validation",
        ).order_by(Document.created_at.asc()).all()
        
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
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
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
            
            # Persistir Artifacts en la base de datos
            with get_db_session() as db_session:
                from process_ai_core.db.helpers import update_document_status
                
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
                
                # Actualizar estado del documento a pending_validation
                update_document_status(
                    session=db_session,
                    document_id=document_id,
                    status="pending_validation",
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
    
    Permite editar directamente el JSON del documento y genera una nueva versión
    con content_type='manual_edit'. El documento vuelve a pending_validation.
    
    Args:
        document_id: ID del documento
        content_json: JSON del documento editado (ProcessDocument en formato JSON)
    
    Returns:
        DocumentVersion creada
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
        
        # Validar que el JSON sea válido y parseable
        try:
            from process_ai_core.domains.processes.builder import ProcessBuilder
            builder = ProcessBuilder()
            process_doc = builder.parse_document(content_json)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"JSON inválido: {str(e)}"
            )
        
        # Renderizar Markdown desde el documento editado
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
        
        # Renderizar markdown (sin imágenes por ahora, ya que es edición manual)
        markdown = renderer.render_markdown(
            document=process_doc,
            profile=profile,
            images_by_step={},
            evidence_images=[],
        )
        
        # Crear DocumentVersion con edición manual
        from process_ai_core.db.helpers import create_document_version, update_document_status, create_audit_log
        
        version = create_document_version(
            session=session,
            document_id=document_id,
            run_id=None,  # Edición manual, no hay run
            content_type="manual_edit",
            content_json=content_json,
            content_markdown=markdown,
        )
        
        # Actualizar estado a pending_validation
        update_document_status(
            session=session,
            document_id=document_id,
            status="pending_validation",
        )
        
        session.commit()
        
        return {
            "version_id": version.id,
            "version_number": version.version_number,
            "content_type": version.content_type,
            "created_at": version.created_at.isoformat(),
        }


@router.post("/{document_id}/patch")
async def patch_document_with_ai(
    document_id: str,
    observations: str = Body(..., embed=True),
    run_id: str | None = Body(None, embed=True),
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
        
        profile = get_profile(process_audience)
        renderer = ProcessRenderer()
        
        logger.info("Renderizando markdown...")
        markdown = renderer.render_markdown(
            document=process_doc,
            profile=profile,
            images_by_step={},
            evidence_images=[],
        )
        
        # Crear nuevo Run para el patch (nueva sesión)
        from process_ai_core.db.helpers import create_run, create_artifact, update_document_status
        from process_ai_core.config import get_settings
        from process_ai_core.export import export_pdf
        
        logger.info("Creando nuevo run...")
        
        # Generar run_id antes de crear en BD
        import uuid
        new_run_id = str(uuid.uuid4())
        
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
            
            # Actualizar estado a pending_validation
            update_document_status(
                session=session,
                document_id=document_id,
                status="pending_validation",
            )
            
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
                "content_type": v.content_type,
                "run_id": v.run_id,
                "approved_at": v.approved_at.isoformat(),
                "approved_by": v.approved_by,
                "is_current": v.is_current,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]


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

