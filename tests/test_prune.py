"""
Test de integración del prune de artefactos huérfanos (Fase E3).

Verifica que `prune_orphan_artifacts`:
  - detecta objetos flat (esquema viejo) y runs/documentos inexistentes,
  - NO toca los artefactos de runs/documentos que sí existen,
  - en dry_run no borra; con apply borra.
"""

import uuid

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion, Folder, Process, Run, Workspace
from process_ai_core.db.helpers import prune_orphan_artifacts
from process_ai_core.storage.local import LocalDiskStorage


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    import process_ai_core.storage as storage_pkg
    monkeypatch.setattr(storage_pkg, "get_storage", lambda: store)
    return store


def test_prune_detects_and_deletes_orphans(session, tmp_storage):
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(id=f"prn-ws-{uid}", slug=f"prn-ws-{uid}", name="Prn", workspace_type="organization")
    session.add(ws); session.flush()
    folder = Folder(id=f"prn-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder); session.flush()
    doc = Process(id=f"prn-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
                  document_type="process", name="Prn Doc", status="draft")
    session.add(doc); session.flush()
    real_run = Run(id=f"prn-run-{uid}", document_id=doc.id, domain="process")
    session.add(real_run); session.flush()

    # Objetos en storage: run real (existe), run huérfano, y un flat viejo.
    tmp_storage.put(f"workspaces/{ws.id}/runs/{real_run.id}/process.json", b"{}")
    tmp_storage.put(f"workspaces/{ws.id}/runs/ghost-run-xyz/process.json", b"{}")
    tmp_storage.put("old-flat-run/process.json", b"{}")

    try:
        # dry-run: detecta pero no borra
        summary = prune_orphan_artifacts(session, dry_run=True)
        assert summary["flat"] >= 1
        assert summary["orphan_runs"] >= 1
        assert summary["objects_deleted"] == 0
        assert tmp_storage.exists(f"workspaces/{ws.id}/runs/ghost-run-xyz/process.json")

        # apply: borra huérfanos + flat, NO el run real
        prune_orphan_artifacts(session, dry_run=False)
        assert not tmp_storage.exists(f"workspaces/{ws.id}/runs/ghost-run-xyz/process.json")
        assert not tmp_storage.exists("old-flat-run/process.json")
        assert tmp_storage.exists(f"workspaces/{ws.id}/runs/{real_run.id}/process.json")
    finally:
        session.query(Run).filter_by(id=real_run.id).delete()
        session.query(DocumentVersion).filter_by(document_id=doc.id).delete()
        session.query(Process).filter_by(id=doc.id).delete()
        session.query(Document).filter_by(id=doc.id).delete()
        session.query(Folder).filter_by(workspace_id=ws.id).delete()
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()
