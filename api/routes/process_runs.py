"""
Endpoint para crear y consultar corridas del pipeline.

Este endpoint maneja:
- POST /api/v1/process-runs: Crear una nueva corrida
- GET /api/v1/process-runs/{run_id}: Consultar estado de una corrida
"""

import tempfile
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from process_ai_core.config import get_settings
from process_ai_core.document_profiles import get_profile
from process_ai_core.domain_models import RawAsset
from process_ai_core.engine import run_process_pipeline

from ..models.requests import ProcessMode, ProcessRunResponse

router = APIRouter(prefix="/api/v1/process-runs", tags=["process-runs"])


@router.post("", response_model=ProcessRunResponse)
async def create_process_run(
    process_name: str = Form(...),
    mode: ProcessMode = Form(ProcessMode.OPERATIVO),
    detail_level: str = Form(None),
    context_text: str = Form(None),
    folder_id: str = Form(...),  # Requerido
    workspace_id: str = Form(...),  # Requerido
    audio_files: List[UploadFile] = File(default=[]),
    video_files: List[UploadFile] = File(default=[]),
    image_files: List[UploadFile] = File(default=[]),
    text_files: List[UploadFile] = File(default=[]),
):
    """
    Crea una nueva corrida del pipeline de documentación.

    Recibe archivos multimedia (audio, video, imágenes, texto) y genera
    un documento de proceso estructurado (JSON, Markdown, PDF).

    Args:
        process_name: Nombre del proceso a documentar
        mode: Modo del documento (operativo o gestión)
        detail_level: Nivel de detalle (opcional)
        audio_files: Archivos de audio (.m4a, .mp3, .wav)
        video_files: Archivos de video (.mp4, .mov, .mkv)
        image_files: Archivos de imagen (.png, .jpg, .jpeg, .webp)
        text_files: Archivos de texto (.txt, .md)

    Returns:
        ProcessRunResponse con run_id, status y paths a artefactos generados
    """
    settings = get_settings()

    # Validar permisos antes de procesar
    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.permissions import has_permission
    
    with get_db_session() as session:
        # Verificar que el usuario tiene permiso para crear documentos
        # Nota: user_id debería venir del request, por ahora lo omitimos
        # TODO: Agregar user_id al request cuando tengamos autenticación
        # if not has_permission(session, user_id, workspace_id, "documents.create"):
        #     raise HTTPException(
        #         status_code=403,
        #         detail="No tiene permisos para crear documentos"
        #     )
        pass  # Temporalmente sin verificación hasta tener user_id en el request

    # Validar que haya al menos un archivo
    total_files = (
        len(audio_files) + len(video_files) + len(image_files) + len(text_files)
    )
    if total_files == 0:
        raise HTTPException(
            status_code=400, detail="Se requiere al menos un archivo de entrada"
        )
    
    # Validar que folder_id y workspace_id estén presentes
    if not folder_id:
        raise HTTPException(
            status_code=400, detail="folder_id es requerido"
        )
    if not workspace_id:
        raise HTTPException(
            status_code=400, detail="workspace_id es requerido"
        )
    
    # Generar run_id temporal para el procesamiento (antes de crear nada en BD)
    # Esto permite que el pipeline use el ID, y solo creamos en BD si tiene éxito
    run_id = str(uuid.uuid4())
    
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

        # Procesar cada tipo de archivo
        await process_files(audio_files, "audio", "aud")
        await process_files(video_files, "video", "vid")
        await process_files(image_files, "image", "img")
        await process_files(text_files, "text", "txt")

        # Construir contexto opcional
        context_block = None
        if detail_level or context_text or folder_id:
            lines = ["=== CONTEXTO Y PREFERENCIAS ==="]
            if detail_level:
                lines.append(f"- Nivel de detalle: {detail_level}")
            
            # Agregar información de la carpeta si existe
            if folder_id:
                from process_ai_core.db.database import get_db_session
                from process_ai_core.db.helpers import get_folder_by_id
                with get_db_session() as db_session:
                    folder = get_folder_by_id(db_session, folder_id)
                    if folder:
                        folder_path = folder.path or folder.name
                        lines.append(f"- Ubicación del proceso: {folder_path}. Considera el contexto de esta ubicación al generar el documento.")
            
            if context_text:
                lines.append("")
                lines.append("=== CONTEXTO ADICIONAL ===")
                lines.append(context_text)
            context_block = "\n".join(lines) + "\n\n"

        # Obtener perfil según modo
        profile = get_profile(mode.value)

        # Ejecutar pipeline PRIMERO (antes de crear nada en BD)
        # Si falla, no se crea nada en la base de datos
        try:
            output_dir = Path(settings.output_dir) / run_id
            output_dir.mkdir(parents=True, exist_ok=True)

            result = run_process_pipeline(
                process_name=process_name,
                raw_assets=raw_assets,
                profile=profile,
                context_block=context_block,
                output_base=output_dir,  # Las imágenes se copiarán a output_dir/assets/
            )

            # Persistir artefactos en disco
            json_path = output_dir / "process.json"
            md_path = output_dir / "process.md"

            json_path.write_text(result["json_str"], encoding="utf-8")
            md_path.write_text(result["markdown"], encoding="utf-8")

            # Generar PDF si se requiere
            pdf_generated = False
            try:
                from process_ai_core.export import export_pdf

                export_pdf(run_dir=output_dir, md_path=md_path, pdf_name="process.pdf")
                pdf_generated = True
            except Exception as pdf_error:
                # PDF opcional, no fallamos si no se puede generar
                pass

            # Construir paths relativos a los artefactos
            artifacts = {
                "json": f"/api/v1/artifacts/{run_id}/process.json",
                "markdown": f"/api/v1/artifacts/{run_id}/process.md",
            }
            if pdf_generated:
                artifacts["pdf"] = f"/api/v1/artifacts/{run_id}/process.pdf"

            # SOLO AHORA crear Document, Run y Artifacts en BD (transacción atómica)
            # Si algo falla aquí, el pipeline ya se ejecutó exitosamente
            from process_ai_core.db.database import get_db_session
            from process_ai_core.db.helpers import (
                create_process_document,
                create_run,
                create_artifact,
                update_document_status,
            )
            
            with get_db_session() as db_session:
                # Crear Document (folder_id es requerido)
                document = create_process_document(
                    session=db_session,
                    workspace_id=workspace_id,
                    name=process_name,
                    description="",
                    folder_id=folder_id,  # Requerido
                    audience=mode.value,
                    detail_level=detail_level or "",
                    context_text=context_text or "",
                )
                
                # Asegurar que el document.id esté disponible
                db_session.flush()
                document_id = document.id
                
                # Crear Run con el ID que ya usamos para el directorio
                run = create_run(
                    session=db_session,
                    document_id=document_id,
                    document_type="process",
                    profile=mode.value,
                    run_id=run_id,  # Usar el ID que ya generamos
                )
                db_session.flush()
                
                # Crear Artifacts
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
                
                # Commit se hace automáticamente al salir del with si no hay errores
                # Si hay error, se hace rollback automáticamente

            return ProcessRunResponse(
                run_id=run_id,
                process_name=process_name,
                status="completed",
                artifacts=artifacts,
            )

        except Exception as e:
            # Si el pipeline falla, limpiar el directorio de salida si se creó
            output_dir = Path(settings.output_dir) / run_id
            if output_dir.exists():
                import shutil
                try:
                    shutil.rmtree(output_dir)
                except Exception:
                    pass  # Ignorar errores al limpiar
            
            # Error interno del servidor: devolver 500
            # No se creó nada en BD porque el pipeline falló antes
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando el pipeline: {str(e)}",
            ) from e


@router.get("/{run_id}", response_model=ProcessRunResponse)
async def get_process_run(run_id: str):
    """
    Obtiene el estado y resultados de una corrida.

    Args:
        run_id: ID de la corrida

    Returns:
        ProcessRunResponse con el estado actual
    """
    # TODO: Implementar consulta desde DB o storage
    # Por ahora devolvemos un error 404
    raise HTTPException(status_code=404, detail=f"Run {run_id} no encontrada")


@router.post("/{run_id}/generate-pdf")
async def generate_pdf_from_run(run_id: str):
    """
    Genera un PDF desde un run existente (sin ejecutar el pipeline completo).

    Este endpoint es más rápido y económico que crear un nuevo run, ya que:
    - No requiere llamadas a OpenAI
    - Solo ejecuta Pandoc para convertir Markdown a PDF
    - Reutiliza el markdown y las imágenes ya generadas

    Args:
        run_id: ID de la corrida existente

    Returns:
        JSON con la URL del PDF generado

    Raises:
        404: Si el run_id no existe o no tiene markdown
        500: Si falla la generación del PDF
    """
    settings = get_settings()
    run_dir = Path(settings.output_dir) / run_id
    md_path = run_dir / "process.md"

    # Verificar que el run existe y tiene markdown
    if not run_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} no encontrado"
        )

    if not md_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Markdown no encontrado para run {run_id}. El run debe tener un process.md generado.",
        )

    # Generar PDF
    try:
        from process_ai_core.export import export_pdf

        pdf_path = export_pdf(
            run_dir=run_dir,
            md_path=md_path,
            pdf_name="process.pdf",
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "pdf_url": f"/api/v1/artifacts/{run_id}/process.pdf",
            "message": "PDF generado exitosamente",
        }

    except FileNotFoundError as e:
        # Pandoc no está instalado
        raise HTTPException(
            status_code=500,
            detail=f"Pandoc no está instalado o no está en PATH: {str(e)}",
        ) from e
    except RuntimeError as e:
        # Error al generar PDF (LaTeX, imágenes faltantes, etc.)
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar PDF: {str(e)}",
        ) from e
    except Exception as e:
        # Error inesperado
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al generar PDF: {str(e)}",
        ) from e

