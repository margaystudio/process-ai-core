#!/usr/bin/env python3
"""
Migra archivos del módulo Contexto (context_files / context_folders) a documentos
importados en carpetas de documentos (Folder).

Uso:
    python tools/migrate_context_to_documents.py [--dry-run] [--workspace-id WS_ID]

Los archivos migrados quedan APPROVED (eran material de referencia disponible).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from process_ai_core.config import get_settings
from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import create_folder, update_workspace_storage_usage
from process_ai_core.db.models import ContextFile, ContextFolder, Folder, Workspace
from process_ai_core.document_import import create_imported_document

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIGRATION_ROOT_NAME = "Contexto migrado"


def _get_root_folder(session, workspace_id: str) -> Folder:
    root = (
        session.query(Folder)
        .filter_by(workspace_id=workspace_id, parent_id=None)
        .order_by(Folder.sort_order.asc(), Folder.created_at.asc())
        .first()
    )
    if not root:
        raise RuntimeError(f"No hay carpeta raíz en workspace {workspace_id}")
    return root


def _ensure_migration_parent(session, workspace_id: str) -> Folder:
    existing = (
        session.query(Folder)
        .filter_by(workspace_id=workspace_id, name=MIGRATION_ROOT_NAME, parent_id=None)
        .first()
    )
    if existing:
        return existing
    return create_folder(
        session=session,
        workspace_id=workspace_id,
        name=MIGRATION_ROOT_NAME,
        path=MIGRATION_ROOT_NAME,
        parent_id=None,
        sort_order=999,
    )


def _map_context_folders(session, workspace_id: str, migration_parent: Folder) -> dict[str, str]:
    """context_folder_id -> document Folder.id"""
    mapping: dict[str, str] = {}
    context_folders = (
        session.query(ContextFolder)
        .filter_by(workspace_id=workspace_id)
        .order_by(ContextFolder.path.asc())
        .all()
    )

    for cf in context_folders:
        parent_doc_folder_id = migration_parent.id
        if cf.parent_id and cf.parent_id in mapping:
            parent_doc_folder_id = mapping[cf.parent_id]

        parent = session.query(Folder).filter_by(id=parent_doc_folder_id).first()
        path = f"{parent.path}/{cf.name}" if parent and parent.path else cf.name

        folder = create_folder(
            session=session,
            workspace_id=workspace_id,
            name=cf.name,
            path=path,
            parent_id=parent_doc_folder_id,
            sort_order=cf.sort_order,
        )
        session.flush()
        mapping[cf.id] = folder.id

    return mapping


def _resolve_file_bytes(cf: ContextFile, output_dir: Path) -> bytes | None:
    file_path = output_dir / cf.file_path
    if file_path.is_file():
        return file_path.read_bytes()
    # Fallback: output/context/{workspace_id}/{filename}
    alt = output_dir / "context" / cf.workspace_id / Path(cf.file_path).name
    if alt.is_file():
        return alt.read_bytes()
    logger.warning("Archivo no encontrado para context file %s (%s)", cf.id, cf.name)
    return None


def migrate_workspace(session, workspace: Workspace, *, dry_run: bool, system_user_id: str | None) -> int:
    context_files = session.query(ContextFile).filter_by(workspace_id=workspace.id).all()
    if not context_files:
        return 0

    settings = get_settings()
    output_dir = Path(settings.output_dir)
    migration_parent = _ensure_migration_parent(session, workspace.id)
    folder_map = _map_context_folders(session, workspace.id, migration_parent)
    root_folder = _get_root_folder(session, workspace.id)

    migrated = 0
    for cf in context_files:
        file_bytes = _resolve_file_bytes(cf, output_dir)
        if not file_bytes:
            continue

        target_folder_id = folder_map.get(cf.folder_id) if cf.folder_id else root_folder.id
        if not target_folder_id:
            target_folder_id = migration_parent.id

        if dry_run:
            logger.info("[dry-run] migraría %s -> folder %s", cf.name, target_folder_id)
            migrated += 1
            continue

        create_imported_document(
            session=session,
            workspace_id=workspace.id,
            folder_id=target_folder_id,
            filename=cf.name,
            file_bytes=file_bytes,
            requires_approval=False,
            user_id=system_user_id,
        )
        migrated += 1
        logger.info("Migrado: %s (workspace %s)", cf.name, workspace.id)

    if not dry_run and migrated:
        update_workspace_storage_usage(session, workspace.id)

    return migrated


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrar context files a documentos importados")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir en BD")
    parser.add_argument("--workspace-id", help="Migrar solo un workspace")
    args = parser.parse_args()

    total = 0
    with get_db_session() as session:
        query = session.query(Workspace)
        if args.workspace_id:
            query = query.filter_by(id=args.workspace_id)
        workspaces = query.all()

        if not workspaces:
            logger.warning("No se encontraron workspaces")
            return

        for ws in workspaces:
            count = migrate_workspace(session, ws, dry_run=args.dry_run, system_user_id=None)
            total += count

        if not args.dry_run:
            session.commit()
            logger.info("Migración completada: %d archivos", total)
        else:
            session.rollback()
            logger.info("[dry-run] Se migrarían %d archivos", total)


if __name__ == "__main__":
    main()
