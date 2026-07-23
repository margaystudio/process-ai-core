"""Tests adversariales del streaming de Tyto (Fase B).

El streaming es percepción de velocidad, no relajación de garantías. Cada test
ataca un mecanismo y debe fallar si se lo quita:

- Rechazo: sin documentos aprobados el stream NO emite tokens ni llama al LLM;
  el único evento es el result de rechazo.
- Guard en el evento final: una cita fabricada en el texto streameado jamás sale
  como 🟢; los niveles solo llegan en el evento `result` (nunca en los tokens).
- Aislamiento por workspace intacto por el camino del stream.
- Centinela de rechazo del modelo: no se muestran tokens de un rechazo a medio
  formar.

El LLM se mockea con streams controlados: determinístico, sin modelo real.
"""

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import process_ai_core.db.models  # noqa: F401 – registra modelos en Base.metadata
from process_ai_core.db.database import Base
from process_ai_core.db.models import DocumentType, DocumentVersion, Folder, Process, Workspace
from process_ai_core.db.models_semantic import TytoQueryLog
from process_ai_core.domains.document_types import BEHAVIOR_KEYS
from process_ai_core.semantic import TytoAnswerService, TytoQueryService
from process_ai_core.semantic.chunking import ChunkIndexService
from process_ai_core.semantic.tyto_answer import (
    REFUSAL_SENTINEL,
    TIER_APROBADO,
    TIER_INFERIDO,
    TIER_REFERENCIA,
    TytoAnswerError,
    parse_cited_text,
)

QUESTION = "cierre caja POS"


# ── Infraestructura (mismo patrón que test_tyto_answer) ──────────────────────

@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
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


def _make_doc(session, workspace, folder, *, name, markdown, document_type="procedimiento"):
    doc = Process(
        id=_uid(), workspace_id=workspace.id, folder_id=folder.id,
        document_type=document_type, name=name, status="approved",
    )
    session.add(doc)
    session.flush()
    version = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=1,
        version_status="APPROVED", content_type="generated",
        content_json="{}", content_markdown=markdown, is_current=True,
    )
    session.add(version)
    session.flush()
    doc.approved_version_id = version.id
    session.commit()
    indexer = ChunkIndexService()
    indexer._embedding_unavailable = True
    indexer.index_version(session, version)
    session.commit()
    return doc, version


class FakeStreamLLM:
    """LLM de streaming determinístico. Sin tokens, revienta si lo llaman."""

    def __init__(self, tokens=None):
        self.tokens = tokens
        self.calls = []

    def stream_text(self, *, system, user, temperature=0.2):
        self.calls.append({"system": system, "user": user})
        if self.tokens is None:
            raise AssertionError("El LLM no debía ser llamado en este escenario")
        yield from self.tokens


def _service(llm, threshold=0.1) -> TytoAnswerService:
    retrieval = TytoQueryService()
    retrieval._embedding_unavailable = True
    return TytoAnswerService(
        retrieval=retrieval, llm_provider=llm, relevance_threshold=threshold
    )


def _collect(service, session, workspace, question=QUESTION, user_id="u1"):
    return list(
        service.answer_stream(
            session, workspace_id=workspace.id, question=question, user_id=user_id
        )
    )


# ── Rechazo: cero tokens, cero LLM ───────────────────────────────────────────

def test_rechazo_sin_documentos_no_emite_tokens_ni_llama_al_llm(session, workspace):
    llm = FakeStreamLLM(tokens=None)  # revienta si el camino de rechazo se quita
    events = _collect(_service(llm), session, workspace)

    assert [e["type"] for e in events] == ["result"]
    result = events[0]["answer"]
    assert result.answered is False and result.refusal_reason
    assert llm.calls == []
    # y el rechazo queda logueado igual que en Fase A
    log = session.query(TytoQueryLog).one()
    assert log.answered is False


def test_rechazo_bajo_umbral_no_emite_tokens(session, workspace, folder):
    _make_doc(
        session, workspace, folder, name="Limpieza",
        markdown="# Limpieza\n\nBarrer la caja de herramientas del taller.",
    )
    llm = FakeStreamLLM(tokens=None)
    events = _collect(_service(llm, threshold=0.9), session, workspace)
    assert [e["type"] for e in events] == ["result"]
    assert events[0]["answer"].answered is False


# ── Tokens: solo texto; niveles únicamente en el evento final ────────────────

def test_stream_tokens_solo_texto_y_guard_en_el_result(session, workspace, folder):
    _make_doc(
        session, workspace, folder, name="Cierre de caja",
        markdown="# Cierre de caja\n\nContar el efectivo y registrar el cierre de caja en el POS.",
    )
    llm = FakeStreamLLM(tokens=[
        "Contá el efectivo ", "[S1]. ", "Dato inventado con cita falsa ", "[S99].",
    ])
    events = _collect(_service(llm), session, workspace)

    types = [e["type"] for e in events]
    assert types[:-1] == ["token"] * (len(types) - 1) and types[-1] == "result"
    # Los eventos token traen SOLO texto (jamás tier ni fuentes)
    for e in events[:-1]:
        assert set(e.keys()) == {"type", "text"}
    streamed = "".join(e["text"] for e in events[:-1])
    assert streamed == "Contá el efectivo [S1]. Dato inventado con cita falsa [S99]."

    result = events[-1]["answer"]
    assert result.answered is True
    seg_ok, seg_fabricado = result.segments
    assert seg_ok.tier == TIER_APROBADO and seg_ok.source_ids == ["S1"]
    # el MISMO guard de la Fase A corre sobre la salida completa:
    assert seg_fabricado.tier == TIER_INFERIDO and seg_fabricado.source_ids == []
    assert result.answer == streamed  # la prosa con marcadores es lo que se streameó


def test_niveles_por_stream_con_fuente_referencia(session, workspace, folder):
    behaviors = {k: False for k in BEHAVIOR_KEYS}
    behaviors.update({"tyto": True, "es_referencia": True})
    session.add(DocumentType(
        workspace_id=workspace.id, key="manual_externo", label="Manual externo",
        behaviors_json=json.dumps(behaviors),
    ))
    session.commit()
    _make_doc(
        session, workspace, folder, name="Manual del fabricante",
        markdown="# Manual\n\nLa caja registradora POS admite el cierre diario.",
        document_type="manual_externo",
    )
    llm = FakeStreamLLM(tokens=["El POS admite cierre diario [S1]."])
    events = _collect(_service(llm), session, workspace)
    result = events[-1]["answer"]
    assert result.segments[0].tier == TIER_REFERENCIA
    assert result.sources[0].tier == TIER_REFERENCIA


# ── Centinela: un rechazo del modelo no se muestra a medio formar ────────────

def test_rechazo_del_modelo_no_streamea_tokens(session, workspace, folder):
    _make_doc(
        session, workspace, folder, name="Cierre de caja",
        markdown="# Cierre de caja\n\nContar el efectivo y registrar el cierre de caja en el POS.",
    )
    llm = FakeStreamLLM(tokens=["NO_PUEDO_", "RESPONDER:", " las fuentes no lo cubren"])
    events = _collect(_service(llm), session, workspace)

    assert [e["type"] for e in events] == ["result"]  # cero tokens visibles
    result = events[0]["answer"]
    assert result.answered is False
    assert result.refusal_reason == "las fuentes no lo cubren"


def test_prosa_normal_retenida_se_libera(session, workspace, folder):
    """El holdback del centinela no se traga una respuesta corta legítima."""
    _make_doc(
        session, workspace, folder, name="Cierre de caja",
        markdown="# Cierre de caja\n\nContar el efectivo y registrar el cierre de caja en el POS.",
    )
    llm = FakeStreamLLM(tokens=["NO", " hace falta supervisor ", "[S1]."])
    events = _collect(_service(llm), session, workspace)
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed == "NO hace falta supervisor [S1]."
    assert events[-1]["answer"].answered is True


# ── Aislamiento por workspace (camino del stream) ────────────────────────────

def test_stream_jamas_incluye_chunks_de_otro_workspace(session, workspace, folder):
    doc_propio, _ = _make_doc(
        session, workspace, folder, name="Cierre propio",
        markdown="# Cierre\n\nEl cierre de caja se registra en el POS propio.",
    )
    otro_ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="Otro", workspace_type="organization")
    session.add(otro_ws)
    otra_carpeta = Folder(id=_uid(), workspace_id=otro_ws.id, name="Ops", path="Ops")
    session.add(otra_carpeta)
    session.commit()
    secreto = "SECRETO-OTRO-TENANT-99999"
    _make_doc(
        session, otro_ws, otra_carpeta, name="Cierre ajeno",
        markdown=f"# Cierre\n\nCierre de caja POS: {secreto}.",
    )

    llm = FakeStreamLLM(tokens=["Se registra en el POS [S1]."])
    events = _collect(_service(llm), session, workspace)
    result = events[-1]["answer"]

    assert {s.document_id for s in result.sources} == {doc_propio.id}
    assert secreto not in llm.calls[0]["user"]


# ── Salida inutilizable → error explícito ────────────────────────────────────

def test_stream_vacio_es_error_explicito(session, workspace, folder):
    _make_doc(
        session, workspace, folder, name="Cierre de caja",
        markdown="# Cierre de caja\n\nContar el efectivo y registrar el cierre de caja en el POS.",
    )
    llm = FakeStreamLLM(tokens=[])
    with pytest.raises(TytoAnswerError):
        _collect(_service(llm), session, workspace)


# ── Parser de marcadores ─────────────────────────────────────────────────────

def test_parse_cited_text():
    assert parse_cited_text("Contá el efectivo [S1]. Luego cerrá [S1] [S2]. Sin cita.") == [
        ("Contá el efectivo", ["S1"]),
        ("Luego cerrá", ["S1", "S2"]),
        ("Sin cita.", []),
    ]
    assert parse_cited_text("Todo sin marcadores") == [("Todo sin marcadores", [])]
    assert parse_cited_text("[S1] arranca citando") == [("arranca citando", [])]
    # la puntuación suelta tras la última cita no genera un segmento 🔴 espurio
    assert parse_cited_text("Una sola afirmación [S1].") == [("Una sola afirmación", ["S1"])]


# ── Endpoint SSE ─────────────────────────────────────────────────────────────

def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def client(session, workspace, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from api.dependencies import get_current_user_id, get_db
    from api.routes import tyto as tyto_route
    from api.workspace_client import get_workspace_context, sync_workspace_access

    fake_llm = FakeStreamLLM(tokens=["Registrá el cierre ", "en el POS [S1]."])
    monkeypatch.setattr(tyto_route, "_build_service", lambda: _service(fake_llm))
    monkeypatch.setattr(tyto_route, "resolve_tenant_workspace_id", lambda ctx: workspace.id)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    app.dependency_overrides[get_workspace_context] = lambda: object()
    app.dependency_overrides[sync_workspace_access] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_endpoint_stream_contrato(client, session, workspace, folder):
    doc, _ = _make_doc(
        session, workspace, folder, name="Cierre",
        markdown="# Cierre\n\nRegistrar el cierre de caja en el POS.",
    )
    resp = client.post("/api/v1/tyto/query/stream", json={"question": QUESTION})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    types = [name for name, _ in events]
    assert types[:-1] == ["token"] * (len(types) - 1) and types[-1] == "result"
    # tokens: solo texto
    for name, data in events[:-1]:
        assert set(data.keys()) == {"text"}
    # result: contrato §3 idéntico a la Fase A
    result = events[-1][1]
    assert result["answered"] is True
    assert result["segments"][0]["source_ids"] == ["S1"]
    assert result["segments"][0]["tier"] == TIER_APROBADO
    assert result["sources"][0]["document_id"] == doc.id
    # y la consulta quedó logueada
    assert session.query(TytoQueryLog).filter_by(answered=True).count() == 1


def test_endpoint_stream_rechazo_un_solo_evento(client):
    resp = client.post("/api/v1/tyto/query/stream", json={"question": "astronomía marciana"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert [name for name, _ in events] == ["result"]
    result = events[0][1]
    assert result["answered"] is False and result["refusal_reason"]
    assert result["segments"] == [] and result["sources"] == []


def test_endpoint_stream_error_explicito(client, session, workspace, folder, monkeypatch):
    from api.routes import tyto as tyto_route

    _make_doc(
        session, workspace, folder, name="Cierre",
        markdown="# Cierre\n\nRegistrar el cierre de caja en el POS.",
    )

    class BrokenLLM(FakeStreamLLM):
        def stream_text(self, *, system, user, temperature=0.2):
            from process_ai_core.ai.openai_provider import AIProviderError

            yield "Registrá "
            raise AIProviderError("stream cortado")

    monkeypatch.setattr(tyto_route, "_build_service", lambda: _service(BrokenLLM(tokens=[])))
    resp = client.post("/api/v1/tyto/query/stream", json={"question": QUESTION})
    events = _parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert "confiable" in events[-1][1]["detail"]


def test_endpoint_stream_requiere_autenticacion():
    from fastapi.testclient import TestClient

    from api.main import app

    assert not app.dependency_overrides
    resp = TestClient(app).post("/api/v1/tyto/query/stream", json={"question": "hola"})
    assert resp.status_code == 401
