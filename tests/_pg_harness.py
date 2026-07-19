"""Harness compartido para verificación en PostgreSQL real (tests + benchmark).

La capa semántica corre el hot path en SQL solo en PostgreSQL con pgvector/pg_trgm.
Los tests unitarios usan SQLite (fallback Python); este harness levanta el schema
real contra un PostgreSQL EFÍMERO/LOCAL (docker) para ejercitar el camino SQL nuevo.

Uso: exportar BENCH_DATABASE_URL apuntando a ese Postgres. NUNCA el sandbox
compartido — hay una guarda explícita que rechaza hosts supabase/pooler.

No depende de la cadena de Alembic (que en esta rama queda incompleta hasta que
mergee feat/config-carpetas): construye el schema con Base.metadata.create_all y
luego replica lo que hacen las migraciones 0005 + 0011 (columnas vector + índices).
"""

from __future__ import annotations

import os
import random

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import process_ai_core.db.models  # noqa: F401 – registra modelos en Base.metadata
import process_ai_core.db.models_semantic  # noqa: F401
from process_ai_core.db.database import Base
from process_ai_core.db.models import DocumentVersion, Folder, Process, Workspace
from process_ai_core.db.models_semantic import (
    DocumentChunk,
    DocumentRelation,
    KnowledgeObject,
)
from process_ai_core.semantic import _pg, normalize_name
from process_ai_core.semantic.chunking import embedding_to_literal

DIM = 1536
SCHEMA = _pg.schema()


def bench_url() -> str | None:
    return os.getenv("BENCH_DATABASE_URL") or os.getenv("SEMANTIC_PG_URL")


def _assert_not_sandbox(url: str) -> None:
    lowered = url.lower()
    if "supabase" in lowered or "pooler" in lowered:
        raise RuntimeError(
            "BENCH_DATABASE_URL apunta a Supabase/pooler. El harness solo corre "
            "contra un Postgres efímero/local; nunca el sandbox compartido."
        )


def make_engine(url: str | None = None) -> Engine:
    url = url or bench_url()
    if not url:
        raise RuntimeError("Falta BENCH_DATABASE_URL (Postgres efímero con pgvector).")
    _assert_not_sandbox(url)
    return create_engine(url, future=True)


def make_session(engine: Engine) -> Session:
    return sessionmaker(bind=engine, future=True)()


def setup_schema(engine: Engine) -> None:
    """Schema fresco + extensiones + columnas vector + índices (0005 + 0011)."""
    with engine.begin() as conn:
        # Drop CASCADE del schema entero: evita el ordenamiento de FKs circulares
        # (documents ↔ document_versions ↔ runs ↔ validations). Las extensiones
        # viven en otro schema, no se ven afectadas.
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))
        for ext in ("vector", "pg_trgm"):
            conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))

    # create_all ya crea las columnas embedding como vector(1536) en Postgres
    # (VectorLiteral); acá solo faltan los índices que crean 0005 + 0011.
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
                f'ON "{SCHEMA}".document_chunks USING hnsw (embedding vector_cosine_ops)'
            )
        )
        # 0005: índice sobre la columna varchar cruda (redundante; el planner no lo usa).
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_knowledge_objects_name_trgm "
                f'ON "{SCHEMA}".knowledge_objects USING gin (normalized_name gin_trgm_ops)'
            )
        )
        # 0011: índice sobre la EXPRESIÓN (normalized_name::text) — el que sí se usa.
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_knowledge_objects_name_trgm_txt "
                f'ON "{SCHEMA}".knowledge_objects USING gin ((normalized_name::text) gin_trgm_ops)'
            )
        )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_knowledge_objects_name_embedding_hnsw "
                f'ON "{SCHEMA}".knowledge_objects USING hnsw (name_embedding vector_cosine_ops)'
            )
        )
    # La sonda de capacidad se cachea por engine: invalidar por si cambió la infra.
    _pg.reset_caps_cache()


# ── Generación de datos ───────────────────────────────────────────────────────

def rand_vec(rng: random.Random) -> list[float]:
    return [rng.gauss(0.0, 1.0) for _ in range(DIM)]


def _uid(rng: random.Random) -> str:
    return "%032x" % rng.getrandbits(128)


def new_workspace(session: Session, rng: random.Random, name: str = "WS") -> Workspace:
    ws = Workspace(
        id=_uid(rng), slug=f"ws-{_uid(rng)[:8]}", name=name,
        workspace_type="organization",
    )
    session.add(ws)
    folder = Folder(id=_uid(rng), workspace_id=ws.id, name="Ops", path="Ops")
    session.add(folder)
    session.commit()
    ws._folder_id = folder.id  # type: ignore[attr-defined]
    return ws


def add_doc_version(
    session: Session,
    rng: random.Random,
    ws: Workspace,
    *,
    name="Doc",
    doc_status="approved",
    version_status="APPROVED",
    is_current=True,
    markdown="# Doc\n\nContenido.",
) -> tuple[Process, DocumentVersion]:
    doc = Process(
        id=_uid(rng), workspace_id=ws.id, folder_id=ws._folder_id,  # type: ignore[attr-defined]
        document_type="procedimiento", name=name, status=doc_status,
    )
    session.add(doc)
    session.flush()
    version = DocumentVersion(
        id=_uid(rng), document_id=doc.id, version_number=1,
        version_status=version_status, content_type="generated",
        content_json="{}", content_markdown=markdown, is_current=is_current,
    )
    session.add(version)
    session.flush()
    if version_status == "APPROVED" and is_current:
        doc.approved_version_id = version.id
    session.commit()
    return doc, version


def add_chunk(
    session: Session,
    rng: random.Random,
    version: DocumentVersion,
    *,
    idx: int,
    content: str,
    embedding: list[float] | None,
) -> DocumentChunk:
    chunk = DocumentChunk(
        id=_uid(rng), document_version_id=version.id, chunk_index=idx,
        content=content,
        embedding=embedding_to_literal(embedding) if embedding is not None else None,
    )
    session.add(chunk)
    return chunk


def add_ko(
    session: Session,
    rng: random.Random,
    ws: Workspace,
    *,
    name: str,
    type: str = "sistema",
    embedding: list[float] | None = None,
    model: str | None = None,
) -> KnowledgeObject:
    ko = KnowledgeObject(
        id=_uid(rng), workspace_id=ws.id, type=type,
        canonical_name=name, normalized_name=normalize_name(name),
        name_embedding=embedding_to_literal(embedding) if embedding is not None else None,
        name_embedding_model=model,
    )
    session.add(ko)
    return ko


def bulk_add_kos(
    session: Session,
    rng: random.Random,
    ws: Workspace,
    names,
    *,
    type: str = "sistema",
    batch: int = 10000,
) -> None:
    """Inserta muchos knowledge_objects rápido (insert mappings, sin ORM por fila)."""
    from sqlalchemy import insert

    rows = [
        {
            "id": _uid(rng), "workspace_id": ws.id, "type": type,
            "canonical_name": n, "normalized_name": normalize_name(n),
            "metadata_json": "{}",
        }
        for n in names
    ]
    for j in range(0, len(rows), batch):
        session.execute(insert(KnowledgeObject), rows[j : j + batch])
    session.commit()


def add_relation(
    session: Session,
    rng: random.Random,
    ws: Workspace,
    doc: Process,
    version: DocumentVersion,
    target,
    *,
    status="confirmed",
    relation_type="usa",
    target_type=None,
) -> DocumentRelation:
    rel = DocumentRelation(
        id=_uid(rng), workspace_id=ws.id, document_id=doc.id,
        source_type="document", source_id=doc.id, relation_type=relation_type,
        target_type=target_type or target.type, target_id=target.id,
        status=status, source_document_version_id=version.id, confidence=0.9,
    )
    session.add(rel)
    return rel
