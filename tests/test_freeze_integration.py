"""
Tests de integración del congelado del PDF al aprobar (Fase B/F).

Verifica, contra la DB real, que al congelar una versión APROBADA:
  - se renderiza el PDF, se sube a storage bajo la clave canónica (tenant-scoped),
  - se persiste pdf_storage_key + pdf_sha256 (que coincide con el blob) + engine,
  - es idempotente (no re-renderiza si ya hay key),
  - las claves de dos workspaces nunca colisionan (aislamiento multi-tenant).

El storage se apunta a un directorio temporal para no tocar output_dir real.
"""

import hashlib
import uuid

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import DocumentVersion, Process, Workspace, Folder
from process_ai_core.storage.local import LocalDiskStorage


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Apunta el storage del freeze a un LocalDiskStorage temporal."""
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    import api.routes._freeze as freeze_mod
    monkeypatch.setattr(freeze_mod, "get_storage", lambda: store)
    return store


def _make_approved_version(session, html="<h1>Doc</h1><p>contenido</p>"):
    """Crea workspace+folder+document+versión APPROVED. Devuelve (version, ids_a_limpiar)."""
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(id=f"frz-ws-{uid}", slug=f"frz-ws-{uid}", name="Frz", workspace_type="organization")
    session.add(ws); session.flush()
    folder = Folder(id=f"frz-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder); session.flush()
    doc = Process(
        id=f"frz-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
        document_type="process", name="Frz Doc", status="approved",
    )
    session.add(doc); session.flush()
    ver = DocumentVersion(
        id=f"frz-ver-{uid}", document_id=doc.id, version_number=1,
        version_status="APPROVED", content_type="generated",
        content_json="{}", content_markdown="# Doc", content_html=html,
        is_current=True,
    )
    session.add(ver); session.flush()
    return ver, ws


def _cleanup(session, version, workspace):
    session.query(DocumentVersion).filter_by(id=version.id).delete()
    session.query(Process).filter_by(id=version.document_id).delete()
    from process_ai_core.db.models import Document
    session.query(Document).filter_by(id=version.document_id).delete()
    session.query(Folder).filter_by(workspace_id=workspace.id).delete()
    session.query(Workspace).filter_by(id=workspace.id).delete()
    session.commit()


def test_freeze_persists_hash_and_uploads_blob(session, tmp_storage):
    from api.routes._freeze import freeze_approved_pdf
    version, ws = _make_approved_version(session)
    try:
        ok = freeze_approved_pdf(session, version)
        assert ok is True

        # Clave canónica tenant-scoped
        assert version.pdf_storage_key.startswith(f"workspaces/{ws.id}/")
        assert version.pdf_storage_key.endswith("/document.pdf")
        assert version.pdf_render_engine and "weasyprint" in version.pdf_render_engine
        assert version.pdf_generated_at is not None

        # El blob existe, es PDF, y su hash coincide con pdf_sha256
        blob = tmp_storage.get(version.pdf_storage_key)
        assert blob[:5] == b"%PDF-"
        assert hashlib.sha256(blob).hexdigest() == version.pdf_sha256
    finally:
        _cleanup(session, version, ws)


def test_freeze_is_idempotent(session, tmp_storage):
    from api.routes._freeze import freeze_approved_pdf
    version, ws = _make_approved_version(session)
    try:
        assert freeze_approved_pdf(session, version) is True
        key1, sha1 = version.pdf_storage_key, version.pdf_sha256
        # Segunda llamada: no re-renderiza, devuelve True y no cambia key/hash
        assert freeze_approved_pdf(session, version) is True
        assert version.pdf_storage_key == key1
        assert version.pdf_sha256 == sha1
    finally:
        _cleanup(session, version, ws)


def test_freeze_keys_are_tenant_scoped(session, tmp_storage):
    from api.routes._freeze import freeze_approved_pdf
    v_a, ws_a = _make_approved_version(session)
    v_b, ws_b = _make_approved_version(session)
    try:
        freeze_approved_pdf(session, v_a)
        freeze_approved_pdf(session, v_b)
        assert v_a.pdf_storage_key.startswith(f"workspaces/{ws_a.id}/")
        assert v_b.pdf_storage_key.startswith(f"workspaces/{ws_b.id}/")
        assert v_a.pdf_storage_key != v_b.pdf_storage_key
    finally:
        _cleanup(session, v_a, ws_a)
        _cleanup(session, v_b, ws_b)


def test_freeze_skips_non_approved(session, tmp_storage):
    from api.routes._freeze import freeze_approved_pdf
    version, ws = _make_approved_version(session)
    version.version_status = "DRAFT"
    try:
        assert freeze_approved_pdf(session, version) is False
        assert version.pdf_storage_key is None
    finally:
        version.version_status = "APPROVED"
        _cleanup(session, version, ws)
