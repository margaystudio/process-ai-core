"""Benchmark antes/después del hardening SQL de la capa semántica.

Corre SOLO contra un PostgreSQL efímero/local con pgvector (BENCH_DATABASE_URL);
nunca el sandbox (guarda en tests/_pg_harness). Siembra un dataset realista y mide,
viejo (Python) vs nuevo (SQL), para:
  1) retrieval de Tyto (latencia + equivalencia + EXPLAIN del ranking vectorial),
  2) matching fuzzy (latencia + equivalencia + EXPLAIN del shortlist pg_trgm).

Uso:
  BENCH_DATABASE_URL=postgresql+psycopg://postgres:pass@localhost:5432/bench \\
      python scripts/bench_semantic.py

Variables opcionales: BENCH_N_DOCS, BENCH_N_CHUNKS, BENCH_N_KOS, BENCH_TOP_K, BENCH_SEED.
"""

from __future__ import annotations

import os
import random
import statistics
import sys
import time
from pathlib import Path

# Permitir importar el harness compartido (tests/_pg_harness.py).
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

from sqlalchemy import text  # noqa: E402

import _pg_harness as H  # noqa: E402
from process_ai_core.db.models import Document, DocumentVersion  # noqa: E402
from process_ai_core.db.models_semantic import DocumentChunk  # noqa: E402
from process_ai_core.semantic import _pg  # noqa: E402
from process_ai_core.semantic.chunking import (  # noqa: E402
    embedding_to_literal,
    literal_to_embedding,
)
from process_ai_core.semantic.relations import (  # noqa: E402
    FUZZY_TRGM_FLOOR,
    RelationService,
    _similarity,
)
from process_ai_core.semantic.tyto import TytoQueryService, _cosine  # noqa: E402

N_DOCS = int(os.getenv("BENCH_N_DOCS", "200"))
N_CHUNKS = int(os.getenv("BENCH_N_CHUNKS", "10000"))
N_KOS = int(os.getenv("BENCH_N_KOS", "100000"))
TOP_K = int(os.getenv("BENCH_TOP_K", "6"))
SEED = int(os.getenv("BENCH_SEED", "1234"))

WORDS = [
    "montevideo", "salta", "cordoba", "rosario", "gas", "oil", "premium", "planilla",
    "cierre", "caja", "stock", "deposito", "norte", "sur", "turno", "supervisor",
    "factura", "remito", "auditoria", "balanza", "surtidor", "tanque", "boleta",
    "kiosco", "shop", "aditivo", "gasoil", "nafta", "ancap", "ute", "antel",
]


class _FakeEmbed:
    def __init__(self, vec):
        self._vec = vec

    def embed(self, texts):
        return [list(self._vec) for _ in texts]


def _plan_line(s: str, width: int = 160) -> str:
    return s if len(s) <= width else s[:width] + " …"


def _timeit(fn, repeat=5):
    times = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000.0)
    return statistics.median(times), min(times), max(times)


# ── Retrieval de Tyto: implementación VIEJA (para comparar) ───────────────────

def _old_tyto_retrieve(session, workspace_id, query_vec, top_k):
    """Réplica del retrieval original: carga TODOS los chunks, coseno en Python,
    top_k después de rankear todo, y N+1 (una query de Document por versión)."""
    svc = TytoQueryService()
    versions = svc.approved_current_versions(session, workspace_id)
    version_by_id = {v.id: v for v in versions}
    chunks = (
        session.query(DocumentChunk)
        .filter(DocumentChunk.document_version_id.in_(list(version_by_id)))
        .all()
    )
    scored = [
        (c, _cosine(query_vec, literal_to_embedding(c.embedding)) if c.embedding else 0.0)
        for c in chunks
    ]
    scored.sort(key=lambda p: p[1], reverse=True)
    scored = [p for p in scored if p[1] > 0][:top_k]
    out = []
    for chunk, score in scored:
        v = version_by_id.get(chunk.document_version_id)
        if not v:
            continue
        doc = session.query(Document).filter_by(id=v.document_id).first()  # N+1
        if doc:
            out.append((doc.id, chunk.id, round(score, 4)))
    return out


def bench_tyto(session, ws, query_vec):
    print("\n" + "=" * 72)
    print(f"TYTO RETRIEVAL — {N_CHUNKS} chunks aprobados vigentes, top_k={TOP_K}")
    print("=" * 72)

    new_svc = TytoQueryService(embedding_provider=_FakeEmbed(query_vec))

    def run_new():
        new_svc.retrieve(session, workspace_id=ws.id, query="q", top_k=TOP_K)

    def run_old():
        _old_tyto_retrieve(session, ws.id, query_vec, TOP_K)

    old_med, old_min, _ = _timeit(run_old)
    new_med, new_min, _ = _timeit(run_new)
    print(f"  VIEJO (Python, carga todo + N+1): {old_med:8.2f} ms (min {old_min:.2f})")
    print(f"  NUEVO (SQL pgvector, 1 query):    {new_med:8.2f} ms (min {new_min:.2f})")
    print(f"  speedup:                          {old_med / new_med:8.1f}x")

    # Equivalencia: viejo (Python exacto) vs nuevo-EXACTO (índice off → coseno exacto).
    old_res = _old_tyto_retrieve(session, ws.id, query_vec, TOP_K)
    old_ids = [r[1] for r in old_res]
    sch, vtype = _pg.schema(), _pg.vector_type(session)
    qlit = embedding_to_literal(query_vec)
    session.execute(text("SET LOCAL enable_indexscan = off"))
    session.execute(text("SET LOCAL enable_bitmapscan = off"))
    exact = session.execute(
        text(
            f"""
            SELECT c.id AS chunk_id
            FROM "{sch}".document_chunks c
            JOIN "{sch}".document_versions v ON v.id = c.document_version_id
            JOIN "{sch}".documents d ON d.id = v.document_id
            WHERE d.workspace_id = :ws AND v.version_status = 'APPROVED'
              AND v.is_current = true AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:q AS {vtype}) LIMIT :k
            """
        ),
        {"ws": ws.id, "q": qlit, "k": TOP_K},
    ).all()
    session.rollback()  # limpia los SET LOCAL
    exact_ids = [r.chunk_id for r in exact]
    print(f"  equivalencia (viejo vs SQL-exacto): "
          f"{'IDENTICO ✔' if old_ids == exact_ids else 'DIFIERE ✗'} (top-{TOP_K})")

    # Recall del índice HNSW (aprox) vs exacto — transparencia.
    # OJO: con vectores UNIFORMEMENTE ALEATORIOS (este seed) no hay estructura de
    # vecindad, el peor caso para cualquier ANN → recall bajo esperable. Con
    # embeddings reales (que se agrupan) el recall@k del HNSW es alto. La corrección
    # de la query queda probada por la equivalencia exacta de arriba (IDÉNTICO).
    new_res = _old_or_new_ids(new_svc, session, ws, query_vec)
    inter = len(set(new_res) & set(exact_ids))
    print(f"  recall@{TOP_K} HNSW vs exacto:      {inter}/{len(exact_ids)} "
          f"(vectores aleatorios = peor caso ANN; ver nota)")

    _explain_tyto(session, ws, query_vec)


def _old_or_new_ids(new_svc, session, ws, query_vec):
    ctx = new_svc.retrieve(session, workspace_id=ws.id, query="q", top_k=TOP_K)
    return [c.chunk_id for c in ctx.citations]


def _explain_tyto(session, ws, query_vec):
    sch, vtype = _pg.schema(), _pg.vector_type(session)
    qlit = embedding_to_literal(query_vec)
    print("\n  EXPLAIN (ANALYZE) del ranking vectorial (nuevo):")
    rows = session.execute(
        text(
            f"""
            EXPLAIN (ANALYZE)
            SELECT c.id
            FROM "{sch}".document_chunks c
            JOIN "{sch}".document_versions v ON v.id = c.document_version_id
            JOIN "{sch}".documents d ON d.id = v.document_id
            WHERE d.workspace_id = :ws AND v.version_status = 'APPROVED'
              AND v.is_current = true AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:q AS {vtype}) LIMIT :k
            """
        ),
        {"ws": ws.id, "q": qlit, "k": TOP_K},
    ).all()
    for r in rows:
        print("   ", _plan_line(r[0]))
    session.rollback()


# ── Matching fuzzy ────────────────────────────────────────────────────────────

def bench_matching(session, ws, probe):
    print("\n" + "=" * 72)
    print(f"MATCHING FUZZY — {N_KOS} knowledge_objects, probe='{probe}'")
    print("=" * 72)
    svc = RelationService()

    def run_old():
        cands = (
            session.query(H.KnowledgeObject)
            .filter_by(workspace_id=ws.id, type="sistema")
            .all()
        )
        best, best_s = None, 0.0
        for ko in cands:
            s = _similarity(probe, ko.normalized_name)
            if s > best_s:
                best, best_s = ko, s
        return best

    def run_new():
        cands = svc._fuzzy_candidates(session, ws.id, "sistema", probe)
        best, best_s = None, 0.0
        for ko in cands:
            s = _similarity(probe, ko.normalized_name)
            if s > best_s:
                best, best_s = ko, s
        return best

    old_med, old_min, _ = _timeit(run_old, repeat=3)
    new_med, new_min, _ = _timeit(run_new, repeat=3)
    print(f"  VIEJO (carga todos + SequenceMatcher): {old_med:8.2f} ms (min {old_min:.2f})")
    print(f"  NUEVO (shortlist pg_trgm + SeqMatcher): {new_med:8.2f} ms (min {new_min:.2f})")
    print(f"  speedup:                               {old_med / new_med:8.1f}x")

    old_best = run_old()
    new_best = run_new()
    same = (old_best and new_best and old_best.id == new_best.id)
    print(f"  equivalencia (mismo match):            {'IDÉNTICO ✔' if same else 'DIFIERE ✗'}")

    print(f"\n  EXPLAIN (ANALYZE) del shortlist (nuevo, floor={FUZZY_TRGM_FLOOR}):")
    old_limit = session.execute(text("SELECT show_limit()")).scalar()
    session.execute(text("SELECT set_limit(CAST(:f AS real))"), {"f": FUZZY_TRGM_FLOOR})
    rows = session.execute(
        text(
            f"""
            EXPLAIN (ANALYZE)
            SELECT id FROM "{_pg.schema()}".knowledge_objects
            WHERE workspace_id = :ws AND type = 'sistema'
              AND normalized_name % :n
            ORDER BY similarity(normalized_name, :n) DESC LIMIT 50
            """
        ),
        {"ws": ws.id, "n": probe},
    ).all()
    session.execute(text("SELECT set_limit(CAST(:f AS real))"), {"f": old_limit})
    for r in rows:
        print("   ", _plan_line(r[0]))


# ── Seeding ───────────────────────────────────────────────────────────────────

def seed(session, rng):
    print(f"Sembrando: {N_DOCS} docs / {N_CHUNKS} chunks / {N_KOS} KOs ...")
    t = time.perf_counter()
    ws = H.new_workspace(session, rng, "BENCH")

    # Chunks distribuidos en N_DOCS versiones aprobadas vigentes.
    per_doc = max(1, N_CHUNKS // N_DOCS)
    made = 0
    for d in range(N_DOCS):
        _, ver = H.add_doc_version(session, rng, ws, name=f"Doc {d}")
        for _ in range(per_doc):
            if made >= N_CHUNKS:
                break
            H.add_chunk(session, rng, ver, idx=made % per_doc,
                        content="contenido", embedding=H.rand_vec(rng))
            made += 1
        if d % 50 == 0:
            session.commit()
    session.commit()

    # KOs con nombres diversos (bulk) + un objetivo cercano al probe.
    names = [" ".join(rng.sample(WORDS, k=3)) + f" {i:06d}" for i in range(N_KOS)]
    target = "estacion central ancap ruta interbalnearia"
    names.append(target.title())
    H.bulk_add_kos(session, rng, ws, names)
    # ANALYZE en su propia transacción COMMITEADA: si quedara en una txn que luego
    # se rollbackea (p.ej. al limpiar SET LOCAL), las stats se revertirían y el
    # planner elegiría el índice equivocado. En prod, autovacuum mantiene stats.
    session.commit()
    session.execute(text(f'ANALYZE "{_pg.schema()}".knowledge_objects'))
    session.execute(text(f'ANALYZE "{_pg.schema()}".document_chunks'))
    session.commit()
    print(f"  sembrado en {time.perf_counter() - t:.1f}s")
    # probe = typo del objetivo (matchea pocos, dispara el índice).
    return ws, "estacion central ancap ruta interbalnaria"


def main():
    url = H.bench_url()
    if not url:
        print("ERROR: exportá BENCH_DATABASE_URL (Postgres efímero con pgvector).")
        sys.exit(2)
    print(f"Benchmark contra: {url.split('@')[-1]}")
    engine = H.make_engine()
    H.setup_schema(engine)
    session = H.make_session(engine)
    rng = random.Random(SEED)

    ws, probe = seed(session, rng)
    query_vec = H.rand_vec(rng)  # vector de query aleatorio para Tyto

    bench_tyto(session, ws, query_vec)
    bench_matching(session, ws, probe)
    print("\nOK.")


if __name__ == "__main__":
    main()
