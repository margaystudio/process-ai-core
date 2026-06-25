"""
Tests de la capa de almacenamiento de blobs (Fase A/F).

No requieren base de datos: prueban el contrato de `BlobStorage` sobre
`LocalDiskStorage`, la normalización/validación de claves y las claves canónicas.
"""

import tempfile

import pytest

from process_ai_core.storage import (
    normalize_key,
    version_asset_key,
    version_pdf_key,
)
from process_ai_core.storage.local import LocalDiskStorage


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as root:
        yield LocalDiskStorage(root=root)


# --- normalize_key -----------------------------------------------------------

def test_normalize_key_strips_leading_slash():
    assert normalize_key("/a/b/c") == "a/b/c"


def test_normalize_key_collapses_dot_segments():
    assert normalize_key("a/./b") == "a/b"


@pytest.mark.parametrize("bad", ["", "   ", "..", "a/../b", "../etc/passwd"])
def test_normalize_key_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_key(bad)


# --- contrato put/get/exists/delete -----------------------------------------

def test_put_get_roundtrip(storage):
    key = "workspaces/w1/documents/d1/versions/v1/document.pdf"
    storage.put(key, b"%PDF-1.4 data", content_type="application/pdf")
    assert storage.get(key) == b"%PDF-1.4 data"


def test_exists(storage):
    key = "a/b.txt"
    assert storage.exists(key) is False
    storage.put(key, b"x")
    assert storage.exists(key) is True


def test_get_missing_raises(storage):
    with pytest.raises(FileNotFoundError):
        storage.get("nope/missing.pdf")


def test_delete_is_idempotent(storage):
    key = "a/b.txt"
    storage.put(key, b"x")
    storage.delete(key)
    assert storage.exists(key) is False
    # borrar de nuevo no falla
    storage.delete(key)


def test_put_rejects_traversal(storage):
    with pytest.raises(ValueError):
        storage.put("../escape", b"x")


# --- claves canónicas (aislamiento multi-tenant) -----------------------------

def test_version_pdf_key_includes_workspace():
    key = version_pdf_key("ws-123", "doc-9", "ver-7")
    assert key == "workspaces/ws-123/documents/doc-9/versions/ver-7/document.pdf"


def test_version_asset_key_normalizes_ext():
    assert version_asset_key("ws", "d", "v", "img1", ".png").endswith("/assets/img1.png")
    assert version_asset_key("ws", "d", "v", "img1", "png").endswith("/assets/img1.png")


def test_keys_are_tenant_scoped():
    """La clave de un workspace nunca puede colisionar con la de otro."""
    a = version_pdf_key("ws-A", "doc", "ver")
    b = version_pdf_key("ws-B", "doc", "ver")
    assert a != b
    assert a.startswith("workspaces/ws-A/")
    assert b.startswith("workspaces/ws-B/")


# --- sync de run dir hacia storage -------------------------------------------

def test_sync_run_dir_noop_on_local_backend(tmp_path, monkeypatch):
    """Con backend local, sync es no-op (los archivos ya están en la raíz del storage)."""
    import process_ai_core.storage.sync as sync_mod
    from process_ai_core.config import get_settings

    monkeypatch.setattr(get_settings(), "storage_backend", "local", raising=False)
    (tmp_path / "process.json").write_text("{}")
    assert sync_mod.sync_run_dir_to_storage("ws1", "run1", tmp_path) == 0


def test_sync_run_dir_uploads_on_remote_backend(tmp_path, monkeypatch):
    """Con backend no-local, sube cada archivo bajo la clave {run_id}/..."""
    import process_ai_core.storage.sync as sync_mod
    import process_ai_core.config as cfg

    # Forzar backend no-local
    settings = cfg.get_settings()
    monkeypatch.setattr(settings, "storage_backend", "supabase", raising=False)

    # El store va FUERA del run_dir (en prod el storage root es el padre de los runs).
    captured = LocalDiskStorage(root=str(tmp_path / "store"))
    import process_ai_core.storage.factory as factory
    monkeypatch.setattr(factory, "get_storage", lambda: captured)

    run_dir = tmp_path / "run"
    (run_dir / "assets").mkdir(parents=True)
    (run_dir / "process.json").write_text("{}")
    (run_dir / "assets" / "img1.png").write_bytes(b"PNG")
    # Originales pesados que NO deben subirse a storage:
    (run_dir / "assets" / "vid1.mp4").write_bytes(b"VIDEO")
    (run_dir / "assets" / "vid1.m4a").write_bytes(b"AUDIO")

    n = sync_mod.sync_run_dir_to_storage("ws-A", "run-xyz", run_dir)
    assert n == 2  # solo json + png
    # Claves tenant-scoped: workspaces/{ws}/runs/{run_id}/...
    assert captured.exists("workspaces/ws-A/runs/run-xyz/process.json")
    assert captured.exists("workspaces/ws-A/runs/run-xyz/assets/img1.png")
    # Los originales de video/audio NO se persisten
    assert not captured.exists("workspaces/ws-A/runs/run-xyz/assets/vid1.mp4")
    assert not captured.exists("workspaces/ws-A/runs/run-xyz/assets/vid1.m4a")


# --- contabilidad (list_objects / usage por tenant) --------------------------

def test_list_objects_and_usage(storage):
    storage.put("workspaces/ws-A/runs/r1/a.json", b"12345")  # 5 bytes
    storage.put("workspaces/ws-A/runs/r1/assets/b.png", b"PNGDATA")  # 7 bytes
    storage.put("workspaces/ws-B/runs/r2/c.json", b"x")  # 1 byte (otro tenant)

    keys = {b.key for b in storage.list_objects("workspaces/ws-A")}
    assert keys == {
        "workspaces/ws-A/runs/r1/a.json",
        "workspaces/ws-A/runs/r1/assets/b.png",
    }
    # Uso por tenant aislado por prefijo
    assert storage.usage_bytes("workspaces/ws-A") == 12
    assert storage.usage_bytes("workspaces/ws-B") == 1


def test_workspace_usage_gb(tmp_path, monkeypatch):
    import process_ai_core.storage.accounting as acc
    store = LocalDiskStorage(root=str(tmp_path))
    monkeypatch.setattr(acc, "get_storage", lambda: store)

    store.put("workspaces/ws-A/runs/r1/big.pdf", b"x" * 1_000_000)  # 1 MB
    assert abs(acc.workspace_usage_gb("ws-A") - 0.001) < 1e-9  # 1 MB = 0.001 GB
    assert acc.workspace_usage_gb("ws-Z") == 0.0  # sin objetos


# --- delete_prefix (E3) -------------------------------------------------------

def test_delete_prefix(storage):
    storage.put("workspaces/ws-A/runs/r1/a.json", b"1")
    storage.put("workspaces/ws-A/runs/r1/assets/b.png", b"2")
    storage.put("workspaces/ws-A/runs/r2/c.json", b"3")  # otro run, no se toca

    n = storage.delete_prefix("workspaces/ws-A/runs/r1")
    assert n == 2
    assert not storage.exists("workspaces/ws-A/runs/r1/a.json")
    assert not storage.exists("workspaces/ws-A/runs/r1/assets/b.png")
    # El otro run sigue intacto
    assert storage.exists("workspaces/ws-A/runs/r2/c.json")


def test_delete_prefix_missing_is_zero(storage):
    assert storage.delete_prefix("workspaces/ws-X/runs/nope") == 0
