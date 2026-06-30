"""
Runs de un documento: listado de runs y generación de una nueva versión
ejecutando el pipeline de proceso (subida de archivos + LLM + artefactos).
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Process, Run, Workspace
from process_ai_core.db.helpers import create_run
from process_ai_core.config import get_settings
from process_ai_core.domain_models import RawAsset
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.engine import run_process_pipeline
from process_ai_core.prompt_context import build_context_block
from process_ai_core.export import export_pdf
from process_ai_core.ingest import discover_raw_assets
from process_ai_core.upload_validation import ALLOWED_UPLOAD_EXTENSIONS

from api.models.requests import ProcessRunResponse
from api.routes._branding import get_workspace_pdf_branding
from api.routes._run_paths import run_dir as _run_dir
from api.artifact_signing import sign_artifact_url
from api.dependencies import get_current_user_id
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
)

from ._helpers import _assert_doc_in_active_workspace

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{document_id}/runs")
async def get_document_runs(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Obtiene todos los runs asociados a un documento.
    """
    from process_ai_core.db.models import Run
    from process_ai_core.storage import get_storage

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

        runs = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).all()

        doc_workspace_id = doc.workspace_id
        storage = get_storage()
        # Artefactos por convención: {run_id}/process.{json,md,pdf}. Se firman las
        # URLs de los que existan en storage (ya no hay tabla Artifact).
        artifact_files = {"json": "process.json", "md": "process.md", "pdf": "process.pdf"}
        result = []
        for run in runs:
            artifact_dict = {}
            for atype, filename in artifact_files.items():
                if storage.exists(f"{run.id}/{filename}"):
                    artifact_dict[atype] = sign_artifact_url(run.id, filename, doc_workspace_id)

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
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
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
        text_files: Archivos de texto nuevos (opcional; .txt, .md, .pdf, .docx)
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
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        from process_ai_core.db.permissions import can_create_in_folder
        if not can_create_in_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso para crear runs en la carpeta de este documento"
            )
        # Límite de almacenamiento del plan (no enforce si no hay suscripción/plan).
        from process_ai_core.db.helpers import enforce_storage_limit
        storage_error = enforce_storage_limit(session, doc.workspace_id)
        if storage_error:
            raise HTTPException(status_code=402, detail=storage_error)

        if doc.domain != "process":
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
            domain="process",
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
            last_run_dir = _run_dir(doc.workspace_id, last_run.id)

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
            output_dir = _run_dir(doc.workspace_id, run_id)
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
                export_pdf(
                    run_dir=output_dir,
                    md_path=md_path,
                    pdf_name="process.pdf",
                    branding=get_workspace_pdf_branding(session, doc.workspace_id),
                )
                pdf_generated = True
            except Exception as pdf_error:
                pass

            # Subir artefactos del run (json/md/pdf + assets) a object storage (no-op en local).
            from process_ai_core.storage import sync_run_dir_to_storage
            sync_run_dir_to_storage(doc.workspace_id, run_id, output_dir)

            # Construir URLs firmadas para los artefactos
            artifacts = {
                "json": sign_artifact_url(run_id, "process.json", doc.workspace_id),
                "markdown": sign_artifact_url(run_id, "process.md", doc.workspace_id),
            }
            if pdf_generated:
                artifacts["pdf"] = sign_artifact_url(run_id, "process.pdf", doc.workspace_id)

            # Crear versión IN_REVIEW automáticamente.
            # Los artefactos del run (json/md/pdf/assets) viven en object storage bajo
            # la clave {run_id}/...; no se trackean en una tabla (se sirven por convención).
            with get_db_session() as db_session:
                from process_ai_core.db.helpers import update_document_status, get_or_create_draft
                from process_ai_core.db.models import DocumentVersion, Run
                import uuid

                # Registrar el manifiesto de fuentes (metadata + sha256 + transcripción)
                # en el Run, para defensa de auditoría antes de que el temp se borre.
                from process_ai_core.input_manifest import build_input_manifest_json
                run_row = db_session.query(Run).filter_by(id=run_id).first()
                if run_row is not None:
                    run_row.input_manifest_json = build_input_manifest_json(
                        raw_assets, result.get("enriched_assets"), uploaded_by=user_id
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

                    # Recalcular uso de storage del tenant (best-effort).
                    from process_ai_core.db.helpers import update_workspace_storage_usage
                    update_workspace_storage_usage(db_session, doc.workspace_id)

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
