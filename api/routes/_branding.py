from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.config import get_settings
from process_ai_core.db.models import Document, Run, Workspace
from process_ai_core.export.branding import PdfBranding
from process_ai_core.storage import get_storage, workspace_branding_key

logger = logging.getLogger(__name__)


def _get_workspace_branding(workspace: Workspace) -> dict:
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    branding = metadata.get("branding") or {}
    return branding if isinstance(branding, dict) else {}


def _legacy_local_logo_path(workspace_id: str, filename: str) -> Path:
    """Ruta del esquema viejo (disco local), previo a mover el logo a storage."""
    return Path(get_settings().output_dir) / "workspace-branding" / workspace_id / filename


def _logo_cache_path(workspace_id: str, filename: str) -> Path:
    """
    Ruta local donde se materializa el logo bajado de storage.

    Los dos motores de PDF necesitan un archivo en disco: WeasyPrint lo resuelve
    como `<img src>` y LaTeX como `\\includegraphics`. Un data URI serviría para
    WeasyPrint pero no para LaTeX, así que se materializa una sola vez y se
    reusa. El disco es solo cache — la fuente de verdad es object storage —, por
    lo que perderlo en un redeploy no rompe nada: se vuelve a bajar.
    """
    return (
        Path(get_settings().output_dir)
        / ".cache"
        / "workspace-branding"
        / workspace_id
        / filename
    )


def _resolve_workspace_logo_path(workspace: Workspace) -> str | None:
    """
    Devuelve la ruta local del logo, bajándolo de object storage si hace falta.

    Antes esto leía directo del disco local y devolvía None en silencio si el
    archivo no estaba. En Cloud Run eso significaba que el PDF oficial se
    congelaba SIN logo y nadie se enteraba: el filesystem es efímero y hay varias
    instancias, así que el archivo que subió una no existe en la que congela.

    Ahora: storage → cache local → (compatibilidad) ruta local vieja. Si el
    branding está configurado y aun así no se resuelve, se loggea un warning.
    """
    branding = _get_workspace_branding(workspace)
    filename = branding.get("client_icon_filename")
    if not isinstance(filename, str) or not filename.strip():
        return None  # sin logo configurado: no es un error
    filename = filename.strip()

    cached = _logo_cache_path(workspace.id, filename)
    if cached.exists() and cached.stat().st_size > 0:
        return str(cached.resolve())

    key = workspace_branding_key(workspace.id, filename)
    try:
        data = get_storage().get(key)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        return str(cached.resolve())
    except FileNotFoundError:
        pass  # puede ser un logo subido antes de mover el branding a storage
    except Exception as exc:
        logger.warning(
            "No se pudo leer el logo del workspace %s desde storage (key=%s): %s. "
            "El PDF se va a generar sin logo.",
            workspace.id, key, exc,
        )
        return None

    # Compatibilidad: logos subidos con el esquema viejo, todavía en disco local.
    legacy = _legacy_local_logo_path(workspace.id, filename)
    if legacy.exists():
        logger.info(
            "Logo del workspace %s resuelto desde la ruta local vieja (%s). "
            "Se va a servir igual, pero conviene re-subirlo para que quede en storage.",
            workspace.id, legacy,
        )
        return str(legacy.resolve())

    logger.warning(
        "El workspace %s tiene branding configurado (client_icon_filename=%s) pero "
        "el logo no está ni en storage (key=%s) ni en disco. El PDF se va a "
        "generar sin logo.",
        workspace.id, filename, key,
    )
    return None


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
