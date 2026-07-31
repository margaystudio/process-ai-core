"""
Utilidades para importar archivos como documentos (sin pipeline IA).
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.db.document_codes import assign_document_code
from process_ai_core.db.models import DocumentVersion, Folder, Process
from process_ai_core.export.markdown_html import render_frozen_html
from process_ai_core.media import _extract_text_from_document, pdf_text_or_ocr
from process_ai_core.pdf_images import (
    PdfContent,
    describe_image,
    extract_pdf_content,
    figure_markdown,
    figure_title,
)
from process_ai_core.storage import get_storage
from process_ai_core.storage.keys import version_asset_key, version_source_file_key

logger = logging.getLogger(__name__)

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


def _build_imported_content(
    filename: str,
    text_content: str,
    storage_key: str,
    images: list[dict] | None = None,
) -> tuple[str, str]:
    stem = Path(filename).stem or filename
    payload = {
        "name": stem,
        "imported": True,
        "source_filename": filename,
        "source_storage_key": storage_key,
        "contenido": text_content,
    }
    # Las imágenes van también estructuradas: el markdown las referencia por URL,
    # pero el JSON es lo que consume el RAG / la capa de revisión, y ahí hace
    # falta saber de qué imagen se trata sin tener que parsear markdown.
    if images:
        payload["imagenes"] = images
    content_json = json.dumps(payload, ensure_ascii=False)
    body = text_content.strip() if text_content and text_content.strip() else f"_Archivo importado: {filename}_"
    content_markdown = f"# {stem}\n\n{body}\n"
    return content_json, content_markdown


def version_asset_url(document_id: str, version_id: str, filename: str) -> str:
    """
    URL (sin host) del endpoint que sirve un asset de la versión.

    Es el tercer esquema de ruta que resuelve `StorageAssetFetcher`, junto con
    `assets/...` (artefactos de un run) y las imágenes del editor manual. Se
    resuelve leyendo el blob de object storage, sin salir por HTTP.
    """
    return f"/api/v1/documents/{document_id}/versions/{version_id}/assets/{filename}"


def _extract_pdf_body(
    contenido: PdfContent,
    filename: str,
    workspace_id: str,
    document_id: str,
    version_id: str,
) -> tuple[str, list[dict]]:
    """
    Markdown del PDF **con sus imágenes en el lugar donde estaban**.

    Las imágenes se suben a object storage como assets de la versión y el
    markdown las referencia por el endpoint de assets: el mismo mecanismo que ya
    usa el editor manual, y el que `StorageAssetFetcher` sabe resolver sin red al
    congelar el PDF. Si al congelar faltara alguna, la verificación de integridad
    aborta el freeze en vez de publicar un artefacto mutilado.

    El texto sale del MISMO `PdfContent` que ubicó las imágenes: es lo que
    garantiza que cada figura quede donde el texto la anuncia.
    """
    storage = get_storage()
    imagenes_meta: list[dict] = []
    descripciones: dict[int, object] = {}

    for imagen in contenido.images:
        asset_id = f"img{imagen.order:02d}"
        ext = "jpg" if imagen.ext == "jpeg" else imagen.ext
        key = version_asset_key(workspace_id, document_id, version_id, asset_id, ext)
        storage.put(key, imagen.data, _guess_content_type(f"{asset_id}.{ext}", f".{ext}"))

        descripcion = describe_image(imagen, nombre=filename)
        descripciones[imagen.order] = descripcion
        imagenes_meta.append(
            {
                "asset_id": asset_id,
                "url": version_asset_url(document_id, version_id, f"{asset_id}.{ext}"),
                "storage_key": key,
                "pagina": imagen.page,
                "orden": imagen.order,
                "titulo": figure_title(imagen, descripcion),
                # Inferencia pura: se guarda marcada como tal, igual que se
                # imprime (ADR-015).
                "descripcion": descripcion.descripcion if descripcion else "",
                "descripcion_confianza": "inferido",
                "contexto": imagen.context,
                "sha256": imagen.sha256,
            }
        )

    urls = {m["orden"]: m["url"] for m in imagenes_meta}
    partes: list[str] = []
    for item in contenido.flow:
        if item.kind == "text":
            partes.append(item.text)
        elif item.image is not None:
            partes.append(
                figure_markdown(item.image, urls[item.image.order], descripciones[item.image.order])
            )

    logger.info(
        "PDF importado '%s': %d imagen(es) conservadas en la representación derivada.",
        filename, len(imagenes_meta),
    )
    return "\n\n".join(p for p in partes if p.strip()), imagenes_meta


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

    # Un PDF con imágenes embebidas perdía TODAS sus imágenes al importarse: la
    # representación derivada quedaba solo con texto, y es la derivada lo que se
    # lee en la app y lo que indexa Tyto. Ahora las conserva, en su posición.
    #
    # El PDF se abre UNA vez: el mismo `PdfContent` da el texto y las imágenes con
    # su posición. Que salgan del mismo motor no es una optimización, es lo que
    # hace que la figura quede donde el texto la anuncia.
    imagenes_meta: list[dict] = []
    body: str | None = None
    if ext == ".pdf":
        contenido = extract_pdf_content(file_bytes, nombre=filename)
        if contenido.images:
            try:
                body, imagenes_meta = _extract_pdf_body(
                    contenido, filename, workspace_id, document_id, version_id
                )
            except Exception as exc:  # noqa: BLE001 — una importación no se rompe por esto
                logger.warning(
                    "No se pudieron guardar las imágenes de '%s' (%s); se importa solo el texto.",
                    filename, exc,
                )
                body, imagenes_meta = None, []
        if body is None:
            # Sin imágenes de contenido (o fallo al guardarlas): el texto sale del
            # mismo `PdfContent`, con caída a OCR si el PDF está escaneado.
            body = pdf_text_or_ocr(contenido, file_bytes, filename)

    text_content = body if body is not None else _extract_text_from_bytes(filename, file_bytes)
    content_json, content_markdown = _build_imported_content(
        filename, text_content, storage_key, imagenes_meta
    )

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
    # Mismo código estable que para los documentos generados (ADR-019).
    assign_document_code(session, process)

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
        # Congelado desde la creación, igual que en el pipeline. Para un .pdf
        # importado no se usa (el artefacto es el archivo original), pero para
        # .docx/.md/.txt este HTML es lo que se va a imprimir.
        content_html=render_frozen_html(content_markdown),
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
