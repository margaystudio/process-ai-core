"""
Versiones y flujo de aprobación de un documento:
- Listado de versiones, versión actual e historial de auditoría.
- Preview PDF de una versión.
- Envío a revisión, cancelación de envío y clonado a borrador.
"""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel


class SubmitVersionRequest(BaseModel):
    """Body opcional del submit: aprobadores sugeridos + comentario del autor.

    Semántica sugerencia + notificación: NO restringe quién puede aprobar.
    """

    approver_ids: list[str] = []
    comment: str = ""

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion
from process_ai_core.db.helpers import (
    cancel_submission,
    get_or_create_draft,
    submit_version_for_review,
)
from process_ai_core.config import get_settings
from process_ai_core.export import export_pdf_from_content, get_export_content

from api.routes._branding import get_workspace_pdf_branding
from api.routes._run_paths import run_dir as _run_dir
from api.dependencies import get_current_user_id
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
)

from ._helpers import (
    _assert_doc_in_active_workspace,
    _rewrite_img_src_to_absolute,
    _strip_latex_artifacts,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{document_id}/versions")
async def get_document_versions(
    document_id: str,
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
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
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

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
async def get_version_preview_pdf(
    document_id: str,
    version_id: str,
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
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
        document = session.query(Document).filter_by(id=document_id).first()
        if document:
            _assert_doc_in_active_workspace(document.workspace_id, resolve_tenant_workspace_id(ctx), document_id)
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
        markdown_fallback = getattr(version, "content_markdown", None)
        # Capturar el workspace_id DENTRO de la sesión: fuera de ella el
        # instance queda detached y acceder al atributo lanza DetachedInstanceError.
        document_workspace_id = document.workspace_id if document else None
        pdf_branding = get_workspace_pdf_branding(
            session,
            document_workspace_id,
        )

    def _is_weasyprint_system_dependency_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        markers = (
            "libgobject-2.0-0",
            "cannot load library",
            "ctypes.util.find_library",
            "weasyprint",
        )
        return any(marker in msg for marker in markers)

    def _convert_html_to_markdown_with_pandoc(html_content: str) -> str:
        """Convierte HTML a Markdown usando Pandoc para fallback de PDF en Windows."""
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            in_html = tmp_dir / "content.html"
            out_md = tmp_dir / "content.md"
            in_html.write_text(html_content, encoding="utf-8")

            cmd = [
                "pandoc",
                in_html.name,
                "--from=html",
                "--to=gfm-raw_html",
                "--wrap=none",
                "-o",
                out_md.name,
            ]
            result = subprocess.run(
                cmd,
                cwd=str(tmp_dir),
                check=True,
                capture_output=True,
                text=True,
            )
            if not out_md.exists():
                stderr = (result.stderr or "").strip()
                raise RuntimeError(f"Pandoc no generó Markdown desde HTML. STDERR: {stderr[:500]}")
            md = out_md.read_text(encoding="utf-8")
            if not md.strip():
                raise RuntimeError("Pandoc devolvió Markdown vacío al convertir HTML")
            return md

    # Fuente de verdad para visualización:
    # regeneramos siempre el preview desde el contenido actual de la versión.
    # Esto evita desfasajes cuando cambia la plantilla PDF o cuando existe un
    # draft_preview.pdf viejo guardado en disco.

    # Post-procesar HTML: limpiar artefactos LaTeX y reescribir URLs de imágenes
    version_workspace_id = document_workspace_id
    if fmt == "html":
        content = _strip_latex_artifacts(content)
        content = _rewrite_img_src_to_absolute(
            content, version_run_id, api_base, workspace_id=version_workspace_id
        )

    # Mismo directorio que el original cuando la versión tiene run_id (assets/, etc.)
    run_dir = None
    if version_run_id and version_workspace_id:
        run_dir = _run_dir(version_workspace_id, version_run_id).resolve()
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
        selected_content = content
        selected_format = fmt

        try:
            pdf_path = export_pdf_from_content(
                content=selected_content,
                format=selected_format,
                run_dir=_run_dir_for_cleanup,
                pdf_name="preview.pdf",
                base_url=api_base if selected_format == "html" else None,
                branding=pdf_branding,
            )
        except Exception as export_exc:
            can_fallback = bool(markdown_fallback and str(markdown_fallback).strip())
            if selected_format == "html" and _is_weasyprint_system_dependency_error(export_exc):
                converted_markdown: Optional[str] = None
                try:
                    converted_markdown = _convert_html_to_markdown_with_pandoc(selected_content)
                    logger.warning(
                        "WeasyPrint no disponible; reintentando PDF con HTML convertido a Markdown (Pandoc) para versión %s",
                        version_id,
                    )
                except Exception as conversion_exc:
                    logger.warning(
                        "Fallback HTML->Markdown con Pandoc falló; usando content_markdown almacenado para versión %s: %s",
                        version_id,
                        conversion_exc,
                    )

                if converted_markdown:
                    selected_content = converted_markdown
                elif can_fallback:
                    selected_content = str(markdown_fallback)
                else:
                    raise
                selected_format = "markdown"
                pdf_path = export_pdf_from_content(
                    content=selected_content,
                    format=selected_format,
                    run_dir=_run_dir_for_cleanup,
                    pdf_name="preview.pdf",
                    base_url=None,
                    branding=pdf_branding,
                )
            else:
                raise

        pdf_bytes = pdf_path.read_bytes()
        content_file = _run_dir_for_cleanup / ("content.html" if selected_format == "html" else "content.md")
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
    except (FileNotFoundError, OSError, RuntimeError) as e:
        logger.warning("Error generando PDF de versión: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo generar el PDF: {e}",
        ) from e
    finally:
        if _is_temp_dir and _run_dir_for_cleanup:
            shutil.rmtree(_run_dir_for_cleanup, ignore_errors=True)


@router.get("/{document_id}/current-version")
async def get_current_document_version(
    document_id: str,
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
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
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

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
async def get_document_audit_log(
    document_id: str,
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
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
        _assert_doc_in_active_workspace(doc.workspace_id, resolve_tenant_workspace_id(ctx), document_id)

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
    payload: SubmitVersionRequest | None = None,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Envía una versión DRAFT a revisión (cambia a IN_REVIEW y crea Validation).

    Solo usuarios con permisos para editar documentos pueden enviar a revisión.

    Args:
        document_id: ID del documento
        version_id: ID de la versión DRAFT a enviar
        user_id: ID del usuario que envía
    Returns:
        Versión actualizada y validación creada
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
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

        _assert_doc_in_active_workspace(doc.workspace_id, workspace_id, document_id)

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
            body = payload or SubmitVersionRequest()
            updated_version, validation = submit_version_for_review(
                session=session,
                version_id=version_id,
                submitter_id=user_id,
                approver_ids=body.approver_ids,
                comment=body.comment,
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
                "assigned_approver_ids": json.loads(validation.assigned_approver_ids or "[]"),
                "submit_comment": validation.submit_comment or "",
            },
        }


@router.post("/{document_id}/versions/{version_id}/cancel-submission")
async def cancel_submission_endpoint(
    document_id: str,
    version_id: str,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Cancela el envío a revisión y vuelve la versión a borrador.
    Solo el creador de la versión (quien la envió) puede cancelar.
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
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
        _assert_doc_in_active_workspace(doc.workspace_id, workspace_id, document_id)
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
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Crea un nuevo DRAFT clonando una versión APPROVED o REJECTED.

    Solo usuarios con permisos para editar documentos pueden clonar versiones.

    Args:
        document_id: ID del documento
        version_id: ID de la versión a clonar (debe ser APPROVED o REJECTED)
        user_id: ID del usuario que clona

    Returns:
        Nueva versión DRAFT creada
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
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

        _assert_doc_in_active_workspace(doc.workspace_id, workspace_id, document_id)

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
