"""
Utilidades para importar archivos como documentos (sin pipeline IA).
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.db.models import DocumentVersion, Folder, Process
from process_ai_core.media import _extract_text_from_document
from process_ai_core.storage import get_storage
from process_ai_core.storage.keys import version_source_file_key

ALLOWED_IMPORT_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
TEXT_EXTENSIONS = {".txt", ".md"}


def _guess_content_type(filename: str, ext: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if ext in TEXT_EXTENSIONS:
        return "text/plain"
    return "application/octet-stream"


def _build_imported_content(filename: str, text_content: str, storage_key: str) -> tuple[str, str]:
    stem = Path(filename).stem or filename
    payload = {
        "name": stem,
        "imported": True,
        "source_filename": filename,
        "source_storage_key": storage_key,
        "contenido": text_content,
    }
    content_json = json.dumps(payload, ensure_ascii=False)
    body = text_content.strip() if text_content and text_content.strip() else f"_Archivo importado: {filename}_"
    content_markdown = f"# {stem}\n\n{body}\n"
    return content_json, content_markdown


def _extract_text_from_bytes(filename: str, file_bytes: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return file_bytes.decode("utf-8", errors="replace")
    suffix = ext or ".bin"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)
    try:
        return _extract_text_from_document(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def create_imported_document(
    session: Session,
    workspace_id: str,
    folder_id: str,
    filename: str,
    file_bytes: bytes,
    requires_approval: bool,
    user_id: str | None,
) -> tuple[Process, DocumentVersion]:
    """
    Crea un documento importado desde un archivo subido.

    Si requires_approval=False, queda APPROVED de inmediato.
    Si requires_approval=True, queda en DRAFT para el flujo normal de revisión.
    """
    from process_ai_core.db.helpers import create_audit_log, update_document_status

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_IMPORT_EXTENSIONS:
        raise ValueError(
            f"Formato no permitido: {ext or '(sin extensión)'}. "
            f"Use: {', '.join(sorted(ALLOWED_IMPORT_EXTENSIONS))}"
        )

    folder = session.query(Folder).filter_by(id=folder_id, workspace_id=workspace_id).first()
    if not folder:
        raise ValueError(f"Carpeta {folder_id} no encontrada en el workspace")

    display_name = Path(filename).stem or filename
    document_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    storage_key = version_source_file_key(workspace_id, document_id, version_id, filename)
    content_type = _guess_content_type(filename, ext)
    storage = get_storage()
    storage.put(storage_key, file_bytes, content_type)

    text_content = _extract_text_from_bytes(filename, file_bytes)
    content_json, content_markdown = _build_imported_content(filename, text_content, storage_key)

    process = Process(
        id=document_id,
        workspace_id=workspace_id,
        folder_id=folder_id,
        domain="process",
        name=display_name,
        description=f"Archivo importado: {filename}",
        audience="",
        detail_level="",
        context_text="",
    )
    session.add(process)
    session.flush()

    version_status = "DRAFT" if requires_approval else "APPROVED"
    now = datetime.now(UTC)

    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        run_id=None,
        version_number=1,
        version_status=version_status,
        content_type="imported",
        content_json=content_json,
        content_markdown=content_markdown,
        content_html=None,
        approved_at=None if requires_approval else now,
        approved_by=None if requires_approval else user_id,
        validation_id=None,
        rejected_at=None,
        rejected_by=None,
        is_current=not requires_approval,
        source_file_key=storage_key,
        source_file_name=filename,
        pdf_storage_key=storage_key if ext == ".pdf" and not requires_approval else None,
        pdf_sha256=hashlib.sha256(file_bytes).hexdigest() if ext == ".pdf" and not requires_approval else None,
        pdf_generated_at=now if ext == ".pdf" and not requires_approval else None,
        pdf_render_engine="imported" if ext == ".pdf" and not requires_approval else None,
        created_by=user_id,
    )
    session.add(version)
    session.flush()

    if requires_approval:
        update_document_status(session, document_id, "draft")
        action = "version.imported_draft"
    else:
        process.approved_version_id = version_id
        process.status = "approved"
        action = "version.imported_approved"

    create_audit_log(
        session=session,
        document_id=document_id,
        user_id=user_id,
        action=action,
        entity_type="version",
        entity_id=version_id,
        metadata_json=json.dumps(
            {
                "source_filename": filename,
                "requires_approval": requires_approval,
                "storage_key": storage_key,
            }
        ),
    )

    return process, version
