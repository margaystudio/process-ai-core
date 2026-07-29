"""
Integridad de evidencias + sistema de diseño del PDF.

Dos bloques:

1. **Integridad** (la parte que puede costar caro): WeasyPrint no lanza cuando no
   puede resolver una imagen — la omite y sigue. Si eso pasa durante el freeze,
   el artefacto de auditoría se congela SIN las evidencias, con hash calculado y
   registrado, y ya no hay forma de notarlo. Acá se verifica que aborte.

2. **Diseño**: color de marca aplicado con contraste calculado, portada con lo
   que queda congelado al aprobar (y NADA mutable), header corrido, pie de tres
   campos y tablas que cortan bien.
"""

import datetime
import hashlib
import io
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest

from process_ai_core.export import (
    ASSET_BASE_URL,
    DocumentContext,
    IncompletePdfError,
    PdfBranding,
    StorageAssetFetcher,
    export_pdf_from_content,
    verify_pdf_images,
)
from process_ai_core.export.color import (
    contrast_ratio,
    on_color,
    readable_on_white,
    resolve_palette,
)
from process_ai_core.export.integrity import count_embedded_images
from process_ai_core.export.pdf_weasyprint import _footer_css, _wrap_html, root_variables_css
from process_ai_core.export.qr import qr_data_uri
from process_ai_core.storage.local import LocalDiskStorage


def _png(color=(30, 90, 160), size=(60, 40)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def _texto_por_pagina(pdf_path) -> list[str]:
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


# ── 1. Integridad de las evidencias ──────────────────────────────────────────


@pytest.fixture
def storage_con_assets(tmp_path, monkeypatch):
    """Storage temporal con una imagen del run, apuntado desde el fetcher."""
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    store.put("workspaces/ws-1/runs/run-1/assets/paso1.png", _png(), "image/png")
    store.put(
        "workspaces/ws-1/editor-uploads/doc-1/subida.png", _png((200, 60, 60)), "image/png"
    )

    import process_ai_core.storage as storage_mod

    monkeypatch.setattr(storage_mod, "get_storage", lambda: store)
    return store


def _render_con_fetcher(html, tmp_path, **fetcher_kwargs):
    fetcher = StorageAssetFetcher(
        workspace_id="ws-1", run_id="run-1", document_id="doc-1", **fetcher_kwargs
    )
    pdf = export_pdf_from_content(
        content=html,
        format="html",
        run_dir=tmp_path,
        pdf_name="x.pdf",
        base_url=ASSET_BASE_URL,
        url_fetcher=fetcher,
    )
    return Path(pdf).read_bytes(), fetcher


def test_las_imagenes_se_leen_de_storage_sin_salir_a_la_red(storage_con_assets, tmp_path):
    """
    El fetcher resuelve contra object storage. Si intentara HTTP, el host
    centinela no existe y la imagen no estaría.
    """
    html = f'<h1>D</h1><img src="{ASSET_BASE_URL}assets/paso1.png">'
    pdf_bytes, fetcher = _render_con_fetcher(html, tmp_path)

    assert not fetcher.failures
    assert fetcher.expected_raster_count == 1
    assert count_embedded_images(pdf_bytes) >= 1
    verify_pdf_images(pdf_bytes, fetcher)  # no lanza


def test_tambien_resuelve_las_imagenes_del_editor_manual(storage_con_assets, tmp_path):
    html = f'<h1>D</h1><img src="{ASSET_BASE_URL}api/v1/documents/doc-1/editor-images/subida.png">'
    pdf_bytes, fetcher = _render_con_fetcher(html, tmp_path)

    assert not fetcher.failures
    verify_pdf_images(pdf_bytes, fetcher)


def test_una_imagen_irresoluble_ABORTA_en_vez_de_producir_un_pdf_mutilado(
    storage_con_assets, tmp_path
):
    """
    EL test de esta tarea. WeasyPrint omite la imagen sin lanzar: el PDF se
    genera igual, más chico y sin la evidencia. Sin este control se le calcularía
    el SHA-256 y quedaría registrado como el documento oficial.
    """
    html = (
        f'<h1>D</h1><img src="{ASSET_BASE_URL}assets/paso1.png">'
        f'<img src="{ASSET_BASE_URL}assets/no-existe.png">'
    )
    pdf_bytes, fetcher = _render_con_fetcher(html, tmp_path)

    # El PDF SE GENERÓ igual — esa es exactamente la trampa.
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(fetcher.failures) == 1

    with pytest.raises(IncompletePdfError) as exc:
        verify_pdf_images(pdf_bytes, fetcher, contexto="versión X")
    assert "no-existe.png" in str(exc.value)
    assert "incompleto" in str(exc.value)


def test_el_freeze_no_congela_un_documento_con_evidencias_faltantes(
    storage_con_assets, tmp_path, monkeypatch
):
    """Extremo a extremo: el freeze devuelve False y NO persiste nada."""
    from api.routes import _freeze as freeze_mod
    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.models import (
        AuditLog,
        Document,
        DocumentVersion,
        Folder,
        Process,
        Workspace,
    )

    monkeypatch.setattr(freeze_mod, "get_storage", lambda: storage_con_assets)

    uid = uuid.uuid4().hex[:8]
    with get_db_session() as session:
        ws = Workspace(
            id=f"ev-ws-{uid}", slug=f"ev-ws-{uid}", name="Ev", workspace_type="organization"
        )
        session.add(ws)
        session.flush()
        folder = Folder(id=f"ev-fol-{uid}", workspace_id=ws.id, name="root", path="root")
        session.add(folder)
        session.flush()
        doc = Process(
            id=f"ev-doc-{uid}", workspace_id=ws.id, folder_id=folder.id,
            document_type="procedimiento", name="Con evidencias", status="approved",
        )
        session.add(doc)
        session.flush()
        version = DocumentVersion(
            id=f"ev-ver-{uid}", document_id=doc.id, version_number=1,
            version_status="APPROVED", content_type="generated",
            content_json="{}", content_markdown="# D",
            # La evidencia referenciada NO está en storage.
            content_html='<h1>D</h1><img src="assets/evidencia-perdida.png">',
            run_id=None, is_current=True,
        )
        session.add(version)
        session.flush()

        try:
            assert freeze_mod.freeze_approved_pdf(session, version) is False
            assert version.pdf_storage_key is None, (
                "se congeló un artefacto al que le faltan evidencias"
            )
            assert version.pdf_sha256 is None
        finally:
            session.flush()
            session.query(AuditLog).filter_by(document_id=doc.id).delete()
            session.query(DocumentVersion).filter_by(document_id=doc.id).delete()
            session.query(Process).filter_by(id=doc.id).delete()
            session.query(Document).filter_by(id=doc.id).delete()
            session.query(Folder).filter_by(workspace_id=ws.id).delete()
            session.query(Workspace).filter_by(id=ws.id).delete()
            session.commit()


def test_el_freeze_ya_no_firma_urls_de_artefactos():
    """
    Las imágenes dejaron de bajarse por HTTP desde la propia API: durante el
    freeze eso era una auto-llamada mientras se atendía la aprobación.
    """
    import api.routes._freeze as freeze_mod

    assert not hasattr(freeze_mod, "sign_artifact_url")
    reescrito = freeze_mod._rewrite_img_src_to_assets('<img src="assets/a.png">')
    assert reescrito == f'<img src="{ASSET_BASE_URL}assets/a.png">'
    assert "token=" not in reescrito


# ── 2. Sistema de color ──────────────────────────────────────────────────────


def test_el_color_del_workspace_llega_al_pdf():
    """Antes se leía de la metadata y ningún exportador lo usaba."""
    branding = PdfBranding(primary_color="#0b3d2e", secondary_color="#c8a04a")
    variables = root_variables_css(branding)
    assert "--pdf-primary: #0b3d2e" in variables
    assert "--pdf-secondary: #c8a04a" in variables


def test_sin_marca_definida_cae_a_un_par_neutro():
    variables = root_variables_css(None)
    assert "--pdf-primary:" in variables and "--pdf-secondary:" in variables
    # Nada de verde/rojo: el color del documento no debe leerse como un estado.
    assert "#1f3a5f" in variables


@pytest.mark.parametrize(
    "primary",
    ["#0b3d2e", "#f2c94c", "#ffffff", "#000000", "#2d9cdb", "#c8ff00"],
)
def test_el_texto_del_th_siempre_contrasta_con_el_color_de_marca(primary):
    """
    Un primary claro con texto blanco fijo da una cabecera de tabla ilegible.
    Se elige por contraste medido, y el resultado siempre supera AA.
    """
    texto = on_color(primary)
    assert contrast_ratio(primary, texto) >= 4.5, (
        f"la cabecera de tabla con primary={primary} no llega a AA"
    )


@pytest.mark.parametrize("color", ["#f2c94c", "#c8ff00", "#ffffff", "#0b3d2e"])
def test_los_titulos_son_legibles_sobre_blanco(color):
    """
    El color de marca sirve para rellenar pero no siempre para escribir: un
    amarillo como color de los h1 desaparece en papel.
    """
    assert contrast_ratio(readable_on_white(color), "#ffffff") >= 4.5


def test_un_color_invalido_no_rompe_el_render():
    for basura in ("no-es-color", "", "#12", None, 123):
        paleta = resolve_palette(basura, basura)  # type: ignore[arg-type]
        assert paleta["pdf-primary"].startswith("#")


# ── 3. Portada ───────────────────────────────────────────────────────────────


CTX_APROBADO = DocumentContext(
    code="PRO-CAL-001",
    title="Recepción de combustible",
    document_type_label="Procedimiento Operativo",
    client_name="Estación ACME",
    version_number=3,
    version_id="7f3a9c21-4b8e-4d1a-9c33-5e2b81d47a06",
    is_approved=True,
    elaborated_by="Ana Autora",
    reviewed_by="Beto Revisor",
    approved_by="Carla Jefa",
    approved_at=datetime.datetime(2026, 1, 15),
    supersedes_version_number=2,
    supersedes_approved_at=datetime.datetime(2025, 3, 1),
    validity_until=datetime.date(2027, 1, 15),
    verification_url="https://app.example.com/verificar/7f3a9c21",
)


def _render_ctx(context, branding=None, contenido="<h1>Cuerpo</h1><p>Texto.</p>"):
    tmp = Path(tempfile.mkdtemp())
    pdf = export_pdf_from_content(
        content=contenido, format="html", run_dir=tmp, pdf_name="x.pdf",
        branding=branding, document_context=context,
    )
    return Path(pdf), tmp


def test_la_portada_lleva_lo_que_queda_congelado_al_aprobar():
    pdf, tmp = _render_ctx(CTX_APROBADO)
    try:
        portada = _texto_por_pagina(pdf)[0]
        for esperado in (
            "Recepción de combustible",   # título
            "PRO-CAL-001",                # código
            "Versión 3",                  # número de versión
            "Estación ACME",              # cliente
            "Ana Autora", "Beto Revisor", "Carla Jefa",   # firmas
            # Fecha larga en el acta: dd/mm es ambiguo para quien lee mm/dd y
            # este documento puede terminar ante un auditor externo.
            "15 de enero de 2026",        # fecha de aprobación
            "15 de enero de 2027",        # vigencia
            "7f3a9c21",                   # version_id en el bloque de verificación
        ):
            assert esperado in portada, f"falta en la portada: {esperado}"
        # El tipo documental va como antetítulo; PyMuPDF separa el tracking amplio.
        assert "OPERATIVO" in portada.replace(" ", "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_la_portada_NO_lleva_datos_mutables():
    """
    Estado, carpeta y run cambian sin que cambie el documento. Impresos harían
    que el PDF mienta apenas alguien mueve el documento de carpeta (ADR-018).
    """
    pdf, tmp = _render_ctx(CTX_APROBADO)
    try:
        portada = _texto_por_pagina(pdf)[0]
        for prohibido in ("Estado", "Carpeta", "run_id", "OBSOLETE", "DRAFT", "IN_REVIEW"):
            assert prohibido not in portada, f"la portada expone un dato mutable: {prohibido}"
        # "Aprobado por" SÍ va: es una firma que queda congelada. Lo que no va es
        # el ESTADO como badge — una línea que sea solo la palabra.
        lineas = {l.strip().upper() for l in portada.splitlines()}
        assert "APROBADO" not in lineas, "la portada tiene un badge de estado"
        assert "VIGENTE" not in lineas
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_la_portada_se_degrada_sin_code_ni_vigencia():
    """`code` y `validity_until` todavía llegan siempre en None."""
    from dataclasses import replace

    contexto = replace(CTX_APROBADO, code=None, validity_until=None)
    pdf, tmp = _render_ctx(contexto)
    try:
        portada = _texto_por_pagina(pdf)[0]
        assert "Recepción de combustible" in portada
        assert "Versión 3" in portada
        assert "PRO-CAL-001" not in portada
        # Sin fila vacía ni guion suelto donde iría la vigencia. (El bloque del QR
        # se titula "Verificación de vigencia": eso es otra cosa y sí va.)
        sin_espacios = portada.upper().replace(" ", "")
        assert "VIGENCIADELAAPROBACIÓN" not in sin_espacios
        assert "—" not in portada.split("RESPONSABLES")[0].split("Acta")[-1][:200]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sin_aprobar_el_acta_se_llama_responsables():
    """Todavía no hay acta: no se puede titular como si la hubiera."""
    from dataclasses import replace

    contexto = replace(
        CTX_APROBADO, is_approved=False, approved_by=None, approved_at=None,
        supersedes_version_number=None, validity_until=None,
    )
    pdf, tmp = _render_ctx(contexto)
    try:
        portada = _texto_por_pagina(pdf)[0].replace(" ", "").upper()
        assert "RESPONSABLES" in portada
        assert "ACTADEAPROBACIÓN" not in portada
        assert "SINVALOROPERATIVO" in portada  # el bloque de invalidación va acá
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_la_portada_no_tiene_header_ni_pie_corridos():
    pdf, tmp = _render_ctx(CTX_APROBADO, contenido="<h1>C</h1>" + "<p>x</p>" * 80)
    try:
        paginas = _texto_por_pagina(pdf)
        assert len(paginas) > 1
        assert "Página 1 de" not in paginas[0]
        assert "Copia no controlada" not in paginas[0]
        # Y en el cuerpo sí.
        assert "Página 2 de" in paginas[1]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_qr_es_deterministico():
    """El QR entra en el PDF congelado: si variara arruinaría el SHA-256."""
    a = qr_data_uri("https://app.example.com/verificar/abc")
    b = qr_data_uri("https://app.example.com/verificar/abc")
    assert a and a == b
    assert a.startswith("data:image/png;base64,")
    assert qr_data_uri("https://app.example.com/verificar/otro") != a
    assert qr_data_uri("") is None


# ── 4. Header corrido y pie ──────────────────────────────────────────────────


def test_el_header_corrido_lleva_identidad_y_version():
    pdf, tmp = _render_ctx(CTX_APROBADO, contenido="<h1>C</h1>" + "<p>x</p>" * 80)
    try:
        cuerpo = _texto_por_pagina(pdf)[1]
        assert "Recepción de combustible" in cuerpo
        assert "Versión 3" in cuerpo
        # Sin estado: cambia sin que cambie el documento.
        assert "APROBADO" not in cuerpo
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_pie_tiene_los_tres_campos():
    pdf, tmp = _render_ctx(CTX_APROBADO, contenido="<h1>C</h1>" + "<p>x</p>" * 80)
    try:
        cuerpo = _texto_por_pagina(pdf)[1]
        assert "PRO-CAL-001 · Recepción de combustible · v3" in cuerpo
        assert "Copia no controlada — verificá la vigencia en línea" in cuerpo
        assert "Página 2 de" in cuerpo
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_pie_de_un_borrador_dice_que_esta_invalidado():
    from dataclasses import replace

    contexto = replace(CTX_APROBADO, is_approved=False)
    pdf, tmp = _render_ctx(contexto, contenido="<h1>C</h1>" + "<p>x</p>" * 80)
    try:
        assert "sin valor operativo" in _texto_por_pagina(pdf)[1]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_pie_escapa_las_comillas_del_titulo():
    """El título entra en un `content: "..."` de CSS."""
    contexto = DocumentContext(title='Manual "oficial" \\ 2026', version_number=1)
    css = _footer_css(contexto)
    assert '\\"oficial\\"' in css and "\\\\" in css


# ── 5. Tablas ────────────────────────────────────────────────────────────────


def test_una_tabla_larga_corta_de_pagina_y_repite_el_encabezado():
    """
    Antes era `table { page-break-inside: avoid }`: una tabla más larga que una
    página no tenía dónde caber. Ahora el corte va por fila y el thead se repite.
    """
    filas = "".join(
        f"<tr><td>{i}</td><td>Acción {i}</td><td>Playero</td></tr>" for i in range(1, 61)
    )
    contenido = (
        "<h1>C</h1><table><thead><tr><th>Paso</th><th>Acción</th>"
        f"<th>Responsable</th></tr></thead><tbody>{filas}</tbody></table>"
    )
    pdf, tmp = _render_ctx(CTX_APROBADO, contenido=contenido)
    try:
        paginas = _texto_por_pagina(pdf)
        con_tabla = [p for p in paginas if "Acción" in p]
        assert len(con_tabla) >= 2, "la tabla larga no se repartió en varias páginas"
        for pagina in con_tabla:
            assert "Responsable" in pagina, "el encabezado no se repitió al cortar"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 6. Reproducibilidad ──────────────────────────────────────────────────────


def test_el_rediseño_sigue_siendo_reproducible():
    """Portada, QR y paleta son estáticos: no pueden variar el hash."""
    import time

    branding = PdfBranding(primary_color="#0b3d2e", secondary_color="#c8a04a")
    pdf_a, tmp_a = _render_ctx(CTX_APROBADO, branding)
    bytes_a = pdf_a.read_bytes()
    time.sleep(2.2)
    pdf_b, tmp_b = _render_ctx(CTX_APROBADO, branding)
    bytes_b = pdf_b.read_bytes()
    try:
        assert hashlib.sha256(bytes_a).hexdigest() == hashlib.sha256(bytes_b).hexdigest()
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)
        shutil.rmtree(tmp_b, ignore_errors=True)
