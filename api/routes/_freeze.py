"""
Congelado del PDF de una versión APROBADA como artefacto de auditoría (Fase B).

Al aprobar una versión:
  1. Se renderiza el PDF desde su contenido (fuente de verdad: content_html, si no, markdown).
  2. Se sube a object storage bajo la clave canónica de la versión.
  3. Se calcula SHA-256 y se persiste key + hash + timestamp + motor de render.

Best-effort: si el render o la subida fallan, NO se rompe la aprobación; se loggea
un warning y la versión queda aprobada sin PDF congelado (se puede reintentar luego).
"""

from __future__ import annotations

import hashlib
import logging
import re
import tempfile
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.config import get_settings
from process_ai_core.db.models import Document, DocumentVersion
from process_ai_core.export import export_pdf_from_content, get_export_content
from process_ai_core.storage import get_storage, version_pdf_key
from ..artifact_signing import sign_artifact_url
from ._branding import get_workspace_pdf_branding

logger = logging.getLogger(__name__)


def _rewrite_img_src(html: str, run_id: str | None, api_base: str, workspace_id: str | None) -> str:
    """Reescribe src="assets/..." a la URL firmada del endpoint de artefactos."""
    if not html or not run_id or not workspace_id:
        return html

    def repl(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("http") or src.startswith("/api/v1/"):
            return m.group(0)
        if src.startswith("assets/") or src.startswith("./assets/"):
            clean = src.lstrip("./")
            signed = sign_artifact_url(run_id, clean, workspace_id)
            return f'src="{api_base}{signed}"'
        return m.group(0)

    return re.sub(r'src="([^"]+)"', repl, html)


def _render_engine_label(fmt: str) -> str:
    try:
        if fmt == "html":
            import weasyprint  # type: ignore

            return f"weasyprint-{getattr(weasyprint, '__version__', '?')}"
        return "pandoc"
    except Exception:
        return "weasyprint" if fmt == "html" else "pandoc"


def freeze_approved_pdf(session: Session, version: DocumentVersion, api_base: str | None = None) -> bool:
    """
    Renderiza, sube y registra el PDF de una versión APROBADA. Devuelve True si tuvo éxito.

    Idempotente: si la versión ya tiene `pdf_storage_key`, no re-renderiza.
    """
    if version.version_status != "APPROVED":
        return False
    if version.pdf_storage_key:
        return True  # ya congelado

    try:
        document = session.query(Document).filter_by(id=version.document_id).first()
        if not document:
            logger.warning("freeze_approved_pdf: documento %s no encontrado", version.document_id)
            return False
        workspace_id = document.workspace_id

        content, fmt = get_export_content(version)

        settings = get_settings()
        api_base = (api_base or settings.api_base_url).rstrip("/")
        branding = get_workspace_pdf_branding(session, workspace_id)

        if fmt == "html":
            content = _rewrite_img_src(content, version.run_id, api_base, workspace_id)

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = export_pdf_from_content(
                content=content,
                format=fmt,
                run_dir=Path(tmp),
                pdf_name="document.pdf",
                base_url=api_base,
                branding=branding,
            )
            pdf_bytes = Path(pdf_path).read_bytes()

        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        key = version_pdf_key(workspace_id, version.document_id, version.id)
        get_storage().put(key, pdf_bytes, content_type="application/pdf")

        version.pdf_storage_key = key
        version.pdf_sha256 = sha256
        version.pdf_generated_at = datetime.now(UTC)
        version.pdf_render_engine = _render_engine_label(fmt)

        logger.info(
            "PDF aprobado congelado: version=%s key=%s sha256=%s",
            version.id, key, sha256[:12],
        )
        return True
    except Exception as exc:
        logger.warning(
            "freeze_approved_pdf falló para versión %s (la aprobación sigue válida): %s",
            getattr(version, "id", "?"), exc,
        )
        return False
