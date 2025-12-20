"""
Endpoint para gestionar documentos (procesos, recetas, etc.).

Este endpoint maneja:
- GET /api/v1/documents: Listar documentos de un workspace (opcionalmente filtrados por folder)
- GET /api/v1/documents/{document_id}: Obtener un documento por ID
- PUT /api/v1/documents/{document_id}: Actualizar un documento
"""

from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from typing import List
import tempfile
import shutil
from pathlib import Path

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Process, Recipe, Workspace, Run, Artifact
from process_ai_core.db.helpers import create_run, create_artifact
from process_ai_core.config import get_settings
from process_ai_core.domain_models import RawAsset
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.engine import run_process_pipeline
from process_ai_core.prompt_context import build_context_block
from process_ai_core.export import export_pdf
from process_ai_core.ingest import discover_raw_assets

from ..models.requests import DocumentResponse, DocumentUpdateRequest, ProcessRunResponse

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(workspace_id: str = None, folder_id: str = None, document_type: str = "process"):
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

