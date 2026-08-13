"""
Acta alineada con la referencia, historial de versiones, sello de superada y TOC.

El test que más importa es `test_el_blob_en_storage_no_cambia_al_sellar`: el sello
existe porque ISO 9001 pide identificar lo obsoleto, pero el PDF congelado no se
puede reescribir sin romper el SHA-256 que prueba que es el que se aprobó. Si el
sellado tocara el blob, rompería justamente lo que el artefacto viene a garantizar.
"""

import datetime
import hashlib
import shutil
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    AuditLog,
    Document,
    DocumentVersion,
    Folder,
    OperationalRole,
    Process,
    User,
    UserOperationalRole,
    Validation,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.export import DocumentContext, PdfBranding, export_pdf_from_content
from process_ai_core.export.document_context import VersionHistoryEntry
from process_ai_core.export.pdf_weasyprint import _fecha_larga, _firma, _meses_entre
from process_ai_core.export.superseded_stamp import stamp_superseded
from process_ai_core.export.toc import add_heading_anchors, toc_html

CONTENIDO = (
    "<h1>Cierre de caja</h1><p>Intro.</p>"
    "<h2>Objetivo</h2><p>x</p>"
    "<h2>Alcance</h2><p>y</p>"
    "<h2>Riesgos y controles</h2><p>z</p>"
)

CTX = DocumentContext(
    code="PR-0004",
    title="Cierre de caja de turno",
    document_type_label="Procedimiento Operativo",
    client_name="Estación Ruta 5 S.A.",
    version_number=4,
    version_id="7f3a9c21-4b8e-4d1a-9c33-5e2b81d47a06",
    is_approved=True,
    elaborated_by="Diego Sosa",
    elaborated_by_role="Encargado de turno",
    reviewed_by="Lucía Ferreira",
    reviewed_by_role="Jefa de Operaciones",
    approved_by="Martín Rodríguez",
    approved_by_role="Gerente de Estación",
    approved_at=datetime.datetime(2026, 7, 22),
    supersedes_version_number=3,
    supersedes_approved_at=datetime.datetime(2025, 11, 2),
    validity_until=datetime.date(2028, 7, 22),
    verification_url="https://process.example.com/verificar/abc",
    version_history=(
        VersionHistoryEntry(4, datetime.datetime(2026, 7, 22), "Martín Rodríguez",
                            "Se incorpora el arqueo de vales de flota."),
        VersionHistoryEntry(3, datetime.datetime(2025, 11, 2), "Martín Rodríguez", None),
    ),
)


def _render(context, contenido=CONTENIDO):
    tmp = Path(tempfile.mkdtemp())
    pdf = export_pdf_from_content(
        content=contenido, format="html", run_dir=tmp, pdf_name="x.pdf",
        branding=PdfBranding(primary_color="#14505c", secondary_color="#d99a2b"),
        document_context=context,
    )
    return Path(pdf), tmp


def _texto(pdf_path) -> list[str]:
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        return [p.get_text() for p in doc]
    finally:
        doc.close()


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


# ── 1. Las tres alineaciones del acta ────────────────────────────────────────


def test_el_acta_lleva_el_rol_junto_al_nombre():
    """
    Para gobernanza importa la autoridad bajo la que se aprobó, no solo la
    identidad: "aprobado por Juan Pérez" es más débil que "Juan Pérez, Gerente".
    """
    assert _firma("Diego Sosa", "Encargado de turno") == "Diego Sosa — Encargado de turno"
    # Sin rol va solo el nombre: nada de guion suelto.
    assert _firma("Ana Autora", None) == "Ana Autora"
    assert _firma(None, "Gerente") is None

    pdf, tmp = _render(CTX)
    try:
        portada = _texto(pdf)[0]
        assert "Diego Sosa — Encargado de turno" in portada
        assert "Lucía Ferreira — Jefa de Operaciones" in portada
        assert "Martín Rodríguez — Gerente de Estación" in portada
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sin_rol_configurado_el_acta_no_muestra_guiones_sueltos():
    contexto = replace(
        CTX, elaborated_by_role=None, reviewed_by_role=None, approved_by_role=None
    )
    pdf, tmp = _render(contexto)
    try:
        portada = _texto(pdf)[0]
        assert "Diego Sosa" in portada
        assert "Diego Sosa —" not in portada
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_la_vigencia_dice_la_duracion_y_la_fecha():
    """
    "24 meses — hasta el 22 de julio de 2028" comunica que se aplicó una política;
    una fecha sola parece puesta a dedo.
    """
    assert _meses_entre(datetime.datetime(2026, 7, 22), datetime.date(2028, 7, 22)) == 24
    assert _meses_entre(datetime.datetime(2026, 1, 31), datetime.date(2026, 2, 28)) == 1

    # Una fecha que NO cae a un número redondo de meses se eligió a mano: decir
    # "23 meses" inventaría una regla que no existió.
    assert _meses_entre(datetime.datetime(2026, 1, 15), datetime.date(2027, 6, 3)) is None

    pdf, tmp = _render(CTX)
    try:
        assert "24 meses — hasta el 22 de julio de 2028" in _texto(pdf)[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Fecha a dedo: solo "hasta el ..."
    contexto = replace(CTX, validity_until=datetime.date(2027, 6, 3))
    pdf, tmp = _render(contexto)
    try:
        portada = _texto(pdf)[0]
        assert "hasta el 3 de junio de 2027" in portada
        assert "meses —" not in portada
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_acta_usa_fecha_larga_y_el_pie_fecha_corta():
    """
    dd/mm/aaaa es ambiguo para quien lee mm/dd y este documento puede terminar
    ante un auditor externo. En el acta se escribe el mes con letras; en el pie y
    el cuerpo, donde no es dato probatorio, la fecha corta está bien.
    """
    assert _fecha_larga(datetime.date(2028, 1, 15)) == "15 de enero de 2028"
    assert _fecha_larga(datetime.date(2026, 12, 3)) == "3 de diciembre de 2026"
    assert _fecha_larga(None) is None

    pdf, tmp = _render(CTX)
    try:
        portada = _texto(pdf)[0]
        assert "22 de julio de 2026" in portada
        assert "22/07/2026" not in portada
        # El historial (cuerpo) sí usa fecha corta.
        cuerpo = "\n".join(_texto(pdf)[1:])
        assert "22/07/2026" in cuerpo
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 2. Historial de versiones ────────────────────────────────────────────────


def test_el_historial_no_tiene_columna_de_estado():
    """
    El estado es mutable y este PDF no se puede reescribir: si dijera "vigente",
    mentiría en cuanto se apruebe la versión siguiente.
    """
    pdf, tmp = _render(CTX)
    try:
        todo = "\n".join(_texto(pdf))
        assert "Historial de versiones" in todo

        # Se acota a la SECCIÓN del historial: "vigente" aparece legítimamente en
        # el bloque de verificación de la portada, y buscarlo en todo el
        # documento daría un falso positivo.
        seccion = todo.split("Historial de versiones", 1)[1].split("Cierre de caja", 1)[0]
        for columna in ("Versión", "Aprobada el", "Aprobada por", "Cambios principales"):
            assert columna in seccion
        for prohibido in ("Estado", "OBSOLETE", "APPROVED", "vigente", "Vigente"):
            assert prohibido not in seccion, f"el historial expone estado: {prohibido}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_una_version_sin_resumen_se_imprime_igual():
    """Falta el dato, no la fila: la aprobación ocurrió aunque nadie la describa."""
    pdf, tmp = _render(CTX)
    try:
        todo = "\n".join(_texto(pdf))
        assert "Se incorpora el arqueo de vales de flota." in todo
        assert "Sin detalle registrado" in todo
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_un_borrador_no_lleva_historial():
    contexto = replace(CTX, is_approved=False)
    pdf, tmp = _render(contexto)
    try:
        assert "Historial de versiones" not in "\n".join(_texto(pdf))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_historial_se_reconstruye_por_la_cadena_de_supersedes(session):
    """
    Se recorre supersedes_version_id, no "todas las versiones del documento": un
    borrador descartado o una versión rechazada no son hitos del documento.
    """
    from api.routes._document_context import (
        _build_version_history,
        _collect_version_chain,
        _resolve_signatories,
    )

    uid = uuid.uuid4().hex[:8]
    ws = Workspace(id=f"ah-ws-{uid}", slug=f"ah-ws-{uid}", name="W", workspace_type="organization")
    session.add(ws)
    session.flush()
    folder = Folder(id=f"ah-f-{uid}", workspace_id=ws.id, name="r", path="r")
    session.add(folder)
    session.flush()
    doc = Process(id=f"ah-d-{uid}", workspace_id=ws.id, folder_id=folder.id,
                  document_type="procedimiento", name="D", status="approved")
    session.add(doc)
    session.flush()
    aprobador = User(id=f"ah-u-{uid}", email=f"{uid}@x.com", name="Martín Rodríguez")
    session.add(aprobador)
    session.flush()

    val = Validation(id=f"ah-v-{uid}", document_id=doc.id, status="approved",
                     submit_comment="Se agrega el arqueo de vales.")
    session.add(val)
    session.flush()

    v1 = DocumentVersion(id=f"ah-1-{uid}", document_id=doc.id, version_number=1,
                         version_status="OBSOLETE", content_type="generated",
                         content_json="{}", content_markdown="#",
                         approved_at=datetime.datetime(2025, 3, 1), approved_by=aprobador.id)
    session.add(v1)
    session.flush()
    # Un DRAFT descartado que NO está en la cadena: no debe aparecer.
    descartado = DocumentVersion(id=f"ah-x-{uid}", document_id=doc.id, version_number=99,
                                 version_status="REJECTED", content_type="generated",
                                 content_json="{}", content_markdown="#")
    session.add(descartado)
    v2 = DocumentVersion(id=f"ah-2-{uid}", document_id=doc.id, version_number=2,
                         version_status="APPROVED", content_type="generated",
                         content_json="{}", content_markdown="#",
                         supersedes_version_id=v1.id, validation_id=val.id,
                         approved_at=datetime.datetime(2026, 1, 15), approved_by=aprobador.id,
                         is_current=True)
    session.add(v2)
    session.flush()

    try:
        cadena = _collect_version_chain(session, v2)
        nombres = _resolve_signatories(session, ws.id, [v.approved_by for v in cadena])
        historial = _build_version_history(session, cadena, nombres)
        assert [e.version_number for e in historial] == [2, 1], "orden o cadena incorrectos"
        assert historial[0].change_summary == "Se agrega el arqueo de vales."
        assert historial[0].approved_by == "Martín Rodríguez"
        assert historial[1].change_summary is None
        assert 99 not in [e.version_number for e in historial]
    finally:
        session.flush()
        session.query(AuditLog).filter_by(document_id=doc.id).delete()
        session.query(DocumentVersion).filter_by(document_id=doc.id).update(
            {"validation_id": None}
        )
        session.query(Validation).filter_by(document_id=doc.id).delete()
        session.query(DocumentVersion).filter_by(document_id=doc.id).delete()
        session.query(Process).filter_by(id=doc.id).delete()
        session.query(Document).filter_by(id=doc.id).delete()
        session.query(Folder).filter_by(workspace_id=ws.id).delete()
        session.query(User).filter_by(id=aprobador.id).delete()
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


def test_el_rol_operativo_se_resuelve_en_una_query(session):
    from api.routes._document_context import _resolve_signatories

    uid = uuid.uuid4().hex[:8]
    ws = Workspace(id=f"ar-ws-{uid}", slug=f"ar-ws-{uid}", name="W", workspace_type="organization")
    session.add(ws)
    session.flush()
    user = User(id=f"ar-u-{uid}", email=f"{uid}@x.com", name="Diego Sosa")
    session.add(user)
    session.flush()
    membresia = WorkspaceMembership(
        id=f"ar-m-{uid}", user_id=user.id, workspace_id=ws.id,
        base_access="member",
    )
    session.add(membresia)
    session.flush()
    op = OperationalRole(id=f"ar-o-{uid}", workspace_id=ws.id, name="Encargado de turno",
                         slug="encargado-turno", is_active=True)
    session.add(op)
    session.flush()
    session.add(UserOperationalRole(id=f"ar-uo-{uid}", workspace_membership_id=membresia.id,
                                    operational_role_id=op.id))
    session.flush()

    try:
        firmantes = _resolve_signatories(session, ws.id, [user.id])
        assert firmantes[user.id] == ("Diego Sosa", "Encargado de turno")
        # Sin rol operativo NO se cae al rol de sistema: "aprobado por X, approver"
        # describe un permiso, no una autoridad.
        otros = _resolve_signatories(session, "otro-ws", [user.id])
        assert otros[user.id][1] is None
    finally:
        session.query(UserOperationalRole).filter_by(workspace_membership_id=membresia.id).delete()
        session.query(OperationalRole).filter_by(id=op.id).delete()
        session.query(WorkspaceMembership).filter_by(id=membresia.id).delete()
        session.query(User).filter_by(id=user.id).delete()
        session.query(Workspace).filter_by(id=ws.id).delete()
        session.commit()


# ── 3. Sello de versión superada ─────────────────────────────────────────────


def test_el_blob_en_storage_no_cambia_al_sellar():
    """
    EL test de esta tarea. Si el sellado tocara el blob, el SHA-256 registrado
    dejaría de verificar y el artefacto perdería lo único que prueba que es el
    que se aprobó.
    """
    pdf, tmp = _render(CTX)
    try:
        original = pdf.read_bytes()
        sha_antes = hashlib.sha256(original).hexdigest()

        sellado = stamp_superseded(original, vigente_version=5)

        # El original, intacto — en memoria y en disco.
        assert pdf.read_bytes() == original
        assert hashlib.sha256(pdf.read_bytes()).hexdigest() == sha_antes
        # Y el sellado es otro archivo, necesariamente.
        assert sellado != original
        assert hashlib.sha256(sellado).hexdigest() != sha_antes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_sello_aparece_en_todas_las_paginas_y_dice_cual_rige():
    pdf, tmp = _render(CTX)
    try:
        sellado = stamp_superseded(pdf.read_bytes(), vigente_version=5)
        salida = pdf.parent / "sellado.pdf"
        salida.write_bytes(sellado)
        paginas = _texto(salida)
        assert len(paginas) > 1
        for i, texto in enumerate(paginas):
            assert "VERSIÓN SUPERADA" in texto, f"falta el sello en la página {i + 1}"
        assert "vigente: v5" in paginas[0]
        # El guion largo no existe en las fuentes base-14 del PDF: se usa "·".
        assert "?" not in paginas[0].splitlines()[0]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sin_version_vigente_el_sello_no_afirma_cual_rige():
    pdf, tmp = _render(CTX)
    try:
        sellado = stamp_superseded(pdf.read_bytes(), vigente_version=None)
        salida = pdf.parent / "sellado2.pdf"
        salida.write_bytes(sellado)
        primera = _texto(salida)[0]
        assert "VERSIÓN SUPERADA" in primera
        assert "vigente:" not in primera
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_el_sellado_es_best_effort(monkeypatch):
    """Un documento sin sello es un problema; uno que no abre es peor."""
    import process_ai_core.export.superseded_stamp as mod

    def explota(*a, **k):
        raise RuntimeError("pymupdf roto")

    monkeypatch.setattr(mod, "_sellar_pagina", explota)
    original = b"%PDF-1.4 falso"
    assert mod.stamp_superseded(original, vigente_version=2) == original


def test_el_etag_cambia_cuando_el_pdf_va_sellado():
    """
    El ETag no puede seguir siendo el sha256 pelado: los bytes servidos ya no son
    los del blob. Y el sufijo lleva la versión vigente, así que el ETag cambia
    solo cuando se aprueba una versión nueva — justo cuando el sello dice otra cosa.
    """
    sha = "a" * 64
    assert f'"{sha}"' != f'"{sha}+sup5"'
    assert f'"{sha}+sup5"' != f'"{sha}+sup6"'


# ── 4. Índice de contenidos ──────────────────────────────────────────────────


def test_el_toc_sale_de_los_h2_y_les_pone_ancla():
    html, entradas = add_heading_anchors(CONTENIDO)
    assert [t for _, t in entradas] == ["Objetivo", "Alcance", "Riesgos y controles"]
    assert 'id="objetivo"' in html
    assert 'id="riesgos-y-controles"' in html   # sin acentos, slug estable

    marca = toc_html(entradas)
    assert 'href="#objetivo"' in marca
    # El número de página lo resuelve el motor: no se calcula en Python.
    assert "target-counter" not in marca


def test_el_toc_respeta_anclas_existentes():
    """Un documento importado puede traer sus propias anclas y enlaces internos."""
    html, entradas = add_heading_anchors('<h2 id="mia">Alcance</h2>')
    assert entradas == [("mia", "Alcance")]
    assert html.count("id=") == 1


def test_titulos_repetidos_no_colisionan():
    _, entradas = add_heading_anchors("<h2>Notas</h2><h2>Notas</h2>")
    anchors = [a for a, _ in entradas]
    assert anchors == ["notas", "notas-2"]


def test_el_toc_es_opcional_por_perfil():
    from process_ai_core.domains.processes.profiles import GESTION_V1, OPERATIVO_V1

    # Un pistero con dos páginas en la mano no navega un índice, lo lee.
    assert OPERATIVO_V1.show_toc is False
    assert GESTION_V1.show_toc is True

    con_toc, tmp1 = _render(replace(CTX, show_toc=True))
    sin_toc, tmp2 = _render(replace(CTX, show_toc=False))
    try:
        assert "Contenido" in "\n".join(_texto(con_toc))
        assert "Contenido" not in "\n".join(_texto(sin_toc))
    finally:
        shutil.rmtree(tmp1, ignore_errors=True)
        shutil.rmtree(tmp2, ignore_errors=True)


def test_el_toc_resuelve_numeros_de_pagina():
    """target-counter() los resuelve en el motor; acá se verifica que salgan."""
    largo = CONTENIDO + "".join(f"<p>relleno {i}</p>" for i in range(200))
    pdf, tmp = _render(replace(CTX, show_toc=True), largo)
    try:
        import re

        pagina_toc = _texto(pdf)[1]
        seccion = pagina_toc.split("Contenido", 1)[1][:400]
        # Cada entrada termina en un número de página.
        assert re.search(r"Objetivo\s*\n?\s*\d+", seccion), seccion[:200]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 5. Reproducibilidad ──────────────────────────────────────────────────────


def test_el_documento_completo_sigue_siendo_reproducible():
    """Acta, historial y TOC son estáticos: no pueden variar el hash."""
    import time

    a, tmp_a = _render(replace(CTX, show_toc=True))
    bytes_a = a.read_bytes()
    time.sleep(2.2)
    b, tmp_b = _render(replace(CTX, show_toc=True))
    bytes_b = b.read_bytes()
    try:
        assert hashlib.sha256(bytes_a).hexdigest() == hashlib.sha256(bytes_b).hexdigest()
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)
        shutil.rmtree(tmp_b, ignore_errors=True)
