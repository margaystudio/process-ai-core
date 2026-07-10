"""Tests de la capa semántica: extracción, matching en cascada, candidatas,
dedup/merge de knowledge objects y chunking.

Complementa tests/test_tyto_governance.py (tests de gobernanza ADR-002/006).
"""

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import process_ai_core.db.models  # noqa: F401 – registra modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.models import Document, DocumentVersion, Folder, Process, User, Workspace
from process_ai_core.db.models_semantic import DocumentRelation, KnowledgeObject
from process_ai_core.semantic import (
    RelationService,
    SemanticExtractionService,
    normalize_name,
    split_markdown_into_chunks,
)
from process_ai_core.semantic.extraction import ExtractionResult, ExtractedEntity, ExtractedRelation
from process_ai_core.semantic.pipeline import run_semantic_pipeline


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


def _make_document(session, workspace, folder, name="Cierre de caja") -> Process:
    doc = Process(
        id=_uid(),
        workspace_id=workspace.id,
        folder_id=folder.id,
        document_type="procedimiento",
        name=name,
        status="approved",
    )
    session.add(doc)
    session.commit()
    return doc


def _make_approved_version(session, doc, markdown="# Cierre\n\nUsar el POS.") -> DocumentVersion:
    version = DocumentVersion(
        id=_uid(),
        document_id=doc.id,
        version_number=1,
        version_status="APPROVED",
        content_type="generated",
        content_json="{}",
        content_markdown=markdown,
        is_current=True,
    )
    session.add(version)
    session.flush()  # la versión debe existir en DB antes de setear la FK del documento
    doc.approved_version_id = version.id
    session.commit()
    return version


def _extraction(*relations) -> ExtractionResult:
    result = ExtractionResult()
    for relation_type, entity_type, name, confidence in relations:
        entity = ExtractedEntity(type=entity_type, canonical_name=name)
        result.entities.append(entity)
        result.relations.append(
            ExtractedRelation(
                relation_type=relation_type,
                entity=entity,
                confidence=confidence,
                evidence_text=f"...{name}...",
            )
        )
    return result


class FakeLLM:
    """LLMProvider falso: devuelve el JSON con el que se construye."""

    def __init__(self, payload: dict):
        self._payload = payload

    def complete_json(self, *, system: str, user: str, temperature: float = 0.2) -> str:
        return json.dumps(self._payload)


# ── Normalizador ──────────────────────────────────────────────────────────────

def test_normalize_name_quita_acentos_y_colapsa_espacios():
    assert normalize_name("  SAP  ERP ") == "sap erp"
    assert normalize_name("Recepción de Mercadería") == "recepcion de mercaderia"
    assert normalize_name("") == ""


# ── Extractor (parseo/saneo de la respuesta del modelo) ──────────────────────

def test_extraction_parsea_y_descarta_tipos_invalidos():
    service = SemanticExtractionService(
        llm=FakeLLM(
            {
                "relations": [
                    {"relation_type": "usa", "entity_type": "sistema", "entity_name": "POS",
                     "confidence": 0.94, "evidence": "cargar la venta en el POS"},
                    {"relation_type": "requiere", "entity_type": "rol", "entity_name": "Supervisor",
                     "confidence": 0.88, "evidence": "avisar al supervisor"},
                    # inválidos: tipo de relación y tipo de entidad desconocidos
                    {"relation_type": "inventada", "entity_type": "sistema", "entity_name": "X"},
                    {"relation_type": "usa", "entity_type": "alien", "entity_name": "Y"},
                    # duplicado exacto (se descarta)
                    {"relation_type": "usa", "entity_type": "sistema", "entity_name": "POS"},
                ]
            }
        )
    )
    result = service.extract(title="Cierre de caja", content="texto")
    assert len(result.relations) == 2
    assert result.relations[0].entity.normalized_name == "pos"
    assert result.relations[1].relation_type == "requiere"


def test_extraction_respuesta_no_json_devuelve_vacio():
    class BrokenLLM:
        def complete_json(self, *, system, user, temperature=0.2):
            return "esto no es json"

    result = SemanticExtractionService(llm=BrokenLLM()).extract(title="t", content="c")
    assert result.relations == []


def test_extraction_confidence_se_acota_a_0_1():
    service = SemanticExtractionService(
        llm=FakeLLM({"relations": [
            {"relation_type": "usa", "entity_type": "sistema", "entity_name": "POS", "confidence": 7}
        ]})
    )
    result = service.extract(title="t", content="c")
    assert result.relations[0].confidence == 1.0


# ── Matching en cascada ───────────────────────────────────────────────────────

def test_matching_exacto(session, workspace):
    ko = KnowledgeObject(
        workspace_id=workspace.id, type="sistema",
        canonical_name="SAP ERP", normalized_name="sap erp",
    )
    session.add(ko)
    session.commit()

    match = RelationService().match_entity(session, workspace.id, "sistema", "sap erp")
    assert match.match_kind == "exact"
    assert match.knowledge_object.id == ko.id


def test_matching_fuzzy_typo(session, workspace):
    ko = KnowledgeObject(
        workspace_id=workspace.id, type="sistema",
        canonical_name="Planilla de cierre", normalized_name="planilla de cierre",
    )
    session.add(ko)
    session.commit()

    # typo menor → fuzzy match
    match = RelationService().match_entity(session, workspace.id, "sistema", "planilla de cierres")
    assert match.match_kind == "fuzzy"
    assert match.knowledge_object.id == ko.id


def test_matching_no_cruza_tipos_ni_workspaces(session, workspace):
    otro_ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="Otro", workspace_type="organization")
    session.add(otro_ws)
    session.add(KnowledgeObject(
        workspace_id=otro_ws.id, type="sistema",
        canonical_name="POS", normalized_name="pos",
    ))
    session.add(KnowledgeObject(
        workspace_id=workspace.id, type="rol",
        canonical_name="POS", normalized_name="pos",
    ))
    session.commit()

    match = RelationService().match_entity(session, workspace.id, "sistema", "pos")
    assert match.knowledge_object is None


# ── Generación de candidatas ──────────────────────────────────────────────────

def test_pipeline_crea_candidatas_y_knowledge_objects(session, workspace, folder):
    doc = _make_document(session, workspace, folder)
    version = _make_approved_version(session, doc)

    service = RelationService()
    created = service.generate_candidates(
        session, document=doc, version=version,
        extraction=_extraction(("usa", "sistema", "POS", 0.94), ("requiere", "rol", "Supervisor", 0.88)),
    )
    session.commit()

    assert len(created) == 2
    assert all(r.status == "candidate" for r in created)
    assert all(r.created_by_ai for r in created)
    assert all(r.source_document_version_id == version.id for r in created)
    kos = session.query(KnowledgeObject).filter_by(workspace_id=workspace.id).all()
    assert {(k.type, k.normalized_name) for k in kos} == {("sistema", "pos"), ("rol", "supervisor")}


def test_pipeline_reusa_knowledge_object_existente(session, workspace, folder):
    ko = KnowledgeObject(
        workspace_id=workspace.id, type="sistema",
        canonical_name="POS", normalized_name="pos",
    )
    session.add(ko)
    session.commit()
    doc = _make_document(session, workspace, folder)
    version = _make_approved_version(session, doc)

    created = RelationService().generate_candidates(
        session, document=doc, version=version,
        extraction=_extraction(("usa", "sistema", "POS", 0.9)),
    )
    session.commit()

    assert len(created) == 1
    assert created[0].target_id == ko.id
    assert session.query(KnowledgeObject).count() == 1


def test_pipeline_no_duplica_ni_repropone_rechazadas(session, workspace, folder):
    doc = _make_document(session, workspace, folder)
    version = _make_approved_version(session, doc)
    service = RelationService()

    created = service.generate_candidates(
        session, document=doc, version=version,
        extraction=_extraction(("usa", "sistema", "POS", 0.9), ("requiere", "rol", "Supervisor", 0.8)),
    )
    session.commit()
    assert len(created) == 2

    # Rechazar una
    user = User(id=_uid(), email=f"a-{_uid()[:6]}@x.com", name="Aprobador")
    session.add(user)
    session.commit()
    service.reject(session, created[0], user.id, enforce_segregation=False)
    session.commit()

    # Re-correr el pipeline: no duplica la candidata viva ni re-propone la rechazada
    again = service.generate_candidates(
        session, document=doc, version=version,
        extraction=_extraction(("usa", "sistema", "POS", 0.9), ("requiere", "rol", "Supervisor", 0.8)),
    )
    session.commit()
    assert again == []
    statuses = [r.status for r in session.query(DocumentRelation).filter_by(document_id=doc.id).all()]
    assert sorted(statuses) == ["candidate", "rejected"]


def test_candidatas_de_version_anterior_quedan_obsoletas(session, workspace, folder):
    doc = _make_document(session, workspace, folder)
    v1 = _make_approved_version(session, doc)
    service = RelationService()
    service.generate_candidates(
        session, document=doc, version=v1,
        extraction=_extraction(("usa", "sistema", "POS", 0.9)),
    )
    session.commit()

    # Nueva versión aprobada: el pipeline corre de nuevo con otra extracción
    v1.version_status = "OBSOLETE"
    v1.is_current = False
    v2 = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=2, version_status="APPROVED",
        content_type="generated", content_json="{}", content_markdown="# v2", is_current=True,
    )
    session.add(v2)
    session.commit()

    service.generate_candidates(
        session, document=doc, version=v2,
        extraction=_extraction(("requiere", "rol", "Supervisor", 0.8)),
    )
    session.commit()

    relations = session.query(DocumentRelation).filter_by(document_id=doc.id).all()
    by_status = {r.status for r in relations}
    assert by_status == {"obsolete", "candidate"}
    vigente = [r for r in relations if r.status == "candidate"]
    assert len(vigente) == 1
    assert vigente[0].source_document_version_id == v2.id


# ── Edición (ADR-003) ─────────────────────────────────────────────────────────

def test_editar_relacion_cambia_tipo_y_deja_de_ser_ia(session, workspace, folder):
    doc = _make_document(session, workspace, folder)
    version = _make_approved_version(session, doc)
    service = RelationService()
    (rel,) = service.generate_candidates(
        session, document=doc, version=version,
        extraction=_extraction(("usa", "sistema", "POS", 0.9)),
    )
    session.commit()

    service.edit(session, rel, relation_type="depende_de")
    session.commit()
    assert rel.relation_type == "depende_de"
    assert rel.created_by_ai is False
    assert rel.status == "candidate"  # editar no confirma: sigue ADR-006

    with pytest.raises(ValueError):
        service.edit(session, rel, relation_type="tipo_inexistente")


# ── Duplicados y merge ────────────────────────────────────────────────────────

def test_find_possible_duplicate_sap_vs_sap_erp(session, workspace):
    sap = KnowledgeObject(
        workspace_id=workspace.id, type="sistema",
        canonical_name="SAP", normalized_name="sap",
    )
    sap_erp = KnowledgeObject(
        workspace_id=workspace.id, type="sistema",
        canonical_name="SAP ERP", normalized_name="sap erp",
    )
    session.add_all([sap, sap_erp])
    session.commit()

    dup = RelationService().find_possible_duplicate(session, sap)
    assert dup is not None and dup.id == sap_erp.id


def test_merge_reapunta_todas_las_relaciones(session, workspace, folder):
    doc1 = _make_document(session, workspace, folder, name="Doc 1")
    doc2 = _make_document(session, workspace, folder, name="Doc 2")
    v1 = _make_approved_version(session, doc1)
    v2 = _make_approved_version(session, doc2)

    sap = KnowledgeObject(workspace_id=workspace.id, type="sistema", canonical_name="SAP", normalized_name="sap")
    sap_erp = KnowledgeObject(workspace_id=workspace.id, type="sistema", canonical_name="SAP ERP", normalized_name="sap erp")
    session.add_all([sap, sap_erp])
    session.flush()

    r1 = DocumentRelation(
        workspace_id=workspace.id, document_id=doc1.id, source_type="document", source_id=doc1.id,
        relation_type="usa", target_type="sistema", target_id=sap.id,
        status="confirmed", source_document_version_id=v1.id,
    )
    r2 = DocumentRelation(
        workspace_id=workspace.id, document_id=doc2.id, source_type="document", source_id=doc2.id,
        relation_type="usa", target_type="sistema", target_id=sap.id,
        status="candidate", source_document_version_id=v2.id,
    )
    session.add_all([r1, r2])
    session.commit()

    RelationService().merge_knowledge_objects(session, source=sap, into=sap_erp)
    session.commit()

    # merge reapunta TODAS las document_relations (test de gobernanza del brief)
    remaining = session.query(DocumentRelation).all()
    assert all(r.target_id == sap_erp.id for r in remaining)
    assert session.query(KnowledgeObject).filter_by(id=sap.id).first() is None
    meta = json.loads(sap_erp.metadata_json)
    assert "SAP" in meta["aliases"]


def test_merge_descarta_relacion_redundante_conservando_confirmada(session, workspace, folder):
    doc = _make_document(session, workspace, folder)
    v = _make_approved_version(session, doc)
    sap = KnowledgeObject(workspace_id=workspace.id, type="sistema", canonical_name="SAP", normalized_name="sap")
    sap_erp = KnowledgeObject(workspace_id=workspace.id, type="sistema", canonical_name="SAP ERP", normalized_name="sap erp")
    session.add_all([sap, sap_erp])
    session.flush()
    # misma relación hacia ambos: candidate → sap, confirmed → sap erp
    session.add_all([
        DocumentRelation(
            workspace_id=workspace.id, document_id=doc.id, source_type="document", source_id=doc.id,
            relation_type="usa", target_type="sistema", target_id=sap.id,
            status="candidate", source_document_version_id=v.id,
        ),
        DocumentRelation(
            workspace_id=workspace.id, document_id=doc.id, source_type="document", source_id=doc.id,
            relation_type="usa", target_type="sistema", target_id=sap_erp.id,
            status="confirmed", source_document_version_id=v.id,
        ),
    ])
    session.commit()

    RelationService().merge_knowledge_objects(session, source=sap, into=sap_erp)
    session.commit()

    remaining = session.query(DocumentRelation).filter_by(document_id=doc.id).all()
    assert len(remaining) == 1
    assert remaining[0].status == "confirmed"
    assert remaining[0].target_id == sap_erp.id


def test_merge_valida_workspace_y_tipo(session, workspace):
    otro_ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="Otro", workspace_type="organization")
    session.add(otro_ws)
    a = KnowledgeObject(workspace_id=workspace.id, type="sistema", canonical_name="A", normalized_name="a")
    b = KnowledgeObject(workspace_id=otro_ws.id, type="sistema", canonical_name="B", normalized_name="b")
    c = KnowledgeObject(workspace_id=workspace.id, type="rol", canonical_name="C", normalized_name="c")
    session.add_all([a, b, c])
    session.commit()

    service = RelationService()
    with pytest.raises(ValueError):
        service.merge_knowledge_objects(session, source=a, into=b)  # workspace distinto
    with pytest.raises(ValueError):
        service.merge_knowledge_objects(session, source=a, into=c)  # tipo distinto
    with pytest.raises(ValueError):
        service.merge_knowledge_objects(session, source=a, into=a)  # consigo mismo


# ── Chunking ──────────────────────────────────────────────────────────────────

def test_chunking_respeta_secciones_y_tamano():
    md = "# Título\n\nIntro corta.\n\n## Paso 1\n\n" + ("parrafo largo " * 200) + "\n\n## Paso 2\n\nCierre."
    chunks = split_markdown_into_chunks(md)
    assert len(chunks) >= 3
    assert chunks[0].section_title == "Título"
    assert any(c.section_title == "Paso 1" for c in chunks)
    assert all(len(c.content) <= 1200 + 150 for c in chunks)
    # índices consecutivos (clave única por versión)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_chunking_vacio():
    assert split_markdown_into_chunks("") == []
    assert split_markdown_into_chunks("   \n  ") == []


# ── Pipeline end-to-end (sin LLM real) ────────────────────────────────────────

def test_run_semantic_pipeline_end_to_end(session, workspace, folder):
    doc = _make_document(session, workspace, folder)
    version = _make_approved_version(session, doc, markdown="# Cierre\n\nCargar la venta en el POS.")

    extraction_service = SemanticExtractionService(
        llm=FakeLLM({"relations": [
            {"relation_type": "usa", "entity_type": "sistema", "entity_name": "POS",
             "confidence": 0.94, "evidence": "Cargar la venta en el POS."}
        ]})
    )
    # ChunkIndexService sin provider de embeddings → indexa sin vectores
    from process_ai_core.semantic.chunking import ChunkIndexService

    chunk_service = ChunkIndexService()
    chunk_service._embedding_unavailable = True

    summary = run_semantic_pipeline(
        session,
        document=doc,
        version=version,
        extraction_service=extraction_service,
        chunk_service=chunk_service,
    )
    session.commit()

    assert summary["candidates_created"] == 1
    assert summary["chunks_indexed"] >= 1
    rel = session.query(DocumentRelation).filter_by(document_id=doc.id).one()
    assert rel.status == "candidate"
    assert rel.evidence_text == "Cargar la venta en el POS."
