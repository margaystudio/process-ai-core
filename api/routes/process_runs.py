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

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from process_ai_core.config import get_settings
from api.dependencies import get_current_user_id
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.domain_models import RawAsset
from process_ai_core.engine import run_process_pipeline
from process_ai_core.upload_validation import ALLOWED_UPLOAD_EXTENSIONS

from ..models.requests import ProcessMode, ProcessRunResponse
from ._branding import get_run_pdf_branding, get_workspace_pdf_branding
from ..artifact_signing import sign_artifact_url
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)

router = APIRouter(
    prefix="/api/v1/process-runs",
    tags=["process-runs"],
    dependencies=[Depends(sync_workspace_access)],
)

@router.post("", response_model=ProcessRunResponse)
async def create_process_run(
    process_name: str = Form(...),
    mode: ProcessMode = Form(ProcessMode.OPERATIVO),
    detail_level: str = Form(None),
    context_text: str = Form(None),
    description: str = Form(None),  # Opcional: si no se proporciona, la IA la inferirá
    folder_id: str = Form(...),  # Requerido
    document_type: str = Form("procedimiento"),  # Tipo documental del catálogo
    audio_files: List[UploadFile] = File(default=[]),
    video_files: List[UploadFile] = File(default=[]),
    image_files: List[UploadFile] = File(default=[]),
    text_files: List[UploadFile] = File(default=[]),
    audio_files_extracted_text: List[str] = Form(default=[]),
    video_files_extracted_text: List[str] = Form(default=[]),
    image_files_extracted_text: List[str] = Form(default=[]),
    text_files_extracted_text: List[str] = Form(default=[]),
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Crea una nueva corrida del pipeline de documentación.

    Recibe archivos multimedia (audio, video, imágenes, texto) y genera
    un documento de proceso estructurado (JSON, Markdown, PDF).

    Args:
        process_name: Nombre del proceso a documentar
        mode: Modo del documento (operativo o gestión)
        detail_level: Nivel de detalle (opcional)
        audio_files: Archivos de audio (.m4a, .mp3, .wav, .ogg, .opus, .aac - incluye audios de WhatsApp)
        video_files: Archivos de video (.mp4, .mov, .mkv)
        image_files: Archivos de imagen (.png, .jpg, .jpeg, .webp)
        text_files: Archivos de texto (.txt, .md, .pdf, .docx)

    Returns:
        ProcessRunResponse con run_id, status y paths a artefactos generados
    """
    settings = get_settings()
    workspace_id = resolve_tenant_workspace_id(ctx)

    # Validar permisos antes de procesar
    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.permissions import has_permission
    
    with get_db_session() as session:
        if not has_permission(session, user_id, workspace_id, "documents.create"):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para crear documentos"
            )
        # Validar que el folder exista y pertenezca al workspace ANTES de correr el
        # pipeline (evita desperdiciar una generación entera para fallar luego con un
        # FK violation 500 al insertar el documento). El front puede mandar un id viejo.
        if not folder_id:
            raise HTTPException(status_code=400, detail="folder_id es requerido")
        from process_ai_core.db.models import Folder
        folder = session.query(Folder).filter_by(id=folder_id).first()
        if folder is None or folder.workspace_id != workspace_id:
            raise HTTPException(
                status_code=400,
                detail="La carpeta seleccionada no existe o no pertenece a este espacio de trabajo. Refrescá la página y volvé a seleccionar la carpeta.",
            )
        from process_ai_core.db.permissions import can_create_in_folder
        if not can_create_in_folder(session, user_id, workspace_id, folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso para crear documentos en esta carpeta"
            )
        # Límite de almacenamiento del plan (no enforce si no hay suscripción/plan).
        from process_ai_core.db.helpers import enforce_storage_limit
        storage_error = enforce_storage_limit(session, workspace_id)
        if storage_error:
            raise HTTPException(status_code=402, detail=storage_error)

    # Validar que haya al menos un archivo
    total_files = (
        len(audio_files) + len(video_files) + len(image_files) + len(text_files)
    )
    if total_files == 0:
        raise HTTPException(
            status_code=400, detail="Se requiere al menos un archivo de entrada"
        )
    
    # Validar que folder_id esté presente
    if not folder_id:
        raise HTTPException(
            status_code=400, detail="folder_id es requerido"
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

        async def process_files(
            files: List[UploadFile],
            kind: str,
            prefix: str,
            extracted_texts: List[str] | None = None,
        ):
            """Procesa una lista de archivos y los agrega a raw_assets."""
            if not files:
                return

            overrides = extracted_texts or []

            for idx, upload_file in enumerate(files):
                ext = Path(upload_file.filename).suffix.lower() if upload_file.filename else ""
                allowed = ALLOWED_UPLOAD_EXTENSIONS[kind]
                if ext not in allowed:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Extensión no permitida para {kind}: '{ext or '(sin extensión)'}'. "
                            f"Permitidas: {', '.join(sorted(allowed))}"
                        ),
                    )

                counters[kind] += 1
                asset_id = f"{prefix}{counters[kind]}"

                # Guardar archivo en temp_dir
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

                metadata: dict[str, str] = {"titulo": titulo}
                if idx < len(overrides) and overrides[idx].strip():
                    metadata["extracted_text_override"] = overrides[idx].strip()

                raw_assets.append(
                    RawAsset(
                        id=asset_id,
                        kind=kind,  # type: ignore
                        path_or_url=str(temp_path),
                        metadata=metadata,
                    )
                )

        # Procesar cada tipo de archivo
        await process_files(audio_files, "audio", "aud", audio_files_extracted_text)
        await process_files(video_files, "video", "vid", video_files_extracted_text)
        await process_files(image_files, "image", "img", image_files_extracted_text)
        await process_files(text_files, "text", "txt", text_files_extracted_text)

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
            from ._run_paths import run_dir as _run_dir
            output_dir = _run_dir(workspace_id, run_id)
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
            
            # Si no se proporcionó descripción, inferirla del JSON generado
            inferred_description = description
            if not inferred_description or not inferred_description.strip():
                try:
                    import json
                    doc_json = json.loads(result["json_str"])
                    # Usar el campo "objetivo" del JSON como descripción
                    if "objetivo" in doc_json and doc_json["objetivo"]:
                        inferred_description = doc_json["objetivo"].strip()
                except Exception:
                    # Si falla el parsing, dejar vacío
                    inferred_description = ""

            # Generar PDF si se requiere
            pdf_generated = False
            try:
                from process_ai_core.export import export_pdf
                from process_ai_core.db.database import get_db_session

                with get_db_session() as session:
                    pdf_branding = get_workspace_pdf_branding(session, workspace_id)
                export_pdf(
                    run_dir=output_dir,
                    md_path=md_path,
                    pdf_name="process.pdf",
                    branding=pdf_branding,
                )
                pdf_generated = True
            except Exception as pdf_error:
                # PDF opcional, no fallamos si no se puede generar
                pass

            # Subir los artefactos del run (json/md/pdf + assets) a object storage
            # para que el endpoint de artefactos los sirva en prod (no-op en local).
            from process_ai_core.storage import sync_run_dir_to_storage
            sync_run_dir_to_storage(workspace_id, run_id, output_dir)

            # Construir URLs firmadas para los artefactos
            artifacts = {
                "json": sign_artifact_url(run_id, "process.json", workspace_id),
                "markdown": sign_artifact_url(run_id, "process.md", workspace_id),
            }
            if pdf_generated:
                artifacts["pdf"] = sign_artifact_url(run_id, "process.pdf", workspace_id)

            # SOLO AHORA crear Document, Run y Artifacts en BD (transacción atómica)
            # Si algo falla aquí, el pipeline ya se ejecutó exitosamente
            from process_ai_core.db.database import get_db_session
            from process_ai_core.db.helpers import (
                create_process_document,
                create_run,
                update_document_status,
            )
            
            with get_db_session() as db_session:
                # Crear Document (folder_id es requerido)
                # Usar descripción del usuario o la inferida del JSON
                final_description = inferred_description or ""
                document = create_process_document(
                    session=db_session,
                    workspace_id=workspace_id,
                    name=process_name,
                    description=final_description,
                    folder_id=folder_id,  # Requerido
                    audience=mode.value,
                    detail_level=detail_level or "",
                    context_text=context_text or "",
                    document_type=document_type or "procedimiento",
                )
                
                # Asegurar que el document.id esté disponible
                db_session.flush()
                document_id = document.id
                
                # Crear Run con el ID que ya usamos para el directorio
                run = create_run(
                    session=db_session,
                    document_id=document_id,
                    domain="process",
                    profile=mode.value,
                    run_id=run_id,  # Usar el ID que ya generamos
                )
                # Manifiesto de fuentes (metadata + sha256 + transcripción) para auditoría,
                # antes de que el temp dir con los originales se borre.
                from process_ai_core.input_manifest import build_input_manifest_json
                run.input_manifest_json = build_input_manifest_json(
                    raw_assets, result.get("enriched_assets"), uploaded_by=user_id
                )
                db_session.flush()

                # Los artefactos del run (json/md/pdf/assets) viven en object storage
                # bajo la clave {run_id}/...; no se trackean en una tabla.

                # Crear versión DRAFT desde el run generado y enviarla automáticamente a revisión
                try:
                    from process_ai_core.db.models import DocumentVersion
                    import json
                    import logging
                    logger = logging.getLogger(__name__)
                    
                    # Leer el contenido generado
                    json_path = output_dir / "process.json"
                    md_path = output_dir / "process.md"
                    
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

                    # Recalcular uso de storage del tenant (best-effort).
                    from process_ai_core.db.helpers import update_workspace_storage_usage
                    update_workspace_storage_usage(db_session, workspace_id)

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
                
                # Commit se hace automáticamente al salir del with si no hay errores
                # Si hay error, se hace rollback automáticamente

            return ProcessRunResponse(
                run_id=run_id,
                process_name=process_name,
                status="completed",
                artifacts=artifacts,
                document_id=document_id,
            )

        except Exception as e:
            # Si el pipeline falla, limpiar el directorio de salida si se creó
            from ._run_paths import run_dir as _run_dir
            output_dir = _run_dir(workspace_id, run_id)
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
    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.models import Run, Document
    from ._run_paths import run_dir as _run_dir

    # Resolver workspace del run (necesario para el dir tenant-scoped y la firma)
    workspace_id_for_signing: str | None = None
    with get_db_session() as session:
        run_obj = session.query(Run).filter_by(id=run_id).first()
        if run_obj and run_obj.document_id:
            doc_obj = session.query(Document).filter_by(id=run_obj.document_id).first()
            if doc_obj:
                workspace_id_for_signing = doc_obj.workspace_id

    if not workspace_id_for_signing:
        raise HTTPException(status_code=404, detail=f"Run {run_id} no encontrado")

    run_dir = _run_dir(workspace_id_for_signing, run_id)
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

        with get_db_session() as session:
            pdf_branding = get_run_pdf_branding(session, run_id)

        pdf_path = export_pdf(
            run_dir=run_dir,
            md_path=md_path,
            pdf_name="process.pdf",
            branding=pdf_branding,
        )

        from process_ai_core.storage import sync_run_dir_to_storage
        sync_run_dir_to_storage(workspace_id_for_signing, run_id, run_dir)

        pdf_url = sign_artifact_url(run_id, "process.pdf", workspace_id_for_signing)

        return {
            "run_id": run_id,
            "status": "completed",
            "pdf_url": pdf_url,
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

