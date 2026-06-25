"""
Edición de contenido de un documento:
- Edición manual del JSON/HTML del editor visual.
- Subida y servido de imágenes del editor.
- Patch asistido por IA a partir de observaciones de validación.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document
from process_ai_core.db.helpers import (
    create_audit_log,
    get_editable_version,
    get_in_review_version,
    get_or_create_draft,
)
from process_ai_core.config import get_settings
from process_ai_core.export import export_pdf_from_content

from api.routes._branding import get_workspace_pdf_branding
from api.routes._run_paths import run_dir as _run_dir
from api.artifact_signing import sign_artifact_url
from api.dependencies import get_current_user_id
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
)

from ._helpers import (
    _assert_doc_in_active_workspace,
    _looks_like_markdown,
    _markdown_to_html,
    _rewrite_img_src_to_absolute,
    _strip_latex_artifacts,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.put("/{document_id}/content")
async def update_document_content(
    document_id: str,
    content_json: str = Body(..., embed=True),
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
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
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        from process_ai_core.db.permissions import can_create_in_folder
        if not can_create_in_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(
                status_code=403,
                detail="No tiene acceso para editar documentos en esta carpeta"
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


@router.get("/{document_id}/editable")
async def get_editable_content(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Obtiene el contenido editable (HTML) de la versión DRAFT para edición manual.
    Si no hay DRAFT, se obtiene o crea uno. Si no hay content_html, se genera desde content_markdown.
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        from process_ai_core.db.permissions import can_view_folder
        if not can_view_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(status_code=403, detail="No tiene acceso a la carpeta de este documento")

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

        # Reescribir rutas relativas de imágenes a URLs absolutas (con token firmado)
        settings = get_settings()
        api_base = settings.api_base_url.rstrip("/")
        draft_run_id = getattr(draft, "run_id", None) if draft else None
        html_content = _rewrite_img_src_to_absolute(
            html_content, draft_run_id, api_base, workspace_id=doc.workspace_id
        )

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
    workspace_id: Optional[str],
    output_dir: str,
    api_base: str,
) -> None:
    """Genera y guarda draft_preview.pdf en segundo plano. No lanza excepciones."""
    try:
        html_for_pdf = _rewrite_img_src_to_absolute(content_html, run_id, api_base, workspace_id=workspace_id)
        branding = None
        with get_db_session() as session:
            branding = get_workspace_pdf_branding(session, workspace_id)
        pdf_dir: Optional[Path] = None
        if run_id and workspace_id:
            candidate = _run_dir(workspace_id, run_id)
            if candidate.exists():
                pdf_dir = candidate
        if pdf_dir is None:
            base = Path(output_dir)
            if workspace_id:
                base = base / "workspaces" / workspace_id
            pdf_dir = base / "documents" / document_id
            pdf_dir.mkdir(parents=True, exist_ok=True)

        # Evita servir un PDF viejo si esta generación falla.
        stale_pdf = pdf_dir / "draft_preview.pdf"
        if stale_pdf.exists():
            try:
                stale_pdf.unlink()
            except OSError:
                pass

        export_pdf_from_content(
            content=html_for_pdf,
            format="html",
            run_dir=pdf_dir,
            pdf_name="draft_preview.pdf",
            base_url=api_base,
            branding=branding,
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
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Guarda el HTML del editor manual en la versión DRAFT (borrador).
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        from process_ai_core.db.permissions import can_create_in_folder
        if not can_create_in_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(status_code=403, detail="No tiene acceso para editar documentos en esta carpeta")

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
            workspace_id=doc.workspace_id,
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
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Sube una imagen para el editor manual. Guarda en object storage bajo
    workspaces/{ws}/editor-uploads/{document_id}/ (tenant-scoped + durable en prod).
    Devuelve la URL pública para insertar en el editor.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de imagen")

    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

        from process_ai_core.db.permissions import can_create_in_folder
        if not can_create_in_folder(session, user_id, doc.workspace_id, doc.folder_id):
            raise HTTPException(status_code=403, detail="No tiene acceso para editar documentos en esta carpeta")
        doc_workspace_id = doc.workspace_id

    import uuid
    ext = Path(file.filename or "image").suffix or ".png"
    if ext.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        ext = ".png"
    name = f"{uuid.uuid4().hex}{ext}"

    from process_ai_core.storage import get_storage, workspace_prefix
    key = f"{workspace_prefix(doc_workspace_id)}/editor-uploads/{document_id}/{name}"
    try:
        contents = await file.read()
        get_storage().put(key, contents, content_type=file.content_type or "image/png")
    except Exception as e:
        logger.exception("Error guardando imagen del editor")
        raise HTTPException(status_code=500, detail="Error al guardar la imagen") from e

    url = f"/api/v1/documents/{document_id}/editor-images/{name}"
    return {"url": url}


@router.get("/{document_id}/editor-images/{filename}")
async def get_editor_image(document_id: str, filename: str):
    """Sirve una imagen subida por el editor manual (desde object storage)."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo no válido")

    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Imagen no encontrada")
        doc_workspace_id = doc.workspace_id

    from process_ai_core.storage import get_storage, workspace_prefix
    key = f"{workspace_prefix(doc_workspace_id)}/editor-uploads/{document_id}/{filename}"
    try:
        content = get_storage().get(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    from pathlib import PurePosixPath
    ctype_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp",
    }
    media_type = ctype_map.get(PurePosixPath(filename).suffix.lower(), "application/octet-stream")
    return Response(content=content, media_type=media_type, headers={
        "Content-Disposition": f'inline; filename="{filename}"',
    })


@router.post("/{document_id}/patch")
async def patch_document_with_ai(
    document_id: str,
    observations: str = Body(..., embed=True),
    run_id: str | None = Body(None, embed=True),
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
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
            _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

            from process_ai_core.db.permissions import can_create_in_folder
            if not can_create_in_folder(session, user_id, doc.workspace_id, doc.folder_id):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene acceso para modificar documentos en esta carpeta"
                )
            # Límite de almacenamiento del plan (no enforce si no hay suscripción/plan).
            from process_ai_core.db.helpers import enforce_storage_limit
            storage_error = enforce_storage_limit(session, doc.workspace_id)
            if storage_error:
                raise HTTPException(status_code=402, detail=storage_error)

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
            patch_workspace_id = doc.workspace_id
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

                run_dir = _run_dir(patch_workspace_id, run_id)
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
                    run_dir = _run_dir(patch_workspace_id, last_run.id)
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

        # Llamar al LLM para generar el documento corregido. El helper valida la
        # estructura y reintenta una vez si el modelo devuelve un JSON inservible.
        from process_ai_core.engine import generate_validated_document_json
        from process_ai_core.domains.processes.builder import ProcessBuilder

        builder = ProcessBuilder()
        system_prompt = builder.get_system_prompt()

        try:
            corrected_json = generate_validated_document_json(
                builder=builder,
                prompt=patch_prompt,
                system_prompt=system_prompt,
            )
            logger.info("Documento corregido generado y validado exitosamente")
        except Exception as e:
            logger.error(f"Error al generar documento corregido: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error al generar documento corregido: {str(e)}"
            )

        # Reparsear para obtener el modelo de dominio (ya validado por el helper).
        process_doc = builder.parse_document(corrected_json)

        from process_ai_core.domains.processes.renderer import ProcessRenderer
        from process_ai_core.domains.processes.profiles import get_profile
        from process_ai_core.db.helpers import create_run, update_document_status
        from process_ai_core.config import get_settings
        from process_ai_core.export import export_pdf
        import uuid
        import shutil

        # Generar run_id antes de crear en BD
        new_run_id = str(uuid.uuid4())
        settings = get_settings()
        new_run_dir = _run_dir(patch_workspace_id, new_run_id)
        new_run_dir.mkdir(parents=True, exist_ok=True)

        # Obtener imágenes del run original si existe
        images_by_step = {}
        evidence_images = []

        if run_id:
            original_run_dir = _run_dir(patch_workspace_id, run_id)
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
        output_dir = _run_dir(patch_workspace_id, new_run_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = output_dir / "process.json"
        md_path = output_dir / "process.md"

        # Enriquecer el JSON con las imágenes estructuradas (imagen↔paso + evidencia).
        from process_ai_core.assets_json import inject_assets_into_json
        corrected_json = inject_assets_into_json(corrected_json, images_by_step, evidence_images)

        json_path.write_text(corrected_json, encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")

        logger.info(f"Artifacts guardados en {output_dir}")

        # Generar PDF
        pdf_generated = False
        pdf_branding = None
        with get_db_session() as branding_session:
            doc_for_branding = branding_session.query(Document).filter_by(id=document_id).first()
            pdf_branding = get_workspace_pdf_branding(
                branding_session,
                doc_for_branding.workspace_id if doc_for_branding else None,
            )
        try:
            export_pdf(
                run_dir=output_dir,
                md_path=md_path,
                pdf_name="process.pdf",
                branding=pdf_branding,
            )
            pdf_generated = True
            logger.info("PDF generado exitosamente")
        except Exception as pdf_error:
            logger.warning(f"Error al generar PDF (opcional): {pdf_error}")

        # Subir artefactos del run (json/md/pdf + assets) a object storage (no-op en local).
        from process_ai_core.storage import sync_run_dir_to_storage
        sync_run_dir_to_storage(patch_workspace_id, new_run_id, output_dir)

        # Crear Run en BD (transacción atómica)
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

            # Los artefactos del run viven en object storage bajo la clave {run_id}/...;
            # no se trackean en una tabla (se sirven por convención).

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

                # Recalcular uso de storage del tenant (best-effort).
                from process_ai_core.db.helpers import update_workspace_storage_usage
                update_workspace_storage_usage(session, patch_workspace_id)

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

        # Construir URLs firmadas para los artefactos
        artifacts = {
            "json": sign_artifact_url(new_run_id, "process.json", patch_workspace_id),
            "markdown": sign_artifact_url(new_run_id, "process.md", patch_workspace_id),
        }
        if pdf_generated:
            artifacts["pdf"] = sign_artifact_url(new_run_id, "process.pdf", patch_workspace_id)

        logger.info(f"Patch completado exitosamente, run_id: {new_run_id}")

        from api.models.requests import ProcessRunResponse
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
