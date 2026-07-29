"""
Versiones y flujo de aprobación de un documento:
- Listado de versiones, versión actual e historial de auditoría.
- PDF congelado (artefacto de auditoría) de una versión aprobada.
- Preview PDF regenerado de una versión editable (DRAFT / IN_REVIEW).
- Envío a revisión, cancelación de envío y clonado a borrador.
"""

import json
import logging
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
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
from process_ai_core.storage import get_storage

from api.routes._branding import get_workspace_pdf_branding
from api.routes._document_context import build_document_context
from api.routes._freeze import freeze_approved_pdf
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
def get_document_versions(
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


def frozen_pdf_path(document_id: str, version_id: str) -> str:
    """Path (sin host) del endpoint que sirve el PDF congelado de una versión."""
    return f"/api/v1/documents/{document_id}/versions/{version_id}/pdf"


def _serves_frozen_pdf(version: DocumentVersion) -> bool:
    """
    True si esta versión tiene (o debe tener) un PDF congelado y por lo tanto
    NO se puede regenerar on-the-fly sin romper la trazabilidad.

    - APPROVED: siempre. Si el freeze al aprobar falló, se reintenta al servir.
    - OBSOLETE: solo si quedó congelada (fue APPROVED en su momento). Una
      OBSOLETE sin blob nunca lo va a tener: `freeze_approved_pdf` solo congela
      versiones APPROVED, así que se sigue regenerando.

    DRAFT / IN_REVIEW / REJECTED no tienen artefacto congelado: se regeneran.
    """
    if version.version_status == "APPROVED":
        return True
    return version.version_status == "OBSOLETE" and bool(version.pdf_storage_key)


@router.get("/{document_id}/versions/{version_id}/pdf")
def get_version_frozen_pdf(
    document_id: str,
    version_id: str,
    request: Request,
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Devuelve el PDF **congelado** de una versión: exactamente los bytes que se
    subieron a object storage al aprobarla (o el archivo original, para PDFs
    importados que no requieren aprobación).

    Es el artefacto de auditoría: su SHA-256 está registrado en
    `document_versions.pdf_sha256`. No se re-renderiza nunca, así que cambiar la
    plantilla del PDF no altera lo que ve el usuario.

    Si la versión está APPROVED pero no tiene `pdf_storage_key` (el freeze es
    best-effort, ver api/routes/_freeze.py), se reintenta el freeze una vez bajo
    lock de fila. Si tampoco se puede, devuelve 404: NO se cae al render
    on-the-fly, porque eso devolvería bytes sin hash registrado — justo lo que
    este endpoint evita.

    Sobre el lock (`SELECT ... FOR UPDATE`), dos decisiones deliberadas:

    - **Solo en el camino frío.** El caso normal (la versión YA tiene blob) no
      toma ningún lock: se resuelve con el SELECT sin bloqueo de arriba. El lock
      solo aparece cuando de verdad hay que escribir, que es raro.
    - **Se sostiene durante el render.** Soltarlo antes no serializaría nada. El
      costo es acotado: en Postgres un lock de fila no bloquea lectores (MVCC),
      así que solo espera otro escritor de ESA fila — es decir, otro reintento de
      freeze de la misma versión, que es exactamente lo que queremos serializar.
      Editar un borrador escribe en OTRA fila (la DRAFT) y no se ve afectado.
    - **Sin riesgo de deadlock con la aprobación.** El camino de aprobación
      (api/routes/validations.py, que también llama a freeze_approved_pdf) toma
      locks sobre validation + version + document; este handler toma exactamente
      uno, el de document_versions, y ninguno más después. Un ciclo necesita que
      cada parte espere un lock que la otra ya tiene: acá una de las dos partes
      no pide nada más, así que el ciclo no puede cerrarse. Si en el futuro este
      endpoint necesitara tocar otra tabla, hay que revisar esto de nuevo.
    """
    with get_db_session() as session:
        document = session.query(Document).filter_by(id=document_id).first()
        if not document:
            raise HTTPException(
                status_code=404, detail=f"Documento {document_id} no encontrado"
            )
        _assert_doc_in_active_workspace(
            document.workspace_id, resolve_tenant_workspace_id(ctx), document_id
        )

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

        storage_key = version.pdf_storage_key
        if not storage_key and version.version_status == "APPROVED":
            # ── Camino frío: el freeze al aprobar falló y hay que reintentarlo ──
            #
            # Este GET escribe, así que dos requests concurrentes sobre la misma
            # versión pasarían los dos el chequeo de arriba, renderizarían los
            # dos y harían put() sobre la misma clave determinística. El segundo
            # persistiría un pdf_sha256 calculado sobre SUS bytes mientras en
            # storage quedan los del otro: el hash dejaría de identificar al blob.
            #
            # Se toma el lock de fila y se RE-CHEQUEA: el request que pierde la
            # carrera despierta viendo la key que escribió el ganador y sirve ese
            # blob en vez de renderizar de nuevo.
            #
            # populate_existing() no es opcional: sin él SQLAlchemy devuelve la
            # instancia que ya está en el identity map y `pdf_storage_key`
            # seguiría siendo el None que leímos ANTES de esperar el lock — que
            # es justamente el valor obsoleto que el lock existe para descartar.
            version = (
                session.query(DocumentVersion)
                .filter_by(id=version_id, document_id=document_id)
                .populate_existing()
                .with_for_update()
                .one()
            )
            storage_key = version.pdf_storage_key

            if not storage_key:
                logger.warning(
                    "Versión APPROVED %s sin PDF congelado; reintentando freeze",
                    version_id,
                )
                if freeze_approved_pdf(session, version):
                    session.flush()
                    storage_key = version.pdf_storage_key
            else:
                logger.info(
                    "Versión %s: otro request congeló el PDF mientras esperábamos "
                    "el lock; se sirve ese blob sin re-renderizar",
                    version_id,
                )

        if not storage_key:
            if version.version_status == "APPROVED":
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "La versión está aprobada pero no tiene PDF congelado y el "
                        "reintento de generación falló. Revisá los logs del servidor "
                        "(render/subida a storage) y volvé a intentar."
                    ),
                )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"La versión {version_id} no tiene PDF congelado (estado "
                    f"{version.version_status}). Usá el endpoint preview-pdf para "
                    "ver el PDF regenerado de una versión editable."
                ),
            )

        sha256 = version.pdf_sha256
        version_number = version.version_number
        # El PDF congelado de un documento importado ES el archivo original:
        # conservamos su nombre para que la descarga sea reconocible.
        is_source_file = bool(version.source_file_key) and version.source_file_key == storage_key
        source_file_name = version.source_file_name if is_source_file else None

    filename = source_file_name or f"documento-v{version_number}.pdf"
    # Comillas rotas en Content-Disposition ⇒ header inválido.
    filename = PurePosixPath(filename.replace("\\", "/")).name.replace('"', "") or "documento.pdf"

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        # `no-cache` NO significa "no guardes": significa "guardá, pero revalidá
        # siempre". El artefacto es inmutable, pero el DERECHO A VERLO no lo es.
        # Con `immutable` el navegador puede servir el PDF hasta un año sin tocar
        # el servidor: a un usuario al que le revocan el acceso al documento le
        # seguiría abriendo desde su cache. Esto es control de acceso, no
        # performance, así que gana la revalidación.
        #
        # Se conserva casi todo el beneficio: cada apertura hace un round-trip
        # que termina en 304 sin cuerpo — ni render, ni transferencia del PDF.
        "Cache-Control": "private, no-cache",
    }
    etag = f'"{sha256}"' if sha256 else None
    if etag:
        headers["ETag"] = etag
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)

    try:
        pdf_bytes = get_storage().get(storage_key)
    except FileNotFoundError as exc:
        logger.warning(
            "PDF congelado de la versión %s no está en storage (key=%s)", version_id, storage_key
        )
        raise HTTPException(
            status_code=404,
            detail=(
                "El PDF congelado de esta versión está registrado pero no se "
                "encontró en el almacenamiento."
            ),
        ) from exc

    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get("/{document_id}/versions/{version_id}/preview-pdf")
async def get_version_preview_pdf(
    document_id: str,
    version_id: str,
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Genera y devuelve el PDF de una versión **editable** (DRAFT / IN_REVIEW /
    REJECTED) usando la fuente de verdad (content_html si existe, si no
    content_markdown).
    Si la versión tiene run_id, usa el mismo directorio del run (con assets/)
    para generar el PDF igual que el original; si no, usa un temp dir.
    No modifica process.pdf ni artefactos del run.

    Si la versión ya tiene un PDF congelado (APPROVED, u OBSOLETE que se congeló
    al aprobarse), redirige al endpoint del artefacto en lugar de regenerar:
    regenerar devolvería bytes distintos de los que tienen el SHA-256 registrado.
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
        if _serves_frozen_pdf(version):
            # 307 (no 308): la redirección depende del estado de la versión, no
            # es permanente. Mismo origen ⇒ fetch conserva el header Authorization.
            return RedirectResponse(
                url=frozen_pdf_path(document_id, version_id), status_code=307
            )
        try:
            # Siempre HTML: get_export_content normaliza (ver content_source.py).
            content = get_export_content(version)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        version_run_id = version.run_id
        version_status = version.version_status
        # Capturar el workspace_id DENTRO de la sesión: fuera de ella el
        # instance queda detached y acceder al atributo lanza DetachedInstanceError.
        document_workspace_id = document.workspace_id if document else None
        pdf_branding = get_workspace_pdf_branding(
            session,
            document_workspace_id,
        )
        # Contexto del preview: la versión es editable, así que `is_approved` es
        # False y las firmas todavía pueden cambiar. Se pasa igual para que el
        # borrador se vea como se va a ver el aprobado, sin fingir que ya lo está.
        pdf_document_context = (
            build_document_context(session, document, version) if document else None
        )

    # Acá vivía un fallback que, si WeasyPrint no cargaba, convertía el HTML a
    # Markdown con Pandoc y reintentaba por el camino LaTeX. Con un solo motor no
    # tiene sentido: no hay a dónde caer. Si WeasyPrint falla, el preview falla
    # con un 500 explícito — que es lo correcto, porque un preview que sale por
    # otro motor se vería distinto del PDF que después se congela.

    # Fuente de verdad para visualización de una versión editable:
    # regeneramos siempre el preview desde el contenido actual de la versión,
    # que es justamente lo que el autor/revisor quiere ver mientras edita.
    # Las versiones ya congeladas nunca llegan hasta acá (redirigen arriba).

    # Post-procesar HTML: limpiar artefactos LaTeX y reescribir URLs de imágenes.
    # Sin condicional de formato: el contenido ya viene normalizado a HTML, que
    # es lo único sobre lo que estas sustituciones funcionan.
    version_workspace_id = document_workspace_id
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

    # El render corre en un thread pool para no bloquear el event loop: WeasyPrint
    # pide por HTTP las imágenes del documento a esta misma API, y si el render
    # ocupara el hilo principal el servidor no podría responderlas → deadlock.
    import asyncio

    _run_dir_for_cleanup = run_dir
    _is_temp_dir = not version_run_id

    def _generate_sync() -> bytes:
        pdf_path = export_pdf_from_content(
            content=content,
            format="html",
            run_dir=_run_dir_for_cleanup,
            pdf_name="preview.pdf",
            base_url=api_base,
            branding=pdf_branding,
            document_context=pdf_document_context,
        )

        pdf_bytes = pdf_path.read_bytes()
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
                # no-store solo acá: este PDF se regenera desde contenido mutable,
                # cachearlo mostraría un borrador viejo tras guardar en el editor.
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
def get_current_document_version(
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
def get_document_audit_log(
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
def submit_version_for_review_endpoint(
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
def cancel_submission_endpoint(
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
def clone_version_to_draft(
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
