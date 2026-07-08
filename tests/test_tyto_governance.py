"""Tests de gobernanza de la capa semántica (brief §9 — críticos).

- Una relación 'candidate' nunca se devuelve como confirmada.
- Tyto no usa documentos sin aprobar ni relaciones sin confirmar.
- El creador no confirma sus propias relaciones (segregación).
- merge de knowledge objects reapunta todas las document_relations
  (cubierto también en test_semantic_layer).
- Los document_chunks pertenecen a la versión aprobada vigente.
- Aislamiento por workspace.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa: F401 – registra modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.models import DocumentVersion, Folder, Process, User, Workspace
from process_ai_core.db.models_semantic import DocumentChunk, DocumentRelation, KnowledgeObject
from process_ai_core.semantic import RelationService, TytoQueryService
from process_ai_core.semantic.chunking import ChunkIndexService


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def workspace(session):
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(ws)
    session.commit()
    return ws


@pytest.fixture
def folder(session, workspace):
    f = Folder(id=_uid(), workspace_id=workspace.id, name="Ops", path="Ops")
    session.add(f)
    session.commit()
    return f


def _make_doc_with_version(
    session,
    workspace,
    folder,
    *,
    name="Cierre de caja",
    doc_status="approved",
    version_status="APPROVED",
    is_current=True,
    markdown="# Cierre de caja\n\nCargar la venta en el POS y avisar al supervisor.",
    created_by=None,
):
    doc = Process(
        id=_uid(), workspace_id=workspace.id, folder_id=folder.id,
        document_type="procedimiento", name=name, status=doc_status,
    )
    session.add(doc)
    session.flush()
    version = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=1,
        version_status=version_status, content_type="generated",
        content_json="{}", content_markdown=markdown,
        is_current=is_current, created_by=created_by,
    )
    session.add(version)
    session.flush()  # la versión debe existir en DB antes de setear la FK del documento
    if version_status == "APPROVED" and is_current:
        doc.approved_version_id = version.id
    session.commit()
    return doc, version


def _tyto() -> TytoQueryService:
    service = TytoQueryService()
    service._embedding_unavailable = True  # fallback léxico, sin llamadas externas
    return service


def _indexer() -> ChunkIndexService:
    service = ChunkIndexService()
    service._embedding_unavailable = True
    return service


def _relation(session, workspace, doc, version, ko, status="candidate", relation_type="usa"):
    rel = DocumentRelation(
        workspace_id=workspace.id, document_id=doc.id,
        source_type="document", source_id=doc.id,
        relation_type=relation_type, target_type=ko.type, target_id=ko.id,
        status=status, source_document_version_id=version.id,
        confidence=0.9,
    )
    session.add(rel)
    session.commit()
    return rel


def _ko(session, workspace, type="sistema", name="POS"):
    from process_ai_core.semantic import normalize_name

    ko = KnowledgeObject(
        workspace_id=workspace.id, type=type,
        canonical_name=name, normalized_name=normalize_name(name),
    )
    session.add(ko)
    session.commit()
    return ko


# ── Una candidate nunca cuenta como confirmada ────────────────────────────────

def test_candidate_no_aparece_en_relaciones_confirmadas(session, workspace, folder):
    doc, version = _make_doc_with_version(session, workspace, folder)
    ko = _ko(session, workspace)
    _relation(session, workspace, doc, version, ko, status="candidate")

    confirmed = _tyto().confirmed_relations(session, workspace.id, [doc.id])
    assert confirmed == []


def test_confirmar_cambia_estado_y_registra_quien(session, workspace, folder):
    doc, version = _make_doc_with_version(session, workspace, folder)
    ko = _ko(session, workspace)
    rel = _relation(session, workspace, doc, version, ko)
    approver = User(id=_uid(), email=f"ap-{_uid()[:6]}@x.com", name="Approver")
    session.add(approver)
    session.commit()

    RelationService().confirm(session, rel, approver.id)
    session.commit()

    assert rel.status == "confirmed"
    assert rel.confirmed_by == approver.id
    assert rel.confirmed_at is not None
    # ahora sí forma parte de la red
    assert len(_tyto().confirmed_relations(session, workspace.id, [doc.id])) == 1


def test_no_se_confirma_dos_veces_ni_se_confirma_rechazada(session, workspace, folder):
    doc, version = _make_doc_with_version(session, workspace, folder)
    ko = _ko(session, workspace)
    rel = _relation(session, workspace, doc, version, ko)
    user = User(id=_uid(), email=f"u-{_uid()[:6]}@x.com", name="U")
    session.add(user)
    session.commit()

    service = RelationService()
    service.confirm(session, rel, user.id)
    with pytest.raises(ValueError):
        service.confirm(session, rel, user.id)
    with pytest.raises(ValueError):
        service.reject(session, rel, user.id)


# ── Segregación de funciones ──────────────────────────────────────────────────

def test_creador_no_confirma_sus_propias_relaciones(session, workspace, folder):
    creator = User(id=_uid(), email=f"c-{_uid()[:6]}@x.com", name="Creator")
    other = User(id=_uid(), email=f"o-{_uid()[:6]}@x.com", name="Other")
    session.add_all([creator, other])
    session.commit()

    doc, version = _make_doc_with_version(session, workspace, folder, created_by=creator.id)
    ko = _ko(session, workspace)
    rel = _relation(session, workspace, doc, version, ko)

    service = RelationService()
    with pytest.raises(PermissionError):
        service.confirm(session, rel, creator.id)
    assert rel.status == "candidate"

    # Otro usuario sí puede
    service.confirm(session, rel, other.id)
    assert rel.status == "confirmed"


def test_creador_no_rechaza_sus_propias_relaciones(session, workspace, folder):
    creator = User(id=_uid(), email=f"c-{_uid()[:6]}@x.com", name="Creator")
    session.add(creator)
    session.commit()
    doc, version = _make_doc_with_version(session, workspace, folder, created_by=creator.id)
    ko = _ko(session, workspace)
    rel = _relation(session, workspace, doc, version, ko)

    with pytest.raises(PermissionError):
        RelationService().reject(session, rel, creator.id)


# ── Tyto: universo gobernado ──────────────────────────────────────────────────

def test_tyto_ignora_documentos_sin_aprobar(session, workspace, folder):
    # aprobado + indexado
    doc_ok, v_ok = _make_doc_with_version(session, workspace, folder, name="Aprobado")
    _indexer().index_version(session, v_ok)
    # borrador (IN_REVIEW) — jamás debe aparecer
    doc_draft, v_draft = _make_doc_with_version(
        session, workspace, folder, name="Borrador",
        doc_status="pending_validation", version_status="IN_REVIEW", is_current=False,
        markdown="# Borrador\n\nContenido con POS sin aprobar.",
    )
    # chunk plantado a mano en la versión no aprobada (simula un bug/carga vieja)
    session.add(DocumentChunk(
        document_version_id=v_draft.id, chunk_index=0,
        content="POS sin aprobar", section_title=None,
    ))
    session.commit()

    ctx = _tyto().retrieve(session, workspace_id=workspace.id, query="venta POS supervisor")
    doc_ids = {c.document_id for c in ctx.citations}
    assert doc_ids == {doc_ok.id}


def test_tyto_expande_solo_por_relaciones_confirmadas(session, workspace, folder):
    doc, version = _make_doc_with_version(session, workspace, folder)
    _indexer().index_version(session, version)

    pos = _ko(session, workspace, name="POS")
    sap = _ko(session, workspace, name="SAP ERP")
    _relation(session, workspace, doc, version, pos, status="confirmed")
    _relation(session, workspace, doc, version, sap, status="candidate", relation_type="depende_de")

    ctx = _tyto().retrieve(session, workspace_id=workspace.id, query="venta POS supervisor")
    entity_names = {e["name"] for e in ctx.related_entities}
    assert entity_names == {"POS"}  # la candidate no expande la red


def test_tyto_no_expande_hacia_documentos_no_aprobados(session, workspace, folder):
    doc, version = _make_doc_with_version(session, workspace, folder)
    _indexer().index_version(session, version)
    doc_draft, _ = _make_doc_with_version(
        session, workspace, folder, name="Relacionado sin aprobar",
        doc_status="pending_validation", version_status="IN_REVIEW", is_current=False,
    )
    # relación confirmada doc → doc_draft (documento destino NO aprobado)
    rel = DocumentRelation(
        workspace_id=workspace.id, document_id=doc.id,
        source_type="document", source_id=doc.id,
        relation_type="relacionado_con", target_type="document", target_id=doc_draft.id,
        status="confirmed", source_document_version_id=version.id,
    )
    session.add(rel)
    session.commit()

    ctx = _tyto().retrieve(session, workspace_id=workspace.id, query="venta POS supervisor")
    assert ctx.related_documents == []


def test_tyto_aislamiento_por_workspace(session, workspace, folder):
    doc, version = _make_doc_with_version(session, workspace, folder)
    _indexer().index_version(session, version)

    otro_ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="Otro", workspace_type="organization")
    session.add(otro_ws)
    otra_carpeta = Folder(id=_uid(), workspace_id=otro_ws.id, name="Ops", path="Ops")
    session.add(otra_carpeta)
    session.commit()
    doc2, v2 = _make_doc_with_version(
        session, otro_ws, otra_carpeta, name="Doc de otro tenant",
        markdown="# Otro\n\nVenta POS supervisor en otro workspace.",
    )
    _indexer().index_version(session, v2)

    ctx = _tyto().retrieve(session, workspace_id=workspace.id, query="venta POS supervisor")
    doc_ids = {c.document_id for c in ctx.citations}
    assert doc2.id not in doc_ids
    assert doc_ids == {doc.id}


# ── Chunks: pertenecen a la versión aprobada vigente ─────────────────────────

def test_chunks_solo_de_la_version_aprobada_vigente(session, workspace, folder):
    doc, v1 = _make_doc_with_version(session, workspace, folder)
    indexer = _indexer()
    indexer.index_version(session, v1)
    session.commit()
    assert session.query(DocumentChunk).filter_by(document_version_id=v1.id).count() > 0

    # Nueva versión aprobada reemplaza a la anterior
    v1.version_status = "OBSOLETE"
    v1.is_current = False
    v2 = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=2, version_status="APPROVED",
        content_type="generated", content_json="{}",
        content_markdown="# v2\n\nNuevo contenido del POS.", is_current=True,
    )
    session.add(v2)
    session.commit()

    indexer.index_version(session, v2)
    session.commit()

    # los chunks de la versión vieja se eliminaron; solo la vigente está indexada
    assert session.query(DocumentChunk).filter_by(document_version_id=v1.id).count() == 0
    assert session.query(DocumentChunk).filter_by(document_version_id=v2.id).count() > 0


def test_no_se_indexan_versiones_no_aprobadas(session, workspace, folder):
    _, v_draft = _make_doc_with_version(
        session, workspace, folder, doc_status="draft",
        version_status="DRAFT", is_current=False,
    )
    with pytest.raises(ValueError):
        _indexer().index_version(session, v_draft)
