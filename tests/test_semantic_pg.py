"""Gobernanza y aceleración del CAMINO SQL nuevo, contra PostgreSQL real.

Los tests de tests/test_tyto_governance.py corren en SQLite → ejercitan el fallback
Python. Este módulo ejercita el camino SQL (pgvector/pg_trgm), donde los filtros de
gobernanza viven en el WHERE. Se salta si no hay BENCH_DATABASE_URL (Postgres
efímero con pgvector); NUNCA corre contra el sandbox (guarda en _pg_harness).

Incluye la prueba de mutación exigida en la revisión: si se cae un filtro del WHERE
el resultado se contamina (el test lo demuestra afirmativamente).
"""

from __future__ import annotations

import random

import pytest
from sqlalchemy import text

from process_ai_core.semantic import _pg
from process_ai_core.semantic.relations import RelationService
from process_ai_core.semantic.tyto import TytoQueryService

import _pg_harness as H

pytestmark = pytest.mark.skipif(
    H.bench_url() is None,
    reason="requiere BENCH_DATABASE_URL (Postgres efímero con pgvector)",
)


class _FakeEmbed:
    """Provider determinístico: no toca la red."""

    def __init__(self, vec: list[float]):
        self._vec = vec

    def embed(self, texts):
        return [list(self._vec) for _ in texts]


@pytest.fixture(scope="module")
def engine():
    eng = H.make_engine()
    return eng


@pytest.fixture
def session(engine):
    H.setup_schema(engine)  # schema fresco por test (aislamiento total)
    s = H.make_session(engine)
    yield s
    s.close()


def _tyto(query_vec) -> TytoQueryService:
    return TytoQueryService(embedding_provider=_FakeEmbed(query_vec))


# ── Sanidad: el camino SQL está realmente activo ──────────────────────────────

def test_infra_lista_camino_sql_activo(session):
    assert _pg.vector_search_ready(session) is True
    assert _pg.trgm_ready(session) is True


# ── Gobernanza contra el WHERE del retrieval SQL ──────────────────────────────

def test_aislamiento_por_workspace_sql(session):
    rng = random.Random(1)
    qvec = H.rand_vec(rng)

    ws_a = H.new_workspace(session, rng, "A")
    doc_a, ver_a = H.add_doc_version(session, rng, ws_a, name="Doc A")
    H.add_chunk(session, rng, ver_a, idx=0, content="venta pos supervisor", embedding=qvec)

    ws_b = H.new_workspace(session, rng, "B")
    doc_b, ver_b = H.add_doc_version(session, rng, ws_b, name="Doc B")
    H.add_chunk(session, rng, ver_b, idx=0, content="venta pos supervisor", embedding=qvec)
    session.commit()

    ctx = _tyto(qvec).retrieve(session, workspace_id=ws_a.id, query="venta pos supervisor")
    doc_ids = {c.document_id for c in ctx.citations}
    assert doc_ids == {doc_a.id}
    assert doc_b.id not in doc_ids


def test_solo_approved_vigente_sql(session):
    rng = random.Random(2)
    qvec = H.rand_vec(rng)
    ws = H.new_workspace(session, rng, "WS")

    doc_ok, ver_ok = H.add_doc_version(session, rng, ws, name="Aprobado")
    H.add_chunk(session, rng, ver_ok, idx=0, content="pos supervisor", embedding=qvec)

    # Borrador (no aprobado, no vigente) con un chunk plantado con el MISMO vector.
    doc_draft, ver_draft = H.add_doc_version(
        session, rng, ws, name="Borrador",
        doc_status="pending_validation", version_status="IN_REVIEW", is_current=False,
    )
    H.add_chunk(session, rng, ver_draft, idx=0, content="pos supervisor", embedding=qvec)
    session.commit()

    ctx = _tyto(qvec).retrieve(session, workspace_id=ws.id, query="pos supervisor")
    doc_ids = {c.document_id for c in ctx.citations}
    assert doc_ids == {doc_ok.id}


def test_expande_solo_confirmadas_sql(session):
    rng = random.Random(3)
    qvec = H.rand_vec(rng)
    ws = H.new_workspace(session, rng, "WS")
    doc, ver = H.add_doc_version(session, rng, ws, name="Doc")
    H.add_chunk(session, rng, ver, idx=0, content="pos supervisor", embedding=qvec)

    pos = H.add_ko(session, rng, ws, name="POS")
    sap = H.add_ko(session, rng, ws, name="SAP ERP")
    H.add_relation(session, rng, ws, doc, ver, pos, status="confirmed")
    H.add_relation(session, rng, ws, doc, ver, sap, status="candidate", relation_type="depende_de")
    session.commit()

    ctx = _tyto(qvec).retrieve(session, workspace_id=ws.id, query="pos supervisor")
    names = {e["name"] for e in ctx.related_entities}
    assert names == {"POS"}  # la candidate no expande


# ── Prueba de MUTACIÓN: el filtro is_current es load-bearing ───────────────────

def test_mutacion_is_current_es_load_bearing(session):
    """Con el WHERE correcto, el chunk de la versión NO vigente no aparece.
    Sin el filtro is_current, SÍ se contamina → el filtro es lo que protege."""
    rng = random.Random(4)
    qvec = H.rand_vec(rng)
    ws = H.new_workspace(session, rng, "WS")

    doc_ok, ver_ok = H.add_doc_version(session, rng, ws, name="Aprobado")
    H.add_chunk(session, rng, ver_ok, idx=0, content="pos", embedding=H.rand_vec(rng))

    # Versión NO vigente (is_current=False) con un chunk = query (rankearía primero).
    doc_old, ver_old = H.add_doc_version(
        session, rng, ws, name="Vieja", version_status="APPROVED", is_current=False,
    )
    H.add_chunk(session, rng, ver_old, idx=0, content="pos", embedding=qvec)
    session.commit()

    # (1) Camino correcto: la versión no vigente queda afuera.
    ctx = _tyto(qvec).retrieve(session, workspace_id=ws.id, query="pos")
    assert doc_old.id not in {c.document_id for c in ctx.citations}

    # (2) Mutación: misma query SIN el filtro is_current → el chunk viejo se cuela.
    sch = _pg.schema()
    vtype = _pg.vector_type(session)
    qlit = __import__(
        "process_ai_core.semantic.chunking", fromlist=["embedding_to_literal"]
    ).embedding_to_literal(qvec)
    leaked = session.execute(
        text(
            f"""
            SELECT d.id AS document_id
            FROM "{sch}".document_chunks c
            JOIN "{sch}".document_versions v ON v.id = c.document_version_id
            JOIN "{sch}".documents d ON d.id = v.document_id
            WHERE d.workspace_id = :ws
              AND v.version_status = 'APPROVED'
              -- AND v.is_current = true   <-- filtro removido a propósito
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:qvec AS {vtype})
            LIMIT 5
            """
        ),
        {"ws": ws.id, "qvec": qlit},
    ).all()
    leaked_ids = {r.document_id for r in leaked}
    assert doc_old.id in leaked_ids, "sin is_current el chunk no vigente DEBE colarse"


# ── pg_trgm: el shortlist entra por el índice GIN ─────────────────────────────

def test_shortlist_usa_indice_trgm(session):
    """El shortlist de la Tarea 2 entra por el índice trgm de EXPRESIÓN (0011),
    no por Seq Scan. A escala realista el planner lo elige solo."""
    rng = random.Random(5)
    ws = H.new_workspace(session, rng, "WS")
    words = [
        "montevideo", "salta", "cordoba", "rosario", "gas", "oil", "premium",
        "planilla", "cierre", "caja", "stock", "deposito", "norte", "sur", "turno",
        "supervisor", "factura", "remito", "auditoria", "balanza", "surtidor",
        "tanque", "boleta", "kiosco", "shop", "aditivo", "gasoil", "nafta", "ancap",
    ]
    names = [" ".join(rng.sample(words, k=3)) + f" {i:06d}" for i in range(100_000)]
    names.append("Zutano Perengano Mengano")  # objetivo selectivo
    H.bulk_add_kos(session, rng, ws, names)
    session.execute(text(f'ANALYZE "{_pg.schema()}".knowledge_objects'))

    sch = _pg.schema()
    old = session.execute(text("SELECT show_limit()")).scalar()
    session.execute(text("SELECT set_limit(CAST(0.1 AS real))"))
    plan_rows = session.execute(
        text(
            f"""
            EXPLAIN (ANALYZE)
            SELECT id FROM "{sch}".knowledge_objects
            WHERE workspace_id = :ws AND type = 'sistema'
              AND normalized_name % :name
            ORDER BY similarity(normalized_name, :name) DESC
            LIMIT 50
            """
        ),
        {"ws": ws.id, "name": "zutano perengano mengano"},
    ).all()
    session.execute(text("SELECT set_limit(CAST(:f AS real))"), {"f": old})
    plan = "\n".join(r[0] for r in plan_rows)

    # El índice de expresión (0011) es el load-bearing; NO Seq Scan sobre la tabla.
    assert "ix_knowledge_objects_name_trgm_txt" in plan, plan
    assert "Seq Scan on knowledge_objects" not in plan, plan

    # Y el método real devuelve el objetivo en el shortlist.
    svc = RelationService()
    cands = svc._fuzzy_candidates(session, ws.id, "sistema", "zutano perengano mengano")
    assert any(c.normalized_name == "zutano perengano mengano" for c in cands)


# ── Embedding match: write-through persiste vector + modelo ────────────────────

def test_embedding_writethrough_persiste_vector_y_modelo(session, monkeypatch):
    rng = random.Random(6)
    ws = H.new_workspace(session, rng, "WS")
    vec = H.rand_vec(rng)
    ko = H.add_ko(session, rng, ws, name="SAP ERP")  # sin name_embedding
    session.commit()
    assert ko.name_embedding is None

    svc = RelationService(embedding_provider=_FakeEmbed(vec))
    monkeypatch.setattr(svc, "_active_embedding_model", lambda: "text-embedding-3-small")

    match = svc._embedding_match("sap erp", [ko])
    session.commit()
    assert match is not None and match.knowledge_object.id == ko.id
    assert ko.name_embedding is not None
    assert ko.name_embedding_model == "text-embedding-3-small"


# ── Floor del shortlist: fija el 0.3 (recall de casos que SÍ deben entrar) ─────

def test_floor_preserva_recall_de_duplicados(session):
    """El shortlist SQL con floor pg_trgm=0.3 debe seguir devolviendo los casos que
    la cascada necesita ver. SequenceMatcher solo evalúa lo que el SQL le pasa, así
    que si alguien sube el floor y deja de devolver estos pares, este test se pone
    en rojo (los tests de SQLite no cubren este umbral porque corren el path Python).

    Similitudes trigram medidas: sap/sap erp=0.50, supervisor de turno/turnos=0.86,
    sistema sap/sistema sap erp=0.73 — todas > 0.3.
    """
    rng = random.Random(7)
    ws = H.new_workspace(session, rng, "WS")
    for name in ["SAP ERP", "Supervisor de Turno", "Sistema SAP", "POS",
                 "Balanza Digital", "Planilla de Cierres"]:
        H.add_ko(session, rng, ws, name=name)
    session.commit()

    svc = RelationService()

    def shortlist_names(probe):
        return {
            c.normalized_name
            for c in svc._fuzzy_candidates(session, ws.id, "sistema", probe)
        }

    # Nombre corto: "sap" debe traer "sap erp" (y "sistema sap").
    got = shortlist_names("sap")
    assert "sap erp" in got, f"'sap' no trajo 'sap erp' (floor demasiado alto?): {got}"

    # Typo: "supervisor de turnos" debe traer "supervisor de turno".
    got = shortlist_names("supervisor de turnos")
    assert "supervisor de turno" in got, f"typo no matcheó: {got}"

    # Frase con subcadena: "sistema sap erp" debe traer "sistema sap".
    got = shortlist_names("sistema sap erp")
    assert "sistema sap" in got, f"subcadena no matcheó: {got}"
