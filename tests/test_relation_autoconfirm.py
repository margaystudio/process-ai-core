"""Umbral de autoconfirmación de relaciones candidatas (Tarea 3).

Por defecto (umbral off) toda candidata va a revisión humana (ADR-006). Con un
umbral configurado, las candidatas con confidence >= umbral nacen 'confirmed'
por el sistema (created_by_ai=True, confirmed_by=NULL); el resto sigue candidate.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from process_ai_core.db.database import Base
from process_ai_core.db.models import Document, DocumentVersion, Folder, Workspace
from process_ai_core.db.models_semantic import DocumentRelation
from process_ai_core.semantic.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from process_ai_core.semantic.relations import RelationService


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


@pytest.fixture
def document(session):
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    folder = Folder(id=_uid(), workspace_id=ws.id, name="root", path="root")
    doc = Document(
        id=_uid(), workspace_id=ws.id, folder_id=folder.id,
        document_type="procedimiento", name="Doc", status="approved",
    )
    version = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=1, version_status="APPROVED",
        content_type="manual_edit", content_json="{}",
        content_markdown="# Doc", is_current=True,
    )
    session.add_all([ws, folder, doc, version])
    session.commit()
    return doc, version


def _extraction() -> ExtractionResult:
    """Dos relaciones: una de confianza alta (0.95) y otra baja (0.60)."""
    def rel(name: str, conf: float) -> ExtractedRelation:
        return ExtractedRelation(
            relation_type="usa",
            entity=ExtractedEntity(type="sistema", canonical_name=name),
            confidence=conf,
            evidence_text=f"usa {name}",
        )

    return ExtractionResult(
        entities=[], relations=[rel("SAP", 0.95), rel("Excel", 0.60)]
    )


def test_default_off_todo_a_revision(session, document):
    """Sin umbral, ambas quedan candidate (default de gobernanza intacto)."""
    doc, version = document
    svc = RelationService(autoconfirm_threshold=None)
    created = svc.generate_candidates(
        session, document=doc, version=version, extraction=_extraction(),
    )
    assert len(created) == 2
    assert all(r.status == "candidate" for r in created)
    assert all(r.confirmed_by is None for r in created)


def test_umbral_autoconfirma_solo_los_de_alta_confianza(session, document):
    """Con umbral 0.9, la de 0.95 se autoconfirma; la de 0.60 sigue candidate."""
    doc, version = document
    svc = RelationService(autoconfirm_threshold=0.9)
    created = svc.generate_candidates(
        session, document=doc, version=version, extraction=_extraction(),
    )
    by_status = {r.status for r in created}
    assert by_status == {"confirmed", "candidate"}

    auto = session.query(DocumentRelation).filter_by(status="confirmed").all()
    assert len(auto) == 1
    assert auto[0].confidence == 0.95
    # Rastro de autoconfirmación por el sistema.
    assert auto[0].created_by_ai is True
    assert auto[0].confirmed_by is None
    assert auto[0].confirmed_at is not None

    cand = session.query(DocumentRelation).filter_by(status="candidate").all()
    assert len(cand) == 1
    assert cand[0].confidence == 0.60
