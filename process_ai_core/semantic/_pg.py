"""Helpers dialect-aware para la capa semántica (hot path SQL en PostgreSQL).

La capa semántica corre en SQLite (tests) y PostgreSQL (dev/prod). El camino
rápido (pgvector / pg_trgm) solo aplica en PostgreSQL con la infra presente; en
cualquier otro caso el llamador cae al camino Python portable.

Este módulo centraliza:
- detección de dialecto (`is_postgres`),
- sonda de capacidad cacheada por engine (`vector_search_ready` / `trgm_ready`),
- resolución del schema del tipo `vector` para construir el cast defensivo
  (Supabase instala pgvector en el schema `extensions`, no en el default).

La sonda se cachea por engine (la infra no cambia en la vida del proceso); si una
consulta SQL fallara igual, el llamador degrada a Python.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

try:  # el schema de la app (None en SQLite de tests)
    from ..db.database import DATABASE_SCHEMA as _DB_SCHEMA
except Exception:  # pragma: no cover - defensivo
    _DB_SCHEMA = "process_ai"


def schema() -> str:
    """Schema Postgres de la app (default 'process_ai')."""
    return _DB_SCHEMA or "process_ai"


def is_postgres(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


@dataclass(frozen=True)
class _Caps:
    pgvector: bool
    pg_trgm: bool
    embedding_is_vector: bool
    vector_type: str  # cast a usar, p.ej. '"extensions".vector' o 'vector'


# Cache por engine: la infra no cambia durante la vida del proceso.
_CAPS: dict[int, _Caps] = {}


def _probe(session: Session) -> _Caps:
    conn = session.connection()

    def _has_ext(name: str) -> bool:
        return (
            conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = :n"), {"n": name}
            ).first()
            is not None
        )

    pgvector = _has_ext("vector")
    pg_trgm = _has_ext("pg_trgm")

    # La columna embedding es realmente 'vector' (y no TEXT por 0005 degradada).
    row = conn.execute(
        text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = 'document_chunks' "
            "AND column_name = 'embedding'"
        ),
        {"s": schema()},
    ).first()
    embedding_is_vector = bool(row and row[0] == "vector")

    # Schema del tipo 'vector' para el cast (defensivo: puede vivir en extensions).
    vec_type = "vector"
    if pgvector:
        srow = conn.execute(
            text(
                "SELECT n.nspname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typname = 'vector' LIMIT 1"
            )
        ).first()
        if srow and srow[0] and srow[0] not in ("public", "pg_catalog"):
            vec_type = f'"{srow[0]}".vector'

    return _Caps(pgvector, pg_trgm, embedding_is_vector, vec_type)


def _caps(session: Session) -> _Caps:
    engine: Engine = session.get_bind()
    key = id(engine)
    cached = _CAPS.get(key)
    if cached is None:
        cached = _probe(session)
        _CAPS[key] = cached
    return cached


def vector_search_ready(session: Session) -> bool:
    """True si se puede rankear por pgvector (extensión + columna vector)."""
    if not is_postgres(session):
        return False
    caps = _caps(session)
    return caps.pgvector and caps.embedding_is_vector


def trgm_ready(session: Session) -> bool:
    """True si se puede hacer el shortlist fuzzy server-side con pg_trgm."""
    if not is_postgres(session):
        return False
    return _caps(session).pg_trgm


def vector_type(session: Session) -> str:
    """Nombre del tipo vector para el cast SQL (p.ej. '\"extensions\".vector')."""
    return _caps(session).vector_type


def reset_caps_cache() -> None:
    """Invalida la sonda cacheada (tests que cambian de engine/infra)."""
    _CAPS.clear()
