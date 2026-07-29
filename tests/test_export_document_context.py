"""
Infraestructura de la Fase B: que el dato de gobernanza llegue al exportador,
que el CSS no se rompa y que el logo se resuelva desde object storage.

NO se testea la portada ni el diseño: eso es Fase C. Acá se verifica el
cableado — que `DocumentContext` cruce la frontera del exportador, que un HTML
completo no se escape del wrapper, y que el logo salga de storage y no del disco.
"""

import json
import re
import tempfile
import uuid
from pathlib import Path

import pytest

from api.routes import _branding as branding_mod
from api.routes._document_context import build_document_context
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Document,
    DocumentType,
    DocumentVersion,
    Folder,
    Process,
    User,
    Validation,
    Workspace,
)
from process_ai_core.export import DocumentContext, export_pdf_from_content
from process_ai_core.export.branding import PdfBranding
from process_ai_core.export.pdf_weasyprint import _BASE_CSS, _wrap_html
from process_ai_core.storage import workspace_branding_key
from process_ai_core.storage.local import LocalDiskStorage

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100fffff9270000000049454e44ae426082"
)


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


# ── 1. DocumentContext: qué entra y qué no ───────────────────────────────────


def test_document_context_no_expone_datos_mutables():
    """
    Guardarraíl del criterio: si alguien agrega carpeta, estado actual o run al
    dataclass, este test falla. El PDF aprobado es inmutable; un dato que cambia
    en el sistema haría que el papel contradiga a la pantalla.
    """
    campos = set(DocumentContext.__dataclass_fields__)

    prohibidos = {
        "folder", "folder_id", "folder_path",
        "status", "document_status", "version_status",
        "run", "run_id",
    }
    assert not (campos & prohibidos), f"campos mutables filtrados: {campos & prohibidos}"

    esperados = {
        "code", "title", "document_type_label", "version_number", "elaborated_by",
        "reviewed_by", "approved_by", "approved_at", "supersedes_version_number",
        "supersedes_approved_at", "validity_until", "version_id", "client_name",
        "is_approved", "verification_url",
        # Paso 4: rol de cada firmante, historial de versiones e índice.
        "elaborated_by_role", "reviewed_by_role", "approved_by_role",
        "version_history", "show_toc",
    }
    assert campos == esperados


def test_document_context_es_inmutable_y_todo_opcional():
    ctx = DocumentContext()
    assert ctx.title is None and ctx.is_approved is False
    with pytest.raises(Exception):
        ctx.title = "otro"  # frozen=True


# ── 2. Construcción desde la BD ──────────────────────────────────────────────


def _crear_documento_con_version(session, *, con_tipo=True):
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(
        id=f"dc-ws-{uid}", slug=f"dc-ws-{uid}", name="Estación ACME",
        workspace_type="organization",
    )
    session.add(ws)
    session.flush()
    folder = Folder(id=f"dc-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder)
    session.flush()

    autor = User(id=f"dc-u1-{uid}", email=f"autor-{uid}@x.com", name="Ana Autora")
    revisor = User(id=f"dc-u2-{uid}", email=f"rev-{uid}@x.com", name="Beto Revisor")
    # Sin nombre: debe caer al email en vez de dejar la firma vacía.
    aprobador = User(id=f"dc-u3-{uid}", email=f"apr-{uid}@x.com", name="")
    session.add_all([autor, revisor, aprobador])
    session.flush()

    if con_tipo:
        session.add(DocumentType(
            id=f"dc-dt-{uid}", workspace_id=ws.id, key="procedimiento",
            label="Procedimiento Operativo", prompt_text="", behaviors_json="{}",
        ))
        session.flush()

    doc = Process(
        id=f"dc-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
        document_type="procedimiento", name="Recepción de combustible",
        status="approved",
    )
    session.add(doc)
    session.flush()

    v1 = DocumentVersion(
        id=f"dc-v1-{uid}", document_id=doc.id, version_number=1,
        version_status="OBSOLETE", content_type="generated",
        content_json="{}", content_markdown="# v1",
        approved_at=__import__("datetime").datetime(2025, 3, 1, 12, 0),
    )
    session.add(v1)
    session.flush()

    val = Validation(
        id=f"dc-val-{uid}", document_id=doc.id, validator_user_id=revisor.id,
        status="approved",
    )
    session.add(val)
    session.flush()

    v2 = DocumentVersion(
        id=f"dc-v2-{uid}", document_id=doc.id, version_number=2,
        version_status="APPROVED", content_type="generated",
        content_json="{}", content_markdown="# v2",
        supersedes_version_id=v1.id, validation_id=val.id,
        created_by=autor.id, approved_by=aprobador.id,
        approved_at=__import__("datetime").datetime(2026, 1, 15, 9, 30),
        is_current=True,
    )
    session.add(v2)
    session.flush()
    return doc, v2, ws, [autor.id, revisor.id, aprobador.id], v1.id, val.id


def _limpiar(session, doc, ws, user_ids, extra_version_ids=(), validation_ids=()):
    session.query(DocumentVersion).filter_by(document_id=doc.id).delete()
    session.query(Validation).filter(Validation.id.in_(list(validation_ids) or [""])).delete(
        synchronize_session=False
    )
    session.query(Process).filter_by(id=doc.id).delete()
    session.query(Document).filter_by(id=doc.id).delete()
    session.query(DocumentType).filter_by(workspace_id=ws.id).delete()
    session.query(Folder).filter_by(workspace_id=ws.id).delete()
    session.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    session.query(Workspace).filter_by(id=ws.id).delete()
    session.commit()


def test_build_document_context_resuelve_firmas_tipo_y_reemplazo(session):
    doc, v2, ws, user_ids, v1_id, val_id = _crear_documento_con_version(session)
    try:
        ctx = build_document_context(session, doc, v2)

        assert ctx.title == "Recepción de combustible"
        assert ctx.client_name == "Estación ACME"
        # Label del catálogo del tenant, no el slug.
        assert ctx.document_type_label == "Procedimiento Operativo"
        assert ctx.version_number == 2
        assert ctx.version_id == v2.id
        assert ctx.is_approved is True

        # Las tres firmas, ya resueltas a nombre (no IDs).
        assert ctx.elaborated_by == "Ana Autora"
        assert ctx.reviewed_by == "Beto Revisor"
        assert ctx.approved_by.endswith("@x.com")  # sin nombre → fallback al email
        assert ctx.approved_at.year == 2026

        # Trazabilidad de reemplazo.
        assert ctx.supersedes_version_number == 1
        assert ctx.supersedes_approved_at.year == 2025

        # Sin fuente en el modelo todavía.
        assert ctx.code is None and ctx.validity_until is None
    finally:
        _limpiar(session, doc, ws, user_ids, validation_ids=[val_id])


def test_build_document_context_resuelve_los_nombres_en_una_sola_query(session):
    """
    Tres personas distintas ⇒ una query a users, no una por persona.

    Desde el Paso 4 la misma query trae el rol operativo, y los aprobadores del
    historial de versiones se resuelven en ese mismo lote: sin eso, un documento
    con diez versiones haría diez consultas extra dentro de la transacción de
    aprobación.
    """
    doc, v2, ws, user_ids, _, val_id = _crear_documento_con_version(session)
    queries = []

    from sqlalchemy import event
    engine = session.get_bind()

    def registrar(conn, cursor, statement, params, ctx, many):
        if "FROM process_ai.users" in statement or "FROM users" in statement:
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", registrar)
    try:
        session.expire_all()
        build_document_context(session, doc, v2)
        assert len(queries) == 1, f"se hicieron {len(queries)} queries a users:\n" + "\n".join(queries)
    finally:
        event.remove(engine, "before_cursor_execute", registrar)
        _limpiar(session, doc, ws, user_ids, validation_ids=[val_id])


def test_build_document_context_sin_version_solo_trae_lo_del_documento(session):
    """El process.pdf del patch por IA se genera antes de que exista la versión."""
    doc, v2, ws, user_ids, _, val_id = _crear_documento_con_version(session)
    try:
        ctx = build_document_context(session, doc, None)
        assert ctx.title == "Recepción de combustible"
        assert ctx.document_type_label == "Procedimiento Operativo"
        assert ctx.client_name == "Estación ACME"
        assert ctx.version_number is None
        assert ctx.is_approved is False
    finally:
        _limpiar(session, doc, ws, user_ids, validation_ids=[val_id])


def test_build_document_context_cae_al_slug_si_no_hay_tipo_configurado(session):
    doc, v2, ws, user_ids, _, val_id = _crear_documento_con_version(session, con_tipo=False)
    try:
        ctx = build_document_context(session, doc, v2)
        assert ctx.document_type_label == "procedimiento"
    finally:
        _limpiar(session, doc, ws, user_ids, validation_ids=[val_id])


# ── 3. Bug de --pdf-border-color / wrapper ───────────────────────────────────


HTML_COMPLETO = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    "<style>.propio { color: rebeccapurple; }</style></head>"
    "<body><h1>Importado</h1><table><tr><td>celda</td></tr></table></body></html>"
)


def test_toda_variable_css_usada_esta_definida_por_la_paleta():
    """
    El bug original: `--pdf-border-color` se usaba en _BASE_CSS pero se definía en
    el <style> del wrapper, que no se emitía para HTML completo — los documentos
    importados salían con tablas sin borde.

    Ahora las variables las resuelve `root_variables_css` a partir de la marca del
    cliente y se inyectan SIEMPRE. El guardarraíl es el mismo: ninguna variable
    puede usarse sin estar definida.
    """
    from process_ai_core.export.pdf_weasyprint import root_variables_css

    definidas = root_variables_css(None)
    usadas = set(re.findall(r"var\((--[a-z-]+)", _BASE_CSS))
    assert usadas, "el CSS dejó de usar variables: revisá este guardarraíl"
    for uso in usadas:
        # --pdf-mono tiene fallback inline en el propio var(); el resto va en la paleta.
        if uso == "--pdf-mono":
            continue
        assert f"{uso}:" in definidas, f"{uso} se usa pero la paleta no lo define"


def test_html_completo_ahora_se_envuelve_y_conserva_sus_estilos():
    envuelto = _wrap_html(HTML_COMPLETO, PdfBranding(logo_path="/tmp/logo.png"))

    # Antes esto retornaba temprano: sin header, sin logo.
    assert "pdf-page-header" in envuelto
    assert "logo.png" in envuelto
    assert 'class="pdf-content"' in envuelto
    # El <style> propio del documento sobrevive (y va después del nuestro).
    assert "rebeccapurple" in envuelto
    # Sin anidar <body> dentro de <body>.
    assert envuelto.count("<body>") == 1
    assert "Importado" in envuelto and "celda" in envuelto


def test_html_completo_sin_body_explicito_no_pierde_contenido():
    sin_body = "<html><head><title>x</title></head><p>contenido suelto</p></html>"
    envuelto = _wrap_html(sin_body)
    assert "contenido suelto" in envuelto
    assert envuelto.count("<html") == 1


def test_fragmento_html_sigue_funcionando_igual():
    envuelto = _wrap_html("<p>fragmento</p>")
    assert "fragmento" in envuelto and "pdf-page-header" in envuelto


def test_html_completo_renderiza_pdf_valido():
    with tempfile.TemporaryDirectory() as d:
        pdf = export_pdf_from_content(
            content=HTML_COMPLETO, format="html", run_dir=Path(d), pdf_name="x.pdf"
        )
        assert Path(pdf).read_bytes()[:5] == b"%PDF-"


# ── 4. El contexto llega al PDF ──────────────────────────────────────────────


def test_el_contexto_llega_al_archivo_pdf():
    """
    Prueba de punta a punta de que el dato cruza la frontera del exportador:
    aparece en la metadata del archivo (/Title, /Author). Es metadata, no
    plantilla — el PDF impreso se ve igual.
    """
    from pypdf import PdfReader

    ctx = DocumentContext(
        code="PRO-CAL-001",
        title="Recepción de combustible",
        elaborated_by="Ana Autora",
        client_name="Estación ACME",
        version_number=2,
        is_approved=True,
    )
    with tempfile.TemporaryDirectory() as d:
        pdf = export_pdf_from_content(
            content="<h1>Doc</h1>", format="html", run_dir=Path(d),
            pdf_name="x.pdf", document_context=ctx,
        )
        meta = dict(PdfReader(str(pdf)).metadata or {})

    assert meta.get("/Title") == "PRO-CAL-001 — Recepción de combustible"
    assert meta.get("/Author") == "Ana Autora"


def test_sin_contexto_el_comportamiento_no_cambia():
    with tempfile.TemporaryDirectory() as d:
        con_none = export_pdf_from_content(
            content="<h1>Doc</h1>", format="html", run_dir=Path(d),
            pdf_name="a.pdf", document_context=None,
        ).read_bytes()
        sin_param = export_pdf_from_content(
            content="<h1>Doc</h1>", format="html", run_dir=Path(d), pdf_name="b.pdf"
        ).read_bytes()
    assert con_none == sin_param


# ── 5. Logo desde object storage ─────────────────────────────────────────────


@pytest.fixture
def storage_tmp(tmp_path, monkeypatch):
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    monkeypatch.setattr(branding_mod, "get_storage", lambda: store)
    # output_dir apunta al tmp: el cache local del logo no ensucia el real.
    from process_ai_core.config import Settings, get_settings
    real = get_settings()
    fake = Settings(**{**real.__dict__, "output_dir": str(tmp_path / "out")})
    monkeypatch.setattr(branding_mod, "get_settings", lambda: fake)
    return store


def _workspace_con_logo(session, filename="logo.png"):
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(
        id=f"lg-ws-{uid}", slug=f"lg-ws-{uid}", name="Con Logo",
        workspace_type="organization",
        metadata_json=json.dumps({"branding": {"client_icon_filename": filename}}),
    )
    session.add(ws)
    session.flush()
    return ws


def test_logo_se_resuelve_desde_object_storage(session, storage_tmp):
    ws = _workspace_con_logo(session)
    storage_tmp.put(workspace_branding_key(ws.id, "logo.png"), PNG_1PX, "image/png")
    try:
        branding = branding_mod.get_workspace_pdf_branding(session, ws.id)
        assert branding.logo_path is not None
        # Materializado en disco: los dos motores necesitan un archivo real.
        assert Path(branding.logo_path).read_bytes() == PNG_1PX
    finally:
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


def test_logo_faltante_loggea_warning_en_vez_de_fallar_en_silencio(session, storage_tmp, caplog):
    """
    Este es el bug de Cloud Run: branding configurado, blob ausente, PDF oficial
    congelado sin logo y nadie enterado.
    """
    ws = _workspace_con_logo(session)  # sin subir nada a storage
    try:
        with caplog.at_level("WARNING"):
            branding = branding_mod.get_workspace_pdf_branding(session, ws.id)
        assert branding.logo_path is None
        assert any("no está ni en storage" in r.getMessage() for r in caplog.records)
    finally:
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


def test_sin_branding_configurado_no_hay_warning(session, storage_tmp, caplog):
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(
        id=f"lg-ws-{uid}", slug=f"lg-ws-{uid}", name="Sin Logo",
        workspace_type="organization", metadata_json="{}",
    )
    session.add(ws)
    session.flush()
    try:
        with caplog.at_level("WARNING"):
            branding = branding_mod.get_workspace_pdf_branding(session, ws.id)
        assert branding.logo_path is None
        assert not caplog.records  # no tener logo no es un problema
    finally:
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


def test_logo_legacy_en_disco_sigue_funcionando(session, storage_tmp):
    """Compatibilidad: iconos subidos antes de mover el branding a storage."""
    ws = _workspace_con_logo(session, "viejo.png")
    legacy = branding_mod._legacy_local_logo_path(ws.id, "viejo.png")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(PNG_1PX)
    try:
        branding = branding_mod.get_workspace_pdf_branding(session, ws.id)
        assert branding.logo_path == str(legacy.resolve())
    finally:
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


def test_la_clave_del_logo_es_tenant_scoped():
    key = workspace_branding_key("ws-1", "logo.png")
    assert key == "workspaces/ws-1/branding/logo.png"
    # Sin traversal aunque venga un nombre hostil.
    assert workspace_branding_key("ws-1", "../../otro/x.png") == "workspaces/ws-1/branding/x.png"


# ── 6. Backfill de logos a object storage ────────────────────────────────────


def test_backfill_migra_logos_de_disco_a_storage(session, storage_tmp, tmp_path, monkeypatch):
    """
    tools/backfill_workspace_logos.py: sube lo que quedó en el disco viejo y
    verifica releyendo desde storage antes de dar por migrado.
    """
    import importlib.util

    ws = _workspace_con_logo(session, "viejo.png")
    session.commit()

    legacy = branding_mod._legacy_local_logo_path(ws.id, "viejo.png")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(PNG_1PX)

    spec = importlib.util.spec_from_file_location(
        "backfill_logos", Path(__file__).resolve().parent.parent / "tools" / "backfill_workspace_logos.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    monkeypatch.setattr(modulo, "get_storage", lambda: storage_tmp)
    monkeypatch.setattr(modulo, "get_settings", branding_mod.get_settings)

    try:
        monkeypatch.setattr("sys.argv", ["backfill", "--dry-run"])
        assert modulo.main() == 0
        # El dry-run no sube nada.
        assert not storage_tmp.exists(workspace_branding_key(ws.id, "viejo.png"))

        monkeypatch.setattr("sys.argv", ["backfill"])
        assert modulo.main() == 0
        assert storage_tmp.get(workspace_branding_key(ws.id, "viejo.png")) == PNG_1PX
        # Sin --delete-local el origen queda intacto.
        assert legacy.exists()

        # Idempotente: una segunda corrida no rompe ni duplica.
        assert modulo.main() == 0

        # Con --delete-local borra el origen tras verificar.
        monkeypatch.setattr("sys.argv", ["backfill", "--delete-local"])
        assert modulo.main() == 0
        assert not legacy.exists()

        # Y después de migrar, el logo se resuelve por el camino nuevo.
        branding = branding_mod.get_workspace_pdf_branding(session, ws.id)
        assert branding.logo_path and Path(branding.logo_path).read_bytes() == PNG_1PX
    finally:
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()
