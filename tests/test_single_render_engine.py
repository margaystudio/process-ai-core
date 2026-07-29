"""
Un solo motor de render, y el camino feliz del producto termina con PDF congelado.

El bloqueante que cierra esta fase: el pipeline creaba versiones solo con
`content_markdown`, el freeze iba por Pandoc + LaTeX, la imagen no tiene motor
LaTeX y `freeze_approved_pdf` es best-effort — así que generar → revisar →
aprobar SIN pasar por el editor manual dejaba la versión APPROVED sin
`pdf_storage_key`, en silencio.

El test central es `test_documento_generado_por_pipeline_queda_congelado_al_aprobar`:
reproduce exactamente ese camino y exige que termine con artefacto.
"""

import hashlib
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Document,
    DocumentVersion,
    Folder,
    Process,
    Workspace,
)
from process_ai_core.export import export_pdf, export_pdf_from_content, get_export_content
from process_ai_core.export.markdown_html import (
    MARKDOWN_EXTENSIONS,
    markdown_to_html,
    render_frozen_html,
)
from process_ai_core.storage.local import LocalDiskStorage

MARKDOWN_PIPELINE = """# Recepción de combustible

Procedimiento operativo para la recepción de combustible en playa.

## Pasos

1. Verificar el precinto del camión
2. Contrastar el remito con la orden de compra

| Paso | Responsable |
|------|-------------|
| Medir varillado | Playero |
"""


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture
def storage(tmp_path, monkeypatch):
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    import api.routes._freeze as freeze_mod

    monkeypatch.setattr(freeze_mod, "get_storage", lambda: store)
    return store


# ── 1. Un solo motor ─────────────────────────────────────────────────────────


def test_el_exportador_de_pandoc_ya_no_existe():
    """Se eliminó del camino en vez de dejarlo como código muerto."""
    with pytest.raises(ImportError):
        import process_ai_core.export.pdf_pandoc  # noqa: F401


def test_markdown_sale_por_weasyprint_sin_motor_latex(monkeypatch):
    """
    La prueba de fondo: aunque no exista NINGÚN binario externo, el markdown
    tiene que producir un PDF. Antes acá se necesitaba pandoc + xelatex.
    """
    # Cualquier intento de invocar un binario externo revienta el test.
    def sin_subprocesos(*args, **kwargs):
        raise AssertionError(f"el render no debe invocar binarios externos: {args[:1]}")

    monkeypatch.setattr(subprocess, "run", sin_subprocesos)
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)

    with tempfile.TemporaryDirectory() as d:
        pdf = export_pdf_from_content(
            content=MARKDOWN_PIPELINE, format="markdown", run_dir=Path(d), pdf_name="x.pdf"
        )
        assert Path(pdf).read_bytes()[:5] == b"%PDF-"


def test_export_pdf_de_un_run_tambien_sale_por_weasyprint(monkeypatch):
    """`export_pdf` (artefacto process.pdf del run) mantiene su firma."""
    monkeypatch.setattr(shutil, "which", lambda *_a, **_k: None)
    with tempfile.TemporaryDirectory() as d:
        run_dir = Path(d)
        md = run_dir / "process.md"
        md.write_text(MARKDOWN_PIPELINE, encoding="utf-8")

        pdf = export_pdf(run_dir=run_dir, md_path=md, pdf_name="process.pdf")
        assert Path(pdf).read_bytes()[:5] == b"%PDF-"
        assert Path(pdf).name == "process.pdf"


def test_export_pdf_resuelve_imagenes_relativas_del_run():
    """
    El markdown del pipeline trae `assets/...` relativos. Pandoc los resolvía con
    --resource-path; WeasyPrint necesita base_url apuntando al run.
    """
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6360000002000100fffff9270000000049454e44ae426082"
    )
    with tempfile.TemporaryDirectory() as d:
        run_dir = Path(d)
        (run_dir / "assets").mkdir()
        (run_dir / "assets" / "paso1.png").write_bytes(png)
        md = run_dir / "process.md"
        md.write_text("# Doc\n\n![paso 1](assets/paso1.png)\n", encoding="utf-8")

        # Si la imagen no resolviera, WeasyPrint loggea y sigue: se verifica que
        # el PDF se produzca y que el HTML intermedio apunte al archivo correcto.
        pdf = export_pdf(run_dir=run_dir, md_path=md, pdf_name="process.pdf")
        assert Path(pdf).read_bytes()[:5] == b"%PDF-"
        assert (run_dir / "assets" / "paso1.png").exists()


def test_get_export_content_devuelve_siempre_html():
    class VersionSoloMarkdown:
        content_html = None
        content_markdown = "# Título\n\n- uno\n"

    class VersionConHtml:
        content_html = "<h1>Editado a mano</h1>"
        content_markdown = "# Título"

    html = get_export_content(VersionSoloMarkdown())
    assert isinstance(html, str) and "<h1>" in html and "<li>" in html

    # Si hay HTML propio (el usuario editó), gana sobre el markdown.
    assert get_export_content(VersionConHtml()) == "<h1>Editado a mano</h1>"

    class VersionVacia:
        content_html = None
        content_markdown = ""

    with pytest.raises(ValueError):
        get_export_content(VersionVacia())


def test_el_conversor_es_el_mismo_en_el_editor_y_en_el_pdf():
    """
    El HTML que el revisor ve en el editor y el que se imprime salen de la misma
    función: si divergieran, se aprobaría una cosa y se congelaría otra.
    """
    from api.routes.documents._helpers import _markdown_to_html

    assert _markdown_to_html(MARKDOWN_PIPELINE) == markdown_to_html(MARKDOWN_PIPELINE)
    assert MARKDOWN_EXTENSIONS == ["extra", "nl2br", "tables", "sane_lists"]


# ── 2. content_html congelado como entrada del render ────────────────────────


def test_render_frozen_html_es_best_effort(monkeypatch):
    """Si la conversión falla, la versión se crea igual (sin HTML)."""
    import process_ai_core.export.markdown_html as mod

    def explota(_md):
        raise RuntimeError("markdown roto")

    monkeypatch.setattr(mod, "markdown_to_html", explota)
    assert mod.render_frozen_html("# hola") is None


def test_markdown_to_html_falla_ruidoso_en_el_camino_del_pdf(monkeypatch):
    """
    En el camino del artefacto NO hay fallback silencioso: congelar un PDF
    ilegible sería peor que no congelar nada.
    """
    import builtins

    real_import = builtins.__import__

    def sin_markdown(name, *args, **kwargs):
        if name == "markdown":
            raise ImportError("no hay markdown")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_markdown)
    with pytest.raises(ImportError):
        markdown_to_html("# hola")


def _crear_documento(session):
    uid = str(uuid.uuid4())[:8]
    ws = Workspace(
        id=f"se-ws-{uid}", slug=f"se-ws-{uid}", name="Estación", workspace_type="organization"
    )
    session.add(ws)
    session.flush()
    folder = Folder(id=f"se-fol-{uid}", workspace_id=ws.id, name="root", path="root")
    session.add(folder)
    session.flush()
    doc = Process(
        id=f"se-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
        document_type="procedimiento", name="Recepción de combustible", status="draft",
    )
    session.add(doc)
    session.flush()
    return doc, ws


def _limpiar(session, doc, ws):
    from process_ai_core.db.models import AuditLog

    # get_or_create_draft deja un audit log PENDIENTE en la sesión. Si no se
    # fuerza el flush acá, ese INSERT sale recién en el commit final —después de
    # que este mismo bloque borró el documento— y viola la FK.
    session.flush()
    session.query(AuditLog).filter_by(document_id=doc.id).delete()
    session.query(DocumentVersion).filter_by(document_id=doc.id).delete()
    session.query(Process).filter_by(id=doc.id).delete()
    session.query(Document).filter_by(id=doc.id).delete()
    session.query(Folder).filter_by(workspace_id=ws.id).delete()
    session.query(Workspace).filter_by(id=ws.id).delete()
    session.commit()


def test_get_or_create_draft_no_arrastra_html_viejo_cuando_cambia_el_markdown(session):
    """
    get_or_create_draft hereda content_html de la versión anterior. Si un update
    cambia el markdown sin regenerar el HTML, el PDF imprimiría el contenido
    VIEJO. Se verifica que el clon venga consistente y que regenerar lo alinee.
    """
    from process_ai_core.db.helpers import get_or_create_draft

    doc, ws = _crear_documento(session)
    try:
        aprobada = DocumentVersion(
            id=f"se-v1-{uuid.uuid4().hex[:8]}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="generated",
            content_json="{}", content_markdown="# Viejo",
            content_html="<h1>Viejo</h1>", is_current=True,
        )
        session.add(aprobada)
        session.flush()

        draft = get_or_create_draft(session=session, document_id=doc.id, user_id=None)
        # El clon copia markdown y HTML JUNTOS: son consistentes entre sí.
        assert draft.content_markdown == "# Viejo"
        assert "Viejo" in (draft.content_html or "")

        # Al cambiar el markdown hay que regenerar el HTML, si no queda desfasado.
        draft.content_markdown = "# Nuevo contenido"
        draft.content_html = render_frozen_html(draft.content_markdown)
        session.flush()
        assert "Nuevo contenido" in draft.content_html
        assert "Viejo" not in draft.content_html
    finally:
        _limpiar(session, doc, ws)


def test_draft_nuevo_sin_origen_nace_con_html(session):
    from process_ai_core.db.helpers import get_or_create_draft

    doc, ws = _crear_documento(session)
    try:
        draft = get_or_create_draft(session=session, document_id=doc.id, user_id=None)
        assert draft.content_html and "<h1>" in draft.content_html
    finally:
        _limpiar(session, doc, ws)


# ── 3. EVIDENCIA: el camino feliz termina con artefacto congelado ────────────


def test_documento_generado_por_pipeline_queda_congelado_al_aprobar(session, storage):
    """
    Reproduce el camino que HOY falla: una versión creada por el pipeline (solo
    markdown, sin pasar por el editor manual) que se aprueba.

    Antes: freeze → Pandoc → sin motor LaTeX → excepción tragada por el
    best-effort → versión APPROVED sin pdf_storage_key.
    Ahora: markdown ya congelado como HTML → WeasyPrint → artefacto.
    """
    from api.routes._freeze import freeze_approved_pdf

    doc, ws = _crear_documento(session)
    try:
        # Exactamente como la crea api/routes/documents/runs.py.
        version = DocumentVersion(
            id=f"se-ver-{uuid.uuid4().hex[:8]}",
            document_id=doc.id,
            version_number=1,
            version_status="APPROVED",
            content_type="generated",
            content_json="{}",
            content_markdown=MARKDOWN_PIPELINE,
            content_html=render_frozen_html(MARKDOWN_PIPELINE),
            is_current=True,
        )
        session.add(version)
        session.flush()

        # El HTML quedó congelado en la fila, no se deriva al imprimir.
        assert version.content_html, "el pipeline debe persistir content_html"

        # Ningún binario externo disponible: si el freeze dependiera de LaTeX, falla.
        assert freeze_approved_pdf(session, version) is True

        assert version.pdf_storage_key, (
            "la versión aprobada quedó SIN PDF congelado: es exactamente el "
            "bloqueante que esta fase cierra"
        )
        assert version.pdf_render_engine.startswith("weasyprint-")
        blob = storage.get(version.pdf_storage_key)
        assert blob[:5] == b"%PDF-"
        assert hashlib.sha256(blob).hexdigest() == version.pdf_sha256
    finally:
        _limpiar(session, doc, ws)


def test_version_legacy_sin_content_html_igual_se_congela(session, storage):
    """
    Red de seguridad: una fila vieja sin content_html se convierte al imprimir en
    vez de fallar. No debería existir en producción, pero no puede romper.
    """
    from api.routes._freeze import freeze_approved_pdf

    doc, ws = _crear_documento(session)
    try:
        version = DocumentVersion(
            id=f"se-lg-{uuid.uuid4().hex[:8]}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="generated",
            content_json="{}", content_markdown=MARKDOWN_PIPELINE,
            content_html=None, is_current=True,
        )
        session.add(version)
        session.flush()

        assert freeze_approved_pdf(session, version) is True
        assert version.pdf_storage_key
        assert storage.get(version.pdf_storage_key)[:5] == b"%PDF-"
    finally:
        _limpiar(session, doc, ws)


# ── 4. Marca de invalidación ─────────────────────────────────────────────────
#
# El PDF congelado de una versión aprobada es el artefacto de auditoría. Los
# otros tres caminos (preview de borrador, patch por IA, process.pdf del run)
# producían un PDF visualmente IDÉNTICO: un borrador impreso y circulado era
# indistinguible de un documento válido. La marca invalida el papel.


def _texto_por_pagina(pdf_path) -> list[str]:
    from pypdf import PdfReader

    return [(p.extract_text() or "") for p in PdfReader(str(pdf_path)).pages]


def _render(document_context, contenido=None):
    contenido = contenido or (
        "<h1>Recepción de combustible</h1>"
        + "<h2>Sección</h2><p>Contenido del procedimiento.</p>"
        "<table><tr><th>Paso</th><th>Responsable</th></tr>"
        "<tr><td>Medir</td><td>Playero</td></tr></table>" * 12
    )
    tmp = Path(tempfile.mkdtemp())
    pdf = export_pdf_from_content(
        content=contenido, format="html", run_dir=tmp,
        pdf_name="x.pdf", document_context=document_context,
    )
    return Path(pdf), tmp


def test_el_pdf_aprobado_no_lleva_ninguna_marca():
    """
    El aprobado no lleva contramarca. Decir "APROBADO" sería redundante (solo
    nace de versiones aprobadas) y envejecería mal: el estado cambia cuando se
    aprueba una versión posterior, pero el PDF congelado no se puede reescribir.
    """
    from process_ai_core.export import DocumentContext

    pdf, tmp = _render(DocumentContext(title="Doc", version_number=3, is_approved=True))
    try:
        paginas = _texto_por_pagina(pdf)
        assert len(paginas) > 1, "el caso interesante es multi-página"
        for i, texto in enumerate(paginas):
            assert "BORRADOR" not in texto, f"marca en la página {i + 1} de un aprobado"
            assert "SIN VALOR OPERATIVO" not in texto
            assert "sin valor operativo" not in texto
        # Tampoco la contramarca inversa.
        assert not any("APROBADO" in t for t in paginas)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_borrador_lleva_marca_de_agua_en_TODAS_las_paginas():
    from process_ai_core.export import DocumentContext

    pdf, tmp = _render(DocumentContext(title="Doc", version_number=4, is_approved=False))
    try:
        paginas = _texto_por_pagina(pdf)
        assert len(paginas) > 1
        for i, texto in enumerate(paginas):
            assert "BORRADOR" in texto, f"falta la marca de agua en la página {i + 1}"
        # El pie corrido va en todas MENOS la portada, que no tiene pie por
        # diseño: ahí el mensaje lo da el bloque de invalidación, más visible.
        for i, texto in enumerate(paginas[1:], start=2):
            assert "sin valor operativo" in texto, f"falta el pie en la página {i}"
        assert "SIN VALOR OPERATIVO" in paginas[0], "la portada debe llevar el bloque"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_borrador_lleva_el_bloque_solo_en_la_primera_pagina():
    from process_ai_core.export import DocumentContext

    pdf, tmp = _render(DocumentContext(title="Doc", is_approved=False))
    try:
        paginas = _texto_por_pagina(pdf)
        assert "BORRADOR — SIN VALOR OPERATIVO" in paginas[0]
        # Y dice qué NO se puede hacer, no en qué estado está.
        primera = paginas[0]
        for prohibicion in ("operar", "capacitar", "auditar", "distribuirse"):
            assert prohibicion in primera, f"el bloque no menciona '{prohibicion}'"
        # No se repite en el resto: es un bloque en flujo, no un encabezado.
        for texto in paginas[1:]:
            assert "SIN VALOR OPERATIVO" not in texto
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sin_contexto_se_marca_por_default_seguro():
    """
    Un PDF sin identidad de gobernanza no puede demostrar que sale de una versión
    aprobada. El error caro es el falso negativo (un borrador que pasa por
    válido), así que ante la duda se marca.
    """
    pdf, tmp = _render(None)
    try:
        assert all("BORRADOR" in t for t in _texto_por_pagina(pdf))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_la_marca_no_altera_el_contenido_del_documento():
    """La marca se suma; no reemplaza ni recorta lo que el documento dice."""
    from process_ai_core.export import DocumentContext

    contenido = "<h1>Título del procedimiento</h1><p>Párrafo con contenido sustantivo.</p>"
    pdf_ok, tmp_ok = _render(DocumentContext(is_approved=True), contenido)
    pdf_br, tmp_br = _render(DocumentContext(is_approved=False), contenido)
    try:
        # Sobre el documento COMPLETO: con portada, el cuerpo arranca en la pág. 2.
        texto_ok = "\n".join(_texto_por_pagina(pdf_ok))
        texto_br = "\n".join(_texto_por_pagina(pdf_br))
        for fragmento in ("Título del procedimiento", "Párrafo con contenido sustantivo"):
            assert fragmento in texto_ok and fragmento in texto_br
    finally:
        shutil.rmtree(tmp_ok, ignore_errors=True)
        shutil.rmtree(tmp_br, ignore_errors=True)


def test_marks_as_invalid_decide_por_is_approved():
    from process_ai_core.export import DocumentContext
    from process_ai_core.export.pdf_weasyprint import _marks_as_invalid

    assert _marks_as_invalid(None) is True
    assert _marks_as_invalid(DocumentContext(is_approved=False)) is True
    assert _marks_as_invalid(DocumentContext(is_approved=True)) is False


def test_la_marca_sigue_siendo_reproducible():
    """La marca es estática: no puede reintroducir variabilidad en el hash."""
    import time
    from process_ai_core.export import DocumentContext

    pdf_a, tmp_a = _render(DocumentContext(title="Doc", is_approved=False))
    bytes_a = pdf_a.read_bytes()
    time.sleep(2.2)
    pdf_b, tmp_b = _render(DocumentContext(title="Doc", is_approved=False))
    bytes_b = pdf_b.read_bytes()
    try:
        assert hashlib.sha256(bytes_a).hexdigest() == hashlib.sha256(bytes_b).hexdigest()
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)
        shutil.rmtree(tmp_b, ignore_errors=True)


# ── 5. El freeze persiste el content_html que normalizó ──────────────────────


def test_el_freeze_persiste_content_html_si_venia_vacio(session, storage):
    """
    render_frozen_html es best-effort al crear la versión. Si devolvió None, el
    HTML se derivaría en tiempo de render y la versión de la librería `markdown`
    seguiría siendo una entrada invisible del hash. El freeze lo congela.
    """
    from api.routes._freeze import freeze_approved_pdf

    doc, ws = _crear_documento(session)
    try:
        version = DocumentVersion(
            id=f"se-fh-{uuid.uuid4().hex[:8]}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="generated",
            content_json="{}", content_markdown=MARKDOWN_PIPELINE,
            content_html=None, is_current=True,
        )
        session.add(version)
        session.flush()

        assert freeze_approved_pdf(session, version) is True

        # HTML + PDF + hash quedan congelados en la misma transacción.
        assert version.content_html, "el freeze no persistió el content_html normalizado"
        assert "<h1>" in version.content_html
        assert version.pdf_storage_key and version.pdf_sha256

        # Se guarda la forma PORTABLE: sin URLs firmadas, que vencen.
        assert "token=" not in version.content_html
        assert "/api/v1/artifacts/" not in version.content_html
    finally:
        _limpiar(session, doc, ws)


def test_el_freeze_no_pisa_un_content_html_existente(session, storage):
    """Si el usuario editó a mano, ese HTML es la fuente de verdad."""
    from api.routes._freeze import freeze_approved_pdf

    doc, ws = _crear_documento(session)
    try:
        propio = "<h1>Editado a mano por el autor</h1>"
        version = DocumentVersion(
            id=f"se-fh2-{uuid.uuid4().hex[:8]}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="manual_edit",
            content_json="{}", content_markdown=MARKDOWN_PIPELINE,
            content_html=propio, is_current=True,
        )
        session.add(version)
        session.flush()

        assert freeze_approved_pdf(session, version) is True
        assert version.content_html == propio
    finally:
        _limpiar(session, doc, ws)
