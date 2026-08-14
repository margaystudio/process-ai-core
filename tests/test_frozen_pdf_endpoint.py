"""
Tests del endpoint que sirve el PDF congelado de una versión (artefacto de auditoría).

Contrato que se verifica:
  - APPROVED sirve los bytes del blob de storage y NO invoca el renderer.
  - APPROVED responde con ETag = SHA-256 registrado y Cache-Control inmutable,
    y devuelve 304 ante un If-None-Match que coincide.
  - APPROVED sin `pdf_storage_key` reintenta el freeze (que al aprobar es
    best-effort, ver api/routes/_freeze.py) y sirve el resultado; si el reintento
    falla, devuelve 404 en vez de caer al render on-the-fly.
  - preview-pdf redirige (307) al congelado cuando la versión ya está aprobada.
  - preview-pdf de un DRAFT sigue regenerando el PDF con no-store.
  - Un PDF importado (clave `.../source/archivo.pdf`) se sirve por el mismo camino.
  - Dos reintentos de freeze concurrentes producen UN solo render (lock de fila).
  - Un usuario sin acceso al documento no recibe el PDF, ni siquiera con un ETag
    válido en mano: la autorización corre antes que el atajo del 304.

Complementa tests/test_freeze_integration.py, que cubre el congelado en sí, y
tests/test_pdf_reproducibility.py, que cubre que el render sea determinístico.
"""

import asyncio
import hashlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routes.documents import versions as versions_mod
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Document,
    DocumentVersion,
    Folder,
    Process,
    User,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.storage.local import LocalDiskStorage

PDF_BYTES = b"%PDF-1.4\n% blob congelado\n%%EOF\n"


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Storage temporal, compartido por el endpoint y por el freeze."""
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    import api.routes._freeze as freeze_mod

    monkeypatch.setattr(versions_mod, "get_storage", lambda: store)
    monkeypatch.setattr(freeze_mod, "get_storage", lambda: store)
    return store


def _fake_request(headers: dict | None = None):
    """Sustituto de fastapi.Request: el endpoint solo lee `request.headers`."""
    return SimpleNamespace(headers=headers or {})


def _make_version(session, monkeypatch, *, status="APPROVED", **version_kwargs):
    """Crea workspace + folder + documento + versión, y engancha el tenant activo."""
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(id=f"pdf-ws-{uid}", slug=f"pdf-ws-{uid}", name="PDF", workspace_type="organization")
    session.add(ws)
    session.flush()
    folder = Folder(id=f"pdf-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder)
    session.flush()
    doc = Process(
        id=f"pdf-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
        document_type="process", name="PDF Doc", status="approved",
    )
    session.add(doc)
    session.flush()
    version = DocumentVersion(
        id=f"pdf-ver-{uid}", document_id=doc.id, version_number=3,
        version_status=status, content_type="generated",
        content_json="{}", content_markdown="# Doc",
        content_html="<h1>Doc</h1><p>contenido</p>",
        is_current=status == "APPROVED",
        **version_kwargs,
    )
    session.add(version)
    session.flush()

    # Usuario con acceso: el endpoint exige identidad + permiso por carpeta
    # (base_access 'admin' ⇒ bypass del permiso operativo, como en producción).
    user = User(id=f"pdf-usr-{uid}", email=f"pdf-{uid}@test.io", name="PDF User")
    session.add(user)
    session.flush()
    session.add(
        WorkspaceMembership(
            id=f"pdf-mem-{uid}", user_id=user.id, workspace_id=ws.id, base_access="admin"
        )
    )
    session.flush()

    @contextmanager
    def fake_db_session():
        yield session

    monkeypatch.setattr(versions_mod, "get_db_session", fake_db_session)
    monkeypatch.setattr(versions_mod, "resolve_tenant_workspace_id", lambda ctx: ws.id)
    return version, ws, user.id


def _cleanup(session, version, workspace):
    session.query(DocumentVersion).filter_by(id=version.id).delete()
    session.query(Process).filter_by(id=version.document_id).delete()
    session.query(Document).filter_by(id=version.document_id).delete()
    session.query(Folder).filter_by(workspace_id=workspace.id).delete()
    session.query(WorkspaceMembership).filter_by(workspace_id=workspace.id).delete()
    session.query(Workspace).filter_by(id=workspace.id).delete()
    session.commit()


def _explode(*args, **kwargs):
    raise AssertionError("no se debe renderizar el PDF de una versión congelada")


# ── APPROVED: sirve el blob, sin renderer ──────────────────────────────────────


def test_approved_sirve_el_blob_congelado_sin_renderizar(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    storage.put(key, PDF_BYTES, content_type="application/pdf")
    version.pdf_storage_key = key
    version.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    session.flush()

    # Ni el renderer ni el freeze deben tocarse: el artefacto ya existe.
    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)
    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", _explode)

    try:
        response = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        assert response.status_code == 200
        assert response.body == PDF_BYTES
        assert response.headers["content-type"] == "application/pdf"
        assert "inline" in response.headers["content-disposition"]
        assert response.headers["cache-control"] == "private, no-cache"
        assert response.headers["etag"] == f'"{version.pdf_sha256}"'
    finally:
        _cleanup(session, version, ws)


def test_approved_devuelve_304_con_etag_coincidente(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    storage.put(key, PDF_BYTES, content_type="application/pdf")
    sha = hashlib.sha256(PDF_BYTES).hexdigest()
    version.pdf_storage_key = key
    version.pdf_sha256 = sha
    session.flush()

    try:
        response = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request({"if-none-match": f'"{sha}"'}),
            user_id=user_id, ctx=None,
        )
        assert response.status_code == 304
        assert response.body == b""
    finally:
        _cleanup(session, version, ws)


def test_pdf_importado_se_sirve_por_el_mismo_camino(session, storage, monkeypatch):
    """document_import guarda el archivo fuente como pdf_storage_key (no document.pdf)."""
    version, ws, user_id = _make_version(session, monkeypatch)
    key = (
        f"workspaces/{ws.id}/documents/{version.document_id}"
        f"/versions/{version.id}/source/manual de calidad.pdf"
    )
    storage.put(key, PDF_BYTES, content_type="application/pdf")
    version.pdf_storage_key = key
    version.source_file_key = key
    version.source_file_name = "manual de calidad.pdf"
    version.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    version.pdf_render_engine = "imported"
    session.flush()

    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)

    try:
        response = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        assert response.body == PDF_BYTES
        # Conserva el nombre del archivo original en la descarga.
        assert 'filename="manual de calidad.pdf"' in response.headers["content-disposition"]
    finally:
        _cleanup(session, version, ws)


# ── Descarga (?download=1) ────────────────────────────────────────────────────


def _pdf_de_una_pagina() -> bytes:
    """PDF real (no un blob de mentira): el sello lo tiene que poder abrir."""
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((60, 100), "Documento aprobado", fontsize=14)
    salida = doc.tobytes()
    doc.close()
    return salida


def test_download_cambia_la_disposicion_a_attachment(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    storage.put(key, PDF_BYTES, content_type="application/pdf")
    version.pdf_storage_key = key
    version.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    session.flush()

    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)

    try:
        vista = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id, version_id=version.id,
            request=_fake_request(), user_id=user_id, ctx=None,
        )
        descarga = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id, version_id=version.id,
            request=_fake_request(), download=True, user_id=user_id, ctx=None,
        )

        assert "inline" in vista.headers["content-disposition"]
        assert "attachment" in descarga.headers["content-disposition"]
        # Los MISMOS bytes: `download` solo cambia el header.
        assert descarga.body == vista.body == PDF_BYTES
        # Y NO comparten ETag: si lo hicieran, pedir la descarga después de haber
        # abierto el PDF respondería 304 y el navegador reusaría la entrada
        # cacheada —la que dice `inline`— abriéndolo en vez de guardarlo.
        assert descarga.headers["etag"] != vista.headers["etag"]
    finally:
        _cleanup(session, version, ws)


def test_la_descarga_de_una_version_superada_lleva_el_sello(session, storage, monkeypatch):
    """
    Es el caso donde el sello más importa: el archivo descargado es el que
    circula por fuera del sistema, y tiene que decir por sí solo que ya no rige.
    """
    import fitz

    version, ws, user_id = _make_version(session, monkeypatch, status="OBSOLETE")
    version.is_current = False
    pdf_original = _pdf_de_una_pagina()
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    storage.put(key, pdf_original, content_type="application/pdf")
    version.pdf_storage_key = key
    version.pdf_sha256 = hashlib.sha256(pdf_original).hexdigest()
    session.flush()

    # La versión que la superó: sin una vigente no hay nada que sellar.
    vigente = DocumentVersion(
        id=f"{version.id}-v4", document_id=version.document_id, version_number=4,
        version_status="APPROVED", content_type="generated",
        content_json="{}", content_markdown="# Doc", is_current=True,
    )
    session.add(vigente)
    session.flush()

    try:
        descarga = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id, version_id=version.id,
            request=_fake_request(), download=True, user_id=user_id, ctx=None,
        )

        assert "attachment" in descarga.headers["content-disposition"]
        assert descarga.headers["X-Document-Stamped"] == "superseded"
        # El sello está en los bytes que se descargan, no solo en un header.
        doc = fitz.open(stream=descarga.body, filetype="pdf")
        try:
            texto = doc[0].get_text()
        finally:
            doc.close()
        assert "VERSIÓN SUPERADA" in texto
        assert "vigente: v4" in texto

        # El artefacto en storage NO se tocó: su hash registrado sigue valiendo.
        assert storage.get(key) == pdf_original
        assert descarga.headers["X-Document-SHA256"] == version.pdf_sha256

        # Y una versión aprobada vigente se descarga SIN sello.
        aprobada = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id, version_id=vigente.id,
            request=_fake_request(), download=True, user_id=user_id, ctx=None,
        )
        assert "X-Document-Stamped" not in aprobada.headers
    finally:
        session.query(DocumentVersion).filter_by(id=vigente.id).delete()
        _cleanup(session, version, ws)


# ── APPROVED sin blob: reintento del freeze ───────────────────────────────────


def test_approved_sin_storage_key_reintenta_el_freeze(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    assert version.pdf_storage_key is None
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    calls = []

    def fake_freeze(sess, ver, api_base=None):
        calls.append(ver.id)
        storage.put(key, PDF_BYTES, content_type="application/pdf")
        ver.pdf_storage_key = key
        ver.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
        return True

    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", fake_freeze)

    try:
        response = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        assert calls == [version.id], "debe reintentar el freeze exactamente una vez"
        assert response.status_code == 200
        assert response.body == PDF_BYTES
        assert version.pdf_storage_key == key
    finally:
        _cleanup(session, version, ws)


def test_approved_con_freeze_fallido_devuelve_404_y_no_regenera(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", lambda *a, **k: False)
    # Caer al render on-the-fly sería justo el bug que este endpoint evita.
    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)

    try:
        with pytest.raises(HTTPException) as exc:
            versions_mod.get_version_frozen_pdf(
                document_id=version.document_id,
                version_id=version.id,
                request=_fake_request(),
                user_id=user_id, ctx=None,
            )
        assert exc.value.status_code == 404
        assert "congelado" in exc.value.detail
    finally:
        _cleanup(session, version, ws)


def test_draft_no_tiene_pdf_congelado(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch, status="DRAFT")
    # Un DRAFT nunca se congela: no debe intentar el freeze.
    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", _explode)

    try:
        with pytest.raises(HTTPException) as exc:
            versions_mod.get_version_frozen_pdf(
                document_id=version.document_id,
                version_id=version.id,
                request=_fake_request(),
                user_id=user_id, ctx=None,
            )
        assert exc.value.status_code == 404
        assert "preview-pdf" in exc.value.detail
    finally:
        _cleanup(session, version, ws)


# ── preview-pdf: redirige lo congelado, regenera lo editable ──────────────────


def test_preview_pdf_de_version_aprobada_redirige_al_congelado(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)

    try:
        response = asyncio.run(
            versions_mod.get_version_preview_pdf(
                document_id=version.document_id,
                version_id=version.id,
                user_id=user_id, ctx=None,
            )
        )
        assert response.status_code == 307
        assert response.headers["location"] == (
            f"/api/v1/documents/{version.document_id}/versions/{version.id}/pdf"
        )
    finally:
        _cleanup(session, version, ws)


def test_preview_pdf_de_obsolete_congelada_redirige_al_congelado(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch, status="OBSOLETE")
    version.pdf_storage_key = "workspaces/x/documents/y/versions/z/document.pdf"
    session.flush()
    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)

    try:
        response = asyncio.run(
            versions_mod.get_version_preview_pdf(
                document_id=version.document_id,
                version_id=version.id,
                user_id=user_id, ctx=None,
            )
        )
        assert response.status_code == 307
    finally:
        _cleanup(session, version, ws)


def test_la_redireccion_del_preview_no_pierde_el_parametro_de_descarga(
    session, storage, monkeypatch
):
    """
    Para una versión OBSOLETE la UI pide el preview (no sabe si hay artefacto
    congelado) y el backend redirige. Si `download` se perdiera en el salto, el
    archivo se serviría `inline` justo en el caso donde la descarga más importa:
    el de la versión superada, que es la que lleva el sello.
    """
    version, ws, user_id = _make_version(session, monkeypatch, status="OBSOLETE")
    version.pdf_storage_key = "workspaces/x/documents/y/versions/z/document.pdf"
    session.flush()
    monkeypatch.setattr(versions_mod, "export_pdf_from_content", _explode)

    try:
        response = asyncio.run(
            versions_mod.get_version_preview_pdf(
                document_id=version.document_id,
                version_id=version.id,
                download=True,
                user_id=user_id, ctx=None,
            )
        )
        assert response.status_code == 307
        assert response.headers["location"].endswith("/pdf?download=1")
    finally:
        _cleanup(session, version, ws)


def test_preview_pdf_de_draft_sigue_regenerando(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch, status="DRAFT")
    rendered = []

    def fake_render(*, content, format, run_dir, pdf_name, **kwargs):
        rendered.append({"format": format, "content": content, **kwargs})
        path = Path(run_dir) / pdf_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PDF_BYTES)
        return path

    monkeypatch.setattr(versions_mod, "export_pdf_from_content", fake_render)

    try:
        response = asyncio.run(
            versions_mod.get_version_preview_pdf(
                document_id=version.document_id,
                version_id=version.id,
                user_id=user_id, ctx=None,
            )
        )
        assert len(rendered) == 1, "el DRAFT debe re-renderizarse en cada request"
        assert rendered[0]["format"] == "html"
        # El preview también recibe el contexto, marcado como NO aprobado.
        ctx = rendered[0].get("document_context")
        assert ctx is not None and ctx.is_approved is False
        assert response.status_code == 200
        assert response.body == PDF_BYTES
        assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    finally:
        _cleanup(session, version, ws)


# ── Política de cache y control de acceso ─────────────────────────────────────


def test_cache_control_revalida_en_vez_de_congelar_el_permiso(session, storage, monkeypatch):
    """
    `immutable` haría que el navegador sirviera el PDF hasta un año sin tocar el
    servidor: a un usuario con el acceso revocado le seguiría abriendo. Con
    `no-cache` el blob se cachea igual, pero cada apertura revalida.
    """
    version, ws, user_id = _make_version(session, monkeypatch)
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    storage.put(key, PDF_BYTES, content_type="application/pdf")
    version.pdf_storage_key = key
    version.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    session.flush()

    try:
        response = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        cache_control = response.headers["cache-control"]
        assert cache_control == "private, no-cache"
        assert "immutable" not in cache_control
        assert "max-age" not in cache_control
        # El ETag se conserva: es lo que permite resolver la revalidación en 304.
        assert response.headers["etag"] == f'"{version.pdf_sha256}"'
    finally:
        _cleanup(session, version, ws)


def test_sin_acceso_al_documento_no_se_sirve_el_pdf_ni_con_etag_valido(
    session, storage, monkeypatch
):
    """
    Un usuario que abrió el PDF antes tiene el ETag correcto en su cache. Si le
    revocan el acceso (o cambia de workspace activo), la revalidación NO puede
    resolverse en 304: la autorización corre antes que el atajo del ETag.
    """
    version, ws, user_id = _make_version(session, monkeypatch)
    key = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    storage.put(key, PDF_BYTES, content_type="application/pdf")
    sha = hashlib.sha256(PDF_BYTES).hexdigest()
    version.pdf_storage_key = key
    version.pdf_sha256 = sha
    session.flush()

    try:
        # Con acceso: 200 y el blob.
        ok = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        assert ok.status_code == 200 and ok.body == PDF_BYTES

        # Se revoca el acceso: el workspace activo pasa a ser otro.
        monkeypatch.setattr(
            versions_mod, "resolve_tenant_workspace_id", lambda ctx: "otro-workspace"
        )

        # Sin condicional → 404, no el PDF.
        with pytest.raises(HTTPException) as exc:
            versions_mod.get_version_frozen_pdf(
                document_id=version.document_id,
                version_id=version.id,
                request=_fake_request(),
                user_id=user_id, ctx=None,
            )
        assert exc.value.status_code in (403, 404)

        # Con el ETag que quedó en su cache → sigue siendo 404, NUNCA 304.
        with pytest.raises(HTTPException) as exc_etag:
            versions_mod.get_version_frozen_pdf(
                document_id=version.document_id,
                version_id=version.id,
                request=_fake_request({"if-none-match": f'"{sha}"'}),
                user_id=user_id, ctx=None,
            )
        assert exc_etag.value.status_code in (403, 404)
    finally:
        monkeypatch.setattr(versions_mod, "resolve_tenant_workspace_id", lambda ctx: ws.id)
        _cleanup(session, version, ws)


# ── Concurrencia: el reintento de freeze se serializa con lock de fila ────────


def _crear_version_aprobada_committeada():
    """
    Crea los datos EN LA BASE y commitea. A diferencia del resto del archivo no
    se comparte una sesión: el test de concurrencia necesita que cada thread abra
    su propia transacción, que es donde el SELECT ... FOR UPDATE tiene efecto.
    """
    uid = str(uuid.uuid4())[:8]
    with get_db_session() as s:
        ws = Workspace(
            id=f"cc-ws-{uid}", slug=f"cc-ws-{uid}", name="CC", workspace_type="organization"
        )
        s.add(ws)
        s.flush()
        folder = Folder(id=f"cc-fol-{uid}", workspace_id=ws.id, name="root", path="root")
        s.add(folder)
        s.flush()
        doc = Process(
            id=f"cc-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
            document_type="process", name="CC Doc", status="approved",
        )
        s.add(doc)
        s.flush()
        ver = DocumentVersion(
            id=f"cc-ver-{uid}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="generated",
            content_json="{}", content_markdown="# Doc",
            content_html="<h1>Doc concurrente</h1><p>contenido</p>",
            is_current=True,
        )
        s.add(ver)
        s.flush()
        user = User(id=f"cc-usr-{uid}", email=f"cc-{uid}@test.io", name="CC User")
        s.add(user)
        s.flush()
        s.add(WorkspaceMembership(
            id=f"cc-mem-{uid}", user_id=user.id, workspace_id=ws.id, base_access="admin"
        ))
        s.flush()
        return ws.id, doc.id, ver.id, user.id


def _borrar_version_committeada(workspace_id, document_id, version_id):
    with get_db_session() as s:
        s.query(DocumentVersion).filter_by(id=version_id).delete()
        s.query(Process).filter_by(id=document_id).delete()
        s.query(Document).filter_by(id=document_id).delete()
        s.query(WorkspaceMembership).filter_by(workspace_id=workspace_id).delete()
        s.query(Folder).filter_by(workspace_id=workspace_id).delete()
        s.query(Workspace).filter_by(id=workspace_id).delete()


def test_dos_requests_concurrentes_producen_un_solo_render(storage, monkeypatch):
    """
    Sin el lock, ambos requests pasan el chequeo de `pdf_storage_key is None`,
    ambos renderizan y ambos hacen put() sobre la misma clave: el pdf_sha256 que
    queda persistido puede ser el de los bytes del render PERDEDOR.

    Con el lock: un solo render, y el hash persistido coincide con el blob.
    """
    import api.routes._freeze as freeze_mod

    workspace_id, document_id, version_id, user_id = _crear_version_aprobada_committeada()

    # Se cuenta el render real (no las llamadas a freeze_approved_pdf, que
    # retorna temprano si ya hay key). El sleep ensancha la ventana de carrera.
    renders = []
    lock = threading.Lock()
    render_real = freeze_mod.export_pdf_from_content

    def contar_render(**kwargs):
        with lock:
            renders.append(kwargs.get("pdf_name"))
        time.sleep(0.6)
        return render_real(**kwargs)

    monkeypatch.setattr(freeze_mod, "export_pdf_from_content", contar_render)
    monkeypatch.setattr(versions_mod, "resolve_tenant_workspace_id", lambda ctx: workspace_id)
    # NO se parchea get_db_session: cada thread necesita su propia transacción.

    def pedir_pdf():
        return versions_mod.get_version_frozen_pdf(
            document_id=document_id,
            version_id=version_id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(pedir_pdf), pool.submit(pedir_pdf)]
            respuestas = [f.result(timeout=120) for f in futuros]

        assert len(renders) == 1, (
            f"se renderizó {len(renders)} veces: el reintento de freeze no quedó "
            "serializado y dos requests escribieron sobre la misma clave"
        )

        # Ambos devuelven el MISMO artefacto.
        assert all(r.status_code == 200 for r in respuestas)
        assert respuestas[0].body == respuestas[1].body
        assert respuestas[0].body[:5] == b"%PDF-"

        # Y el hash persistido corresponde a los bytes que quedaron en storage.
        with get_db_session() as s:
            ver = s.query(DocumentVersion).filter_by(id=version_id).one()
            key, sha = ver.pdf_storage_key, ver.pdf_sha256
        assert key, "el freeze no persistió la clave"
        blob = storage.get(key)
        assert hashlib.sha256(blob).hexdigest() == sha
        assert blob == respuestas[0].body
    finally:
        _borrar_version_committeada(workspace_id, document_id, version_id)


# ── El artefacto registrado desapareció del storage ───────────────────────────
#
# Encontrado recorriendo el ambiente de test: dos documentos APROBADOS tenían su
# `pdf_storage_key` en la base y el blob no existía (se habían congelado cuando
# el storage era el disco efímero del contenedor). El endpoint devolvía 404 para
# siempre y el barrido de pendientes NO los veía —tienen key—, así que nada en el
# sistema se enteraba de que un documento aprobado se había quedado sin evidencia.


def _freeze_falso(storage, contenido=b"%PDF-1.4\n% regenerado\n%%EOF\n"):
    """Sustituto del freeze real: escribe un blob y registra key + hash.

    Se reemplaza el render porque lo que se está probando es la RECUPERACIÓN,
    no WeasyPrint (eso vive en test_freeze_integration.py).
    """
    def _fake(session, version, **kwargs):
        key = (
            f"workspaces/regen/documents/{version.document_id}/"
            f"versions/{version.id}/document.pdf"
        )
        storage.put(key, contenido, content_type="application/pdf")
        version.pdf_storage_key = key
        version.pdf_sha256 = hashlib.sha256(contenido).hexdigest()
        return True

    return _fake


def test_si_el_blob_desaparecio_se_regenera_en_vez_de_404_eterno(
    session, storage, monkeypatch
):
    version, ws, user_id = _make_version(session, monkeypatch)
    perdida = f"workspaces/{ws.id}/documents/{version.document_id}/versions/{version.id}/document.pdf"
    version.pdf_storage_key = perdida  # registrada…
    version.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    session.flush()
    # …pero el blob NO está en storage (nunca se hace put).

    regenerado = b"%PDF-1.4\n% regenerado\n%%EOF\n"
    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", _freeze_falso(storage, regenerado))

    try:
        response = versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        assert response.status_code == 200
        assert response.body == regenerado

        # El hash servido es el del artefacto NUEVO, no el del que se perdió:
        # servir los bytes nuevos bajo el hash viejo sería peor que el 404.
        nuevo_sha = hashlib.sha256(regenerado).hexdigest()
        assert response.headers["x-document-sha256"] == nuevo_sha
        assert response.headers["etag"] == f'"{nuevo_sha}"'
        assert version.pdf_sha256 == nuevo_sha
    finally:
        from process_ai_core.db.models import AuditLog

        session.query(AuditLog).filter_by(document_id=version.document_id).delete()
        _cleanup(session, version, ws)


def test_la_regeneracion_queda_asentada_en_el_audit_log(session, storage, monkeypatch):
    """El hash cambia: una copia impresa vieja va a verificar distinto. Que el
    artefacto haya cambiado tiene que ser un hecho registrado, no una corrección
    invisible."""
    from process_ai_core.db.models import AuditLog

    version, ws, user_id = _make_version(session, monkeypatch)
    sha_viejo = hashlib.sha256(PDF_BYTES).hexdigest()
    version.pdf_storage_key = f"workspaces/{ws.id}/perdido.pdf"
    version.pdf_sha256 = sha_viejo
    session.flush()

    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", _freeze_falso(storage))

    try:
        versions_mod.get_version_frozen_pdf(
            document_id=version.document_id,
            version_id=version.id,
            request=_fake_request(),
            user_id=user_id,
            ctx=None,
        )
        evento = (
            session.query(AuditLog)
            .filter_by(document_id=version.document_id, action="pdf_artefacto_regenerado")
            .one()
        )
        assert evento.entity_id == version.id
        assert sha_viejo in evento.changes_json
        assert version.pdf_sha256 in evento.changes_json
    finally:
        session.query(AuditLog).filter_by(document_id=version.document_id).delete()
        _cleanup(session, version, ws)


def test_si_tampoco_se_puede_regenerar_el_404_lo_dice(session, storage, monkeypatch):
    version, ws, user_id = _make_version(session, monkeypatch)
    version.pdf_storage_key = f"workspaces/{ws.id}/perdido.pdf"
    version.pdf_sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    session.flush()

    monkeypatch.setattr(versions_mod, "freeze_approved_pdf", lambda *a, **k: False)

    try:
        with pytest.raises(HTTPException) as exc:
            versions_mod.get_version_frozen_pdf(
                document_id=version.document_id,
                version_id=version.id,
                request=_fake_request(),
                user_id=user_id,
                ctx=None,
            )
        assert exc.value.status_code == 404
        assert "no se pudo regenerar" in exc.value.detail
    finally:
        _cleanup(session, version, ws)
