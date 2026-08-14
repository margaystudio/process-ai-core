"""Borrar un documento tiene que borrarlo, aunque el sistema le haya puesto cosas encima.

El bug real: en la biblioteca de test, "Eliminar" no hacía nada. La API devolvía
500 con un `ForeignKeyViolation` sobre `document_relations`, porque el borrado
limpiaba runs, validaciones, versiones y audit logs pero NO las relaciones — que
las genera el propio motor de sugerencias, sin que el usuario haga nada. O sea:
cuanto más usaba el sistema, menos borrable era el documento.

Estos tests fijan las tres formas en que una relación toca a un documento y la
evidencia adjunta, que tenía el mismo problema latente.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.helpers import delete_document
from process_ai_core.db.models import (
    Document,
    DocumentRelation,
    DocumentVersion,
    EvidenceItem,
    Folder,
    Workspace,
)


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def ws(session):
    """El workspace y su carpeta: un documento siempre vive en una."""
    w = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(w)
    session.flush()
    f = Folder(id=_uid(), workspace_id=w.id, name="Operación", path="Operación")
    session.add(f)
    session.commit()
    return SimpleNamespace(id=w.id, folder_id=f.id)


def _documento(session, ws, nombre="Procedimiento"):
    d = Document(
        id=_uid(), workspace_id=ws.id, folder_id=ws.folder_id, domain="process",
        document_type="procedimiento", name=nombre, status="draft",
    )
    session.add(d)
    session.flush()
    v = DocumentVersion(
        id=_uid(), document_id=d.id, version_number=1, version_status="APPROVED",
        content_type="html", content_json="{}", content_markdown="Contenido",
        content_html="<p>Contenido</p>",
    )
    session.add(v)
    session.commit()
    return d, v


def _relacion(session, ws, *, document_id, source_version_id=None, target_id=None):
    r = DocumentRelation(
        id=_uid(), workspace_id=ws.id, document_id=document_id,
        source_type="document", source_id=document_id,
        relation_type="referencia", target_type="document",
        target_id=target_id or _uid(),
        source_document_version_id=source_version_id,
        status="sugerida", created_by_ai=True,
    )
    session.add(r)
    session.commit()
    return r


# ── El caso que devolvía 500 ────────────────────────────────────────────────

def test_se_borra_un_documento_que_tiene_una_relacion_sugerida(session, ws):
    doc, ver = _documento(session, ws)
    _relacion(session, ws, document_id=doc.id, source_version_id=ver.id)

    delete_document(session, doc.id)
    session.commit()

    assert session.query(Document).filter_by(id=doc.id).first() is None
    assert session.query(DocumentRelation).count() == 0


def test_tambien_se_borra_la_relacion_que_apuntaba_al_documento(session, ws):
    """Una relación cuyo destino desaparece no bloqueaba el borrado —`target_id`
    no tiene FK— pero quedaba apuntando a la nada y se mostraba rota en la UI."""
    doc, _ = _documento(session, ws)
    otro, otro_ver = _documento(session, ws, nombre="Instructivo")
    _relacion(session, ws, document_id=otro.id, source_version_id=otro_ver.id,
              target_id=doc.id)

    delete_document(session, doc.id)
    session.commit()

    assert session.query(DocumentRelation).count() == 0
    # El otro documento no se toca: solo se limpia el vínculo.
    assert session.query(Document).filter_by(id=otro.id).first() is not None


def test_no_se_lleva_puestas_las_relaciones_ajenas(session, ws):
    doc, ver = _documento(session, ws)
    otro, otro_ver = _documento(session, ws, nombre="Instructivo")
    _relacion(session, ws, document_id=doc.id, source_version_id=ver.id)
    ajena = _relacion(session, ws, document_id=otro.id, source_version_id=otro_ver.id)

    delete_document(session, doc.id)
    session.commit()

    quedan = session.query(DocumentRelation).all()
    assert [r.id for r in quedan] == [ajena.id]


def test_se_borra_la_evidencia_adjunta(session, ws):
    doc, _ = _documento(session, ws)
    session.add(EvidenceItem(
        id=_uid(), workspace_id=ws.id, document_id=doc.id,
        type="imagen", storage_url="workspaces/x/evidencia.png",
    ))
    session.commit()

    delete_document(session, doc.id)
    session.commit()

    assert session.query(EvidenceItem).count() == 0


def test_un_documento_sin_nada_encima_se_sigue_borrando(session, ws):
    doc, _ = _documento(session, ws)

    delete_document(session, doc.id)
    session.commit()

    assert session.query(Document).filter_by(id=doc.id).first() is None
    assert session.query(DocumentVersion).count() == 0
