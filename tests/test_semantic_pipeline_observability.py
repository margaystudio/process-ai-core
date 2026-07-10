"""Observabilidad del pipeline semántico (Tarea 2).

Verifica que un fallo del pipeline (a) queda registrado en semantic_pipeline_runs
con el stage donde falló y el error (diagnosticable) y (b) se re-lanza pero el
registro usa una sesión propia, de modo que el rastro persiste y la aprobación
(que ya está commiteada antes del hook best-effort) no se ve afectada.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from process_ai_core.db.database import Base
from process_ai_core.db.models import DocumentVersion, Folder, Process, Workspace
from process_ai_core.db.models_semantic import SemanticPipelineRun
from process_ai_core.semantic.pipeline import run_semantic_pipeline


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
def approved(session):
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    folder = Folder(id=_uid(), workspace_id=ws.id, name="root", path="root")
    doc = Process(
        id=_uid(), workspace_id=ws.id, folder_id=folder.id,
        document_type="procedimiento", name="Doc", status="approved",
    )
    version = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=1, version_status="APPROVED",
        content_type="manual_edit", content_json="{}",
        content_markdown="# Titulo\nContenido de prueba.", is_current=True,
    )
    session.add_all([ws, folder, doc, version])
    session.commit()
    return doc, version


class _BoomExtraction:
    def extract(self, **kwargs):
        raise RuntimeError("boom LLM")


class _StubExtraction:
    def extract(self, **kwargs):
        return {"entities": []}


class _StubRelations:
    def generate_candidates(self, session, **kwargs):
        return []


class _StubChunks:
    def index_version(self, session, version):
        return []


def test_fallo_queda_registrado_y_relanza(session, approved):
    doc, version = approved

    with pytest.raises(RuntimeError):
        run_semantic_pipeline(
            session, document=doc, version=version, extraction_service=_BoomExtraction()
        )

    run = session.query(SemanticPipelineRun).filter_by(document_id=doc.id).first()
    assert run is not None, "el fallo debe quedar registrado (rastro consultable)"
    assert run.status == "error"
    assert run.stage == "extraction"
    assert "boom" in (run.error or "").lower()
    assert run.finished_at is not None
    assert run.trigger == "approval"

    # La aprobación no se revierte: la versión sigue APPROVED.
    session.expire_all()
    v = session.query(DocumentVersion).filter_by(id=version.id).first()
    assert v.version_status == "APPROVED"


def test_corrida_ok_queda_registrada(session, approved):
    doc, version = approved

    summary = run_semantic_pipeline(
        session, document=doc, version=version,
        extraction_service=_StubExtraction(),
        relation_service=_StubRelations(),
        chunk_service=_StubChunks(),
        trigger="manual",
    )

    assert summary == {"candidates_created": 0, "chunks_indexed": 0}
    run = session.query(SemanticPipelineRun).filter_by(document_id=doc.id, status="ok").first()
    assert run is not None
    assert run.stage == "done"
    assert run.candidates_created == 0
    assert run.chunks_indexed == 0
    assert run.trigger == "manual"
