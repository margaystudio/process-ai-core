"""
Codificación documental (ADR-019), vigencia de la aprobación y verificación pública.

Los tres se testean juntos porque son la misma cadena: el código y la vigencia se
fijan una vez y quedan impresos en un PDF inmutable, y la página de verificación
es el puente entre ese papel y el estado mutable del sistema.
"""

import datetime
import uuid

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.document_codes import (
    CODE_PADDING,
    assign_document_code,
    code_prefix_for,
    derive_prefix,
    format_code,
    generate_document_code,
)
from process_ai_core.db.helpers import _add_months, workspace_default_validity_months
from process_ai_core.db.models import (
    AuditLog,
    Document,
    DocumentCodeCounter,
    DocumentType,
    DocumentVersion,
    Folder,
    Process,
    User,
    Workspace,
)


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


def _crear_workspace(session, *, con_tipos=True):
    uid = uuid.uuid4().hex[:8]
    ws = Workspace(
        id=f"cd-ws-{uid}", slug=f"cd-ws-{uid}", name="ACME", workspace_type="organization"
    )
    session.add(ws)
    session.flush()
    folder = Folder(id=f"cd-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder)
    session.flush()
    if con_tipos:
        session.add_all([
            DocumentType(id=f"cd-dt1-{uid}", workspace_id=ws.id, key="procedimiento",
                         code_prefix="PR", label="Procedimiento", prompt_text="", behaviors_json="{}"),
            DocumentType(id=f"cd-dt2-{uid}", workspace_id=ws.id, key="politica",
                         code_prefix="PO", label="Política", prompt_text="", behaviors_json="{}"),
        ])
        session.flush()
    return ws, folder


def _crear_doc(session, ws, folder, *, tipo="procedimiento", nombre="Doc"):
    doc = Process(
        id=f"cd-doc-{uuid.uuid4().hex[:8]}", workspace_id=ws.id, folder_id=folder.id,
        document_type=tipo, name=nombre, status="draft",
    )
    session.add(doc)
    session.flush()
    return doc


def _limpiar(session, ws):
    from process_ai_core.db.models import Validation

    session.flush()
    ids = [d[0] for d in session.query(Document.id).filter_by(workspace_id=ws.id).all()]
    # Soltar las FKs que apuntan a versiones antes de borrarlas.
    session.query(Document).filter(Document.id.in_(ids or [""])).update(
        {"approved_version_id": None}, synchronize_session=False
    )
    for did in ids:
        session.query(AuditLog).filter_by(document_id=did).delete()
        session.query(DocumentVersion).filter_by(document_id=did).update({"validation_id": None})
        session.query(Validation).filter_by(document_id=did).delete()
        session.query(DocumentVersion).filter_by(document_id=did).delete()
        session.query(Process).filter_by(id=did).delete()
        session.query(Document).filter_by(id=did).delete()
    session.query(DocumentCodeCounter).filter_by(workspace_id=ws.id).delete()
    session.query(DocumentType).filter_by(workspace_id=ws.id).delete()
    session.query(Folder).filter_by(workspace_id=ws.id).delete()
    session.query(Workspace).filter_by(id=ws.id).delete()
    session.commit()


# ── 1. Formato y prefijos ────────────────────────────────────────────────────


def test_el_formato_del_codigo_es_prefijo_y_secuencial_con_padding():
    assert format_code("PR", 42) == "PR-0042"
    assert format_code("PO", 7) == "PO-0007"
    # Al pasarse del padding crece en vez de fallar: un código feo es mejor que
    # un documento que no se puede crear.
    assert format_code("PR", 12345) == "PR-12345"
    assert CODE_PADDING == 4


def test_todos_los_tipos_por_defecto_traen_prefijo():
    from process_ai_core.domains.document_types import DEFAULT_DOCUMENT_TYPES

    prefijos = {t["key"]: t.get("code_prefix") for t in DEFAULT_DOCUMENT_TYPES}
    assert all(prefijos.values()), f"tipos sin prefijo: {[k for k, v in prefijos.items() if not v]}"
    assert prefijos["procedimiento"] == "PR"
    assert prefijos["politica"] == "PO"
    assert prefijos["instructivo"] == "IT"


def test_un_tipo_personalizado_deriva_su_prefijo():
    assert derive_prefix("política") == "PO"       # sin acentos
    assert derive_prefix("mi_tipo_raro") == "MI"
    assert derive_prefix("") == "DO"               # fallback
    assert derive_prefix("x") == "DO"              # menos de 2 letras


def test_el_prefijo_sale_del_catalogo_del_tenant(session):
    ws, _ = _crear_workspace(session)
    try:
        assert code_prefix_for(session, ws.id, "procedimiento") == "PR"
        assert code_prefix_for(session, ws.id, "politica") == "PO"
        # Tipo que este workspace no tiene: se deriva.
        assert code_prefix_for(session, ws.id, "checklist") == "CH"
    finally:
        _limpiar(session, ws)


# ── 2. Asignación ────────────────────────────────────────────────────────────


def test_el_secuencial_es_por_workspace_y_por_prefijo(session):
    ws_a, fol_a = _crear_workspace(session)
    ws_b, fol_b = _crear_workspace(session)
    try:
        assert assign_document_code(session, _crear_doc(session, ws_a, fol_a)) == "PR-0001"
        assert assign_document_code(session, _crear_doc(session, ws_a, fol_a)) == "PR-0002"
        # Otro tipo ⇒ otra serie.
        assert assign_document_code(
            session, _crear_doc(session, ws_a, fol_a, tipo="politica")
        ) == "PO-0001"
        # Otro workspace ⇒ arranca de nuevo.
        assert assign_document_code(session, _crear_doc(session, ws_b, fol_b)) == "PR-0001"
    finally:
        _limpiar(session, ws_a)
        _limpiar(session, ws_b)


def test_el_codigo_no_se_reasigna_nunca(session):
    """Idempotencia: es el guardarraíl del invariante central de ADR-019."""
    ws, folder = _crear_workspace(session)
    try:
        doc = _crear_doc(session, ws, folder)
        primero = assign_document_code(session, doc)
        assert assign_document_code(session, doc) == primero

        # Reclasificar el tipo NO cambia el código: un procedimiento que pasa a
        # política sigue siendo PR-0001.
        doc.document_type = "politica"
        session.flush()
        assert assign_document_code(session, doc) == primero
        assert doc.code.startswith("PR-")

        # Mover de carpeta tampoco.
        otra = Folder(id=f"cd-f2-{uuid.uuid4().hex[:8]}", workspace_id=ws.id, name="otra", path="otra")
        session.add(otra)
        session.flush()
        doc.folder_id = otra.id
        session.flush()
        assert doc.code == primero
    finally:
        _limpiar(session, ws)


def test_el_contador_no_recicla_numeros_al_borrar(session):
    """
    Si el secuencial saliera de MAX(code), borrar el último documento haría que
    el siguiente reciclara su código, y dos documentos distintos habrían sido
    "PR-0002" en momentos distintos.
    """
    ws, folder = _crear_workspace(session)
    try:
        _crear_doc_con_codigo = lambda: assign_document_code(session, _crear_doc(session, ws, folder))
        assert _crear_doc_con_codigo() == "PR-0001"
        segundo_doc = _crear_doc(session, ws, folder)
        assert assign_document_code(session, segundo_doc) == "PR-0002"

        session.query(Process).filter_by(id=segundo_doc.id).delete()
        session.query(Document).filter_by(id=segundo_doc.id).delete()
        session.flush()

        assert _crear_doc_con_codigo() == "PR-0003", "el contador recicló un número"
    finally:
        _limpiar(session, ws)


def test_un_override_manual_no_rompe_la_serie(session):
    ws, folder = _crear_workspace(session)
    try:
        doc = _crear_doc(session, ws, folder)
        assert assign_document_code(session, doc, override="pr-9999") == "PR-9999"  # normaliza

        # Un override que choca con uno existente se rechaza.
        with pytest.raises(ValueError, match="ya está en uso"):
            assign_document_code(session, _crear_doc(session, ws, folder), override="PR-9999")

        # Y la serie automática sigue su curso sin colisionar.
        assert assign_document_code(session, _crear_doc(session, ws, folder)) == "PR-0001"
    finally:
        _limpiar(session, ws)


def test_el_generador_saltea_un_codigo_ya_ocupado_a_mano(session):
    """El contador garantiza unicidad, pero un override pudo tomar su número."""
    ws, folder = _crear_workspace(session)
    try:
        ocupado = _crear_doc(session, ws, folder)
        assign_document_code(session, ocupado, override="PR-0001")
        # El contador arranca en 1 → chocaría; debe avanzar solo.
        assert generate_document_code(session, ws.id, "procedimiento") == "PR-0002"
    finally:
        _limpiar(session, ws)


def test_el_indice_unico_por_workspace_existe():
    """Respaldo del contador a nivel base de datos (migración 0014)."""
    from sqlalchemy import text

    from process_ai_core.db.database import DATABASE_SCHEMA, get_db_engine

    with get_db_engine(echo=False).connect() as conn:
        indices = [
            r[0]
            for r in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname=:s AND tablename='documents'"),
                {"s": DATABASE_SCHEMA},
            )
        ]
    assert "uq_documents_workspace_code" in indices


def test_los_documentos_nuevos_nacen_con_codigo(session):
    """create_process_document lo asigna sin que el llamador tenga que pedirlo."""
    from process_ai_core.db.helpers import create_process_document

    ws, folder = _crear_workspace(session)
    try:
        doc = create_process_document(
            session=session, workspace_id=ws.id, name="Nuevo", folder_id=folder.id
        )
        session.flush()
        assert doc.code == "PR-0001"
    finally:
        _limpiar(session, ws)


# ── 3. Vigencia de la aprobación ─────────────────────────────────────────────


def test_add_months_respeta_el_fin_de_mes():
    assert _add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)
    assert _add_months(datetime.date(2026, 1, 31), 24) == datetime.date(2028, 1, 31)
    assert _add_months(datetime.date(2024, 2, 29), 12) == datetime.date(2025, 2, 28)


def test_el_default_de_vigencia_es_configurable_por_workspace(session):
    import json

    ws, _ = _crear_workspace(session)
    try:
        assert workspace_default_validity_months(session, ws.id) == 24
        ws.metadata_json = json.dumps({"governance": {"default_validity_months": 12}})
        session.flush()
        assert workspace_default_validity_months(session, ws.id) == 12
        # Valores absurdos se ignoran en vez de propagarse al acta.
        ws.metadata_json = json.dumps({"governance": {"default_validity_months": 0}})
        session.flush()
        assert workspace_default_validity_months(session, ws.id) == 24
    finally:
        _limpiar(session, ws)


def _preparar_para_aprobar(session, ws, folder):
    from process_ai_core.db.models import Validation

    doc = _crear_doc(session, ws, folder, nombre="Para aprobar")
    autor = User(id=f"cd-a-{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@x.com", name="Autor")
    session.add(autor)
    session.flush()
    val = Validation(id=f"cd-v-{uuid.uuid4().hex[:8]}", document_id=doc.id, status="pending")
    session.add(val)
    session.flush()
    version = DocumentVersion(
        id=f"cd-ver-{uuid.uuid4().hex[:8]}", document_id=doc.id, version_number=1,
        version_status="IN_REVIEW", content_type="generated", content_json="{}",
        content_markdown="# D", validation_id=val.id, created_by=autor.id,
    )
    # El aprobador tiene que ser un usuario real: approve_version escribe un
    # audit log con FK a users.
    aprobador = User(
        id=f"cd-ap-{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@x.com", name="Aprobador"
    )
    session.add_all([version, aprobador])
    session.flush()
    return doc, version, val, autor, aprobador


def test_aprobar_fija_la_vigencia_con_el_default(session):
    from process_ai_core.db.helpers import approve_version

    ws, folder = _crear_workspace(session)
    try:
        doc, version, val, autor, aprobador = _preparar_para_aprobar(session, ws, folder)
        aprobada = approve_version(session=session, validation_id=val.id, approver_id=aprobador.id)
        esperado = _add_months(aprobada.approved_at.date(), 24)
        assert aprobada.validity_until == esperado
    finally:
        _limpiar(session, ws)
        session.query(User).filter(User.email.like("%@x.com")).delete(synchronize_session=False)
        session.commit()


def test_aprobar_con_fecha_explicita_la_respeta(session):
    from process_ai_core.db.helpers import approve_version

    ws, folder = _crear_workspace(session)
    try:
        doc, version, val, autor, aprobador = _preparar_para_aprobar(session, ws, folder)
        elegida = datetime.date(2030, 6, 1)
        aprobada = approve_version(
            session=session, validation_id=val.id, approver_id=aprobador.id, validity_until=elegida
        )
        assert aprobada.validity_until == elegida
    finally:
        _limpiar(session, ws)
        session.query(User).filter(User.email.like("%@x.com")).delete(synchronize_session=False)
        session.commit()


def test_se_puede_aprobar_sin_comprometer_vencimiento(session):
    """
    NULL explícito ≠ olvido. La portada omite la fila en vez de inventar una fecha.
    """
    from process_ai_core.db.helpers import approve_version

    ws, folder = _crear_workspace(session)
    try:
        doc, version, val, autor, aprobador = _preparar_para_aprobar(session, ws, folder)
        aprobada = approve_version(
            session=session, validation_id=val.id, approver_id=aprobador.id, skip_validity=True
        )
        assert aprobada.validity_until is None
    finally:
        _limpiar(session, ws)
        session.query(User).filter(User.email.like("%@x.com")).delete(synchronize_session=False)
        session.commit()


# ── 4. Llegan al PDF ─────────────────────────────────────────────────────────


def test_el_codigo_y_la_vigencia_llegan_al_document_context(session):
    from api.routes._document_context import build_document_context

    ws, folder = _crear_workspace(session)
    try:
        doc = _crear_doc(session, ws, folder, nombre="Recepción")
        assign_document_code(session, doc)
        version = DocumentVersion(
            id=f"cd-ver-{uuid.uuid4().hex[:8]}", document_id=doc.id, version_number=2,
            version_status="APPROVED", content_type="generated", content_json="{}",
            content_markdown="# D", approved_at=datetime.datetime(2026, 1, 15),
            validity_until=datetime.date(2028, 1, 15), is_current=True,
        )
        session.add(version)
        session.flush()

        ctx = build_document_context(session, doc, version)
        assert ctx.code == "PR-0001"
        assert ctx.validity_until == datetime.date(2028, 1, 15)
        assert ctx.verification_url and version.id in ctx.verification_url
    finally:
        _limpiar(session, ws)


# ── 5. Config de la URL de verificación ──────────────────────────────────────


def test_en_produccion_la_url_de_verificacion_no_cae_al_fallback(monkeypatch):
    """
    Esa URL queda impresa en un PDF que no se puede reescribir. Si cae a una URL
    efímera de Cloud Run, el QR muere el día que cambie el dominio.
    """
    from process_ai_core.config import get_settings, resolve_verification_base_url

    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("DOCUMENT_VERIFICATION_BASE_URL", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="DOCUMENT_VERIFICATION_BASE_URL"):
            resolve_verification_base_url()

        monkeypatch.setenv("DOCUMENT_VERIFICATION_BASE_URL", "https://process.acme.com/")
        get_settings.cache_clear()
        assert resolve_verification_base_url() == "https://process.acme.com"
    finally:
        get_settings.cache_clear()


def test_en_local_si_cae_al_fallback(monkeypatch):
    from process_ai_core.config import get_settings, resolve_verification_base_url

    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("DOCUMENT_VERIFICATION_BASE_URL", "")
    get_settings.cache_clear()
    try:
        assert resolve_verification_base_url()  # api_base_url
    finally:
        get_settings.cache_clear()


# ── 6. Página de verificación ────────────────────────────────────────────────


def _preparar_para_verificar(session):
    ws, folder = _crear_workspace(session)
    doc = _crear_doc(session, ws, folder, nombre="Recepción de combustible")
    assign_document_code(session, doc)
    doc.status = "approved"

    vieja = DocumentVersion(
        id=str(uuid.uuid4()), document_id=doc.id, version_number=1,
        version_status="OBSOLETE", content_type="generated", content_json="{}",
        content_markdown="# v1", approved_at=datetime.datetime(2025, 3, 1),
        pdf_sha256="a" * 64, is_current=False,
    )
    vigente = DocumentVersion(
        id=str(uuid.uuid4()), document_id=doc.id, version_number=2,
        version_status="APPROVED", content_type="generated", content_json="{}",
        content_markdown="# v2", approved_at=datetime.datetime(2026, 1, 15),
        validity_until=datetime.date(2028, 1, 15), pdf_sha256="b" * 64, is_current=True,
    )
    session.add_all([vieja, vigente])
    session.flush()
    return ws, doc, vieja, vigente


def test_verificacion_publica_dice_si_esta_vigente(session, monkeypatch):
    from api.routes import verification as ver

    ws, doc, vieja, vigente = _preparar_para_verificar(session)
    from contextlib import contextmanager

    @contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(ver, "get_db_session", fake_session)
    try:
        r = ver.verify_document_version(vigente.id, authorization=None)
        assert r["estado"] == "vigente" and r["es_version_vigente"] is True
        assert r["version_number"] == 2
        assert r["pdf_sha256"] == "b" * 64          # para contrastar el PDF en mano
        assert r["validity_until"] == "2028-01-15"
        assert r["detalle_completo"] is False
        # Sin sesión NO se filtra información del cliente.
        assert "title" not in r and "approved_by" not in r and "code" not in r
    finally:
        _limpiar(session, ws)


def test_verificacion_publica_dice_por_cual_fue_superada(session, monkeypatch):
    """No alcanza con "fue superada": hay que decir por cuál versión."""
    from contextlib import contextmanager

    from api.routes import verification as ver

    ws, doc, vieja, vigente = _preparar_para_verificar(session)

    @contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(ver, "get_db_session", fake_session)
    try:
        r = ver.verify_document_version(vieja.id, authorization=None)
        assert r["estado"] == "superada" and r["es_version_vigente"] is False
        assert r["version_vigente_number"] == 2
        assert r["version_vigente_approved_at"].startswith("2026-01-15")
    finally:
        _limpiar(session, ws)


def test_verificacion_con_sesion_agrega_el_detalle(session, monkeypatch):
    from contextlib import contextmanager

    from api.routes import verification as ver

    ws, doc, vieja, vigente = _preparar_para_verificar(session)

    @contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(ver, "get_db_session", fake_session)
    monkeypatch.setattr(ver, "_viewer_user_id", lambda auth: "user-1")
    monkeypatch.setattr(ver, "_tiene_membresia", lambda s, u, w: True)
    try:
        r = ver.verify_document_version(vigente.id, authorization="Bearer x")
        assert r["detalle_completo"] is True
        assert r["code"] == "PR-0001"
        assert r["title"] == "Recepción de combustible"
        assert r["client_name"] == "ACME"
    finally:
        _limpiar(session, ws)


def test_un_version_id_inexistente_da_404(session, monkeypatch):
    from contextlib import contextmanager

    from fastapi import HTTPException

    from api.routes import verification as ver

    @contextmanager
    def fake_session():
        yield session

    monkeypatch.setattr(ver, "get_db_session", fake_session)
    with pytest.raises(HTTPException) as exc:
        ver.verify_document_version(str(uuid.uuid4()), authorization=None)
    assert exc.value.status_code == 404
