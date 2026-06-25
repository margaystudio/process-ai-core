"""
Resolución del directorio local de un run, alineado con la clave de storage.

Todo artefacto vive (en el bucket y en el disco local de trabajo) bajo
`workspaces/{workspace_id}/runs/{run_id}/...`. Para el backend `local`, el directorio
local DEBE coincidir con esa clave para que el endpoint de artefactos lo sirva. Estos
helpers centralizan esa construcción y evitan el viejo `output/{run_id}` plano.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.config import get_settings
from process_ai_core.storage.keys import run_prefix


def run_dir(workspace_id: str, run_id: str) -> Path:
    """Directorio local del run: output_dir/workspaces/{ws}/runs/{run_id}."""
    return Path(get_settings().output_dir) / run_prefix(workspace_id, run_id)


def run_dir_for_run(session: Session, run_id: str) -> Path | None:
    """
    Resuelve el directorio local de un run existente buscando su workspace
    (run -> document -> workspace_id). Devuelve None si el run no existe.
    """
    from process_ai_core.db.models import Run, Document

    run = session.query(Run).filter_by(id=run_id).first()
    if run is None:
        return None
    doc = session.query(Document).filter_by(id=run.document_id).first()
    if doc is None:
        return None
    return run_dir(doc.workspace_id, run_id)
