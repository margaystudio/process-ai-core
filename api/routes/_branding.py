from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.config import get_settings
from process_ai_core.db.models import Document, Run, Workspace
from process_ai_core.export.branding import PdfBranding


def _get_workspace_branding(workspace: Workspace) -> dict:
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    branding = metadata.get("branding") or {}
    return branding if isinstance(branding, dict) else {}


def _resolve_workspace_logo_path(workspace: Workspace) -> str | None:
    branding = _get_workspace_branding(workspace)
    filename = branding.get("client_icon_filename")
    if not isinstance(filename, str) or not filename.strip():
        return None

    settings = get_settings()
    logo_path = Path(settings.output_dir) / "workspace-branding" / workspace.id / filename
    if not logo_path.exists():
        return None
    return str(logo_path.resolve())


def get_workspace_pdf_branding(session: Session, workspace_id: str | None) -> PdfBranding | None:
    if not workspace_id:
        return None

    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        return None

    branding = _get_workspace_branding(workspace)
    return PdfBranding(
        logo_path=_resolve_workspace_logo_path(workspace),
        primary_color=branding.get("primary_color") if isinstance(branding.get("primary_color"), str) else None,
        secondary_color=branding.get("secondary_color") if isinstance(branding.get("secondary_color"), str) else None,
    )


def get_run_pdf_branding(session: Session, run_id: str) -> PdfBranding | None:
    run = session.query(Run).filter_by(id=run_id).first()
    if not run:
        return None
    document = session.query(Document).filter_by(id=run.document_id).first()
    if not document:
        return None
    return get_workspace_pdf_branding(session, document.workspace_id)
