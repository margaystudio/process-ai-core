"""
Freeze diferible, barrido de pendientes y la garantía que sostienen entre los dos.

La regla que fijan estos tests: **una versión APROBADA termina teniendo su PDF
congelado, la mire alguien o no.** El freeze puede diferirse (aprobación en lote)
o fallar (storage caído), pero no puede quedar pendiente para siempre — el
artefacto de auditoría existe para estar disponible el día que alguien pregunte,
y atarlo a que alguien abra el PDF es no tenerlo.

Se cubre el escenario completo de la aprobación por lote: 50 documentos aprobados
sin congelar, el barrido después, y la apertura bajo demanda de uno cualquiera
antes del barrido (que no debe duplicar trabajo).
"""

import hashlib
import uuid
from contextlib import contextmanager

import pytest

from api.routes import _freeze as freeze_mod
from api.routes._freeze import count_versions_pending_freeze, freeze_pending_versions
from api.routes.documents import versions as versions_mod
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion, Folder, Process, Workspace
from process_ai_core.storage.local import LocalDiskStorage

#: Tamaño del lote en el test que reproduce el escenario real de la tarea.
LOTE = 50
#: El resto usa un lote chico a propósito. Cada versión cuesta un render de
#: PDF de verdad (~0,5 s): con 50 en cada test la suite se iba a diez minutos
#: para volver a probar lo mismo. El escenario de 50 se corre una sola vez.
LOTE_CHICO = 6


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture
def storage(tmp_path, monkeypatch):
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    monkeypatch.setattr(freeze_mod, "get_storage", lambda: store)
    monkeypatch.setattr(versions_mod, "get_storage", lambda: store)
    return store


@pytest.fixture
def lote(request, session, monkeypatch):
    """
    Un workspace con N documentos aprobados y SIN pdf_storage_key.

    N sale del marcador `@pytest.mark.lote(n)`; por defecto LOTE_CHICO.
    """
    marcador = request.node.get_closest_marker("lote")
    cantidad = marcador.args[0] if marcador else LOTE_CHICO
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(
        id=f"lote-ws-{uid}", slug=f"lote-ws-{uid}", name="Lote",
        workspace_type="organization",
    )
    session.add(ws)
    session.flush()
    folder = Folder(id=f"lote-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder)
    session.flush()

    versiones = []
    for i in range(cantidad):
        doc = Process(
            id=f"lote-doc-{uid}-{i:02d}", workspace_id=ws.id, folder_id=folder.id,
            document_type="process", name=f"Documento {i}", status="approved",
        )
        session.add(doc)
        session.flush()
        version = DocumentVersion(
            id=f"lote-ver-{uid}-{i:02d}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="generated",
            content_json="{}", content_markdown=f"# Documento {i}",
            content_html=f"<h1>Documento {i}</h1><p>Contenido del documento {i}.</p>",
            is_current=True,
        )
        session.add(version)
        versiones.append(version)
    session.commit()

    @contextmanager
    def fake_db_session():
        yield session

    monkeypatch.setattr(versions_mod, "get_db_session", fake_db_session)
    monkeypatch.setattr(versions_mod, "resolve_tenant_workspace_id", lambda ctx: ws.id)

    yield ws, versiones

    ids = [v.id for v in versiones]
    doc_ids = [v.document_id for v in versiones]
    session.query(DocumentVersion).filter(DocumentVersion.id.in_(ids)).delete(
        synchronize_session=False
    )
    session.query(Process).filter(Process.id.in_(doc_ids)).delete(synchronize_session=False)
    session.query(Document).filter(Document.id.in_(doc_ids)).delete(synchronize_session=False)
    session.query(Folder).filter_by(workspace_id=ws.id).delete()
    session.query(Workspace).filter_by(id=ws.id).delete()
    session.commit()


# ── El escenario completo del lote ───────────────────────────────────────────


@pytest.mark.lote(LOTE)
def test_el_lote_queda_aprobado_sin_congelar_y_el_barrido_lo_completa(
    session, storage, lote
):
    """
    Las tres etapas del camino que habilita `defer_freeze`, en orden:
    aprobado sin artefacto -> barrido -> artefacto con su sha256.
    """
    ws, versiones = lote
    n = len(versiones)

    # 1. Estado tras aprobar en lote: 50 APPROVED, ninguna congelada.
    assert count_versions_pending_freeze(session, ws.id) == n
    assert all(v.pdf_storage_key is None for v in versiones)

    # 2. El barrido.
    resultado = freeze_pending_versions(session, limit=n, workspace_id=ws.id)
    assert resultado["congeladas"] == n, resultado
    assert resultado["fallidas"] == 0, resultado

    # 3. Las 50 quedan con su blob y con el sha256 del blob, no de otra cosa.
    assert count_versions_pending_freeze(session, ws.id) == 0
    for version in versiones:
        session.refresh(version)
        assert version.pdf_storage_key, f"{version.id} quedó sin clave"
        assert version.pdf_sha256, f"{version.id} quedó sin hash"
        blob = storage.get(version.pdf_storage_key)
        assert blob.startswith(b"%PDF"), f"{version.id} no guardó un PDF"
        assert hashlib.sha256(blob).hexdigest() == version.pdf_sha256, (
            f"el hash de {version.id} no identifica al blob guardado"
        )


def test_el_barrido_es_idempotente(session, storage, lote):
    """Correrlo de nuevo no re-renderiza ni cambia los hashes ya registrados."""
    ws, versiones = lote
    freeze_pending_versions(session, limit=len(versiones), workspace_id=ws.id)
    hashes = {}
    for version in versiones:
        session.refresh(version)
        hashes[version.id] = version.pdf_sha256

    segunda = freeze_pending_versions(session, limit=len(versiones), workspace_id=ws.id)
    assert segunda["candidatas"] == 0
    assert segunda["congeladas"] == 0

    for version in versiones:
        session.refresh(version)
        assert version.pdf_sha256 == hashes[version.id]


def test_abrir_el_pdf_antes_del_barrido_congela_y_el_barrido_no_lo_repite(
    session, storage, lote
):
    """
    El freeze bajo demanda y el barrido cubren el mismo agujero por caminos
    distintos; lo que no pueden es pisarse. El que llega segundo tiene que ver
    el trabajo del primero y no rehacerlo.
    """
    ws, versiones = lote
    n = len(versiones)
    elegida = versiones[2]

    assert freeze_mod.freeze_approved_pdf(session, elegida) is True
    session.commit()
    session.refresh(elegida)
    key_bajo_demanda = elegida.pdf_storage_key
    sha_bajo_demanda = elegida.pdf_sha256
    assert key_bajo_demanda

    assert count_versions_pending_freeze(session, ws.id) == n - 1

    resultado = freeze_pending_versions(session, limit=n, workspace_id=ws.id)
    assert resultado["candidatas"] == n - 1, "el barrido volvió a agarrar la ya congelada"
    assert resultado["congeladas"] == n - 1

    session.refresh(elegida)
    assert elegida.pdf_storage_key == key_bajo_demanda
    assert elegida.pdf_sha256 == sha_bajo_demanda, "el barrido re-escribió un artefacto ya emitido"


def test_el_barrido_respeta_el_limite(session, storage, lote):
    """Lotes acotados: el barrido no intenta congelar la cola entera de una."""
    ws, versiones = lote
    tope = len(versiones) - 2
    resultado = freeze_pending_versions(session, limit=tope, workspace_id=ws.id)
    assert resultado["congeladas"] == tope
    assert count_versions_pending_freeze(session, ws.id) == 2


def test_una_version_que_falla_no_se_lleva_puesto_el_resto(
    session, storage, lote, monkeypatch
):
    """
    Cada versión va en su propia transacción. Un documento con una evidencia
    faltante aborta SU freeze —que es lo correcto— pero el barrido sigue.
    """
    ws, versiones = lote
    n = len(versiones)
    rota = versiones[3].id
    original = freeze_mod.freeze_approved_pdf

    def freeze_selectivo(session_, version, *args, **kwargs):
        if version.id == rota:
            raise RuntimeError("evidencia faltante")
        return original(session_, version, *args, **kwargs)

    monkeypatch.setattr(freeze_mod, "freeze_approved_pdf", freeze_selectivo)

    resultado = freeze_pending_versions(session, limit=n, workspace_id=ws.id)
    assert resultado["fallidas"] == 1
    assert resultado["congeladas"] == n - 1
    assert count_versions_pending_freeze(session, ws.id) == 1


def test_el_dry_run_no_congela_nada(session, storage, lote):
    ws, versiones = lote
    n = len(versiones)
    resultado = freeze_pending_versions(session, limit=n, workspace_id=ws.id, dry_run=True)
    assert resultado["candidatas"] == n
    assert resultado["congeladas"] == 0
    assert len(resultado["ids"]) == n
    assert count_versions_pending_freeze(session, ws.id) == n


# ── El parámetro que habilita todo esto ──────────────────────────────────────


def test_defer_freeze_por_defecto_es_false():
    """
    Una aprobación individual sigue saliendo con su artefacto listo. El default
    no cambia: diferir es una decisión que toma quien aprueba en lote.
    """
    from api.routes.validations import ValidationApproveRequest

    assert ValidationApproveRequest().defer_freeze is False
    assert ValidationApproveRequest(defer_freeze=True).defer_freeze is True
