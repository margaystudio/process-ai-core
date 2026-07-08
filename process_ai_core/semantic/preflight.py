"""Preflight de infraestructura de la capa semántica.

Verifica las condiciones para operar en modo NO-degradado:
  - extensión pgvector (``vector``) instalada
  - extensión ``pg_trgm`` instalada
  - la columna ``document_chunks.embedding`` es realmente de tipo ``vector``
    (no ``TEXT``: si la 0005 corrió sin pgvector, quedó TEXT y NO hay vector search)
  - ``OPENAI_API_KEY`` presente

Política según ``settings.semantic_allow_degraded``:
  - False (estricto, default en prod): un faltante es error accionable al arrancar.
  - True (default en dev/test): arranca igual, logueando warnings explícitos.

En backends no-PostgreSQL (SQLite de tests/dev) el preflight reporta "degradado"
sin consultar catálogos que no existen.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings

logger = logging.getLogger(__name__)


class SemanticInfraError(RuntimeError):
    """El preflight estricto de la capa semántica falló."""


def _schema() -> str:
    return os.getenv("DATABASE_SCHEMA", "process_ai")


@dataclass
class SemanticInfraStatus:
    """Resultado del preflight. `ok` = infra completa para modo no-degradado."""

    backend: str
    pgvector: bool
    pg_trgm: bool
    embedding_is_vector: bool
    openai_api_key: bool
    allow_degraded: bool

    @property
    def issues(self) -> list[str]:
        out: list[str] = []
        if not self.pgvector:
            out.append("extensión pgvector ('vector') no instalada")
        if not self.pg_trgm:
            out.append("extensión 'pg_trgm' no instalada (matching fuzzy degradado)")
        if not self.embedding_is_vector:
            out.append(
                "columna document_chunks.embedding no es de tipo 'vector' "
                "(quedó TEXT → sin vector search / índice ANN)"
            )
        if not self.openai_api_key:
            out.append("OPENAI_API_KEY no configurada (sin extracción ni embeddings)")
        return out

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def healthy(self) -> bool:
        """Sano si está completo, o si el modo degradado está explícitamente permitido."""
        return self.ok or self.allow_degraded

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "backend": self.backend,
            "allow_degraded": self.allow_degraded,
            "pgvector": self.pgvector,
            "pg_trgm": self.pg_trgm,
            "embedding_is_vector": self.embedding_is_vector,
            "openai_api_key": self.openai_api_key,
            "issues": self.issues,
        }


def check_semantic_infra(session: Session) -> SemanticInfraStatus:
    """Consulta el estado real de la infra (no aplica política; solo reporta)."""
    settings = get_settings()
    has_key = bool(settings.openai_api_key)

    dialect = session.get_bind().dialect.name
    if dialect != "postgresql":
        # SQLite u otro: no hay pgvector/pg_trgm ni catálogos de PG.
        return SemanticInfraStatus(
            backend=dialect,
            pgvector=False,
            pg_trgm=False,
            embedding_is_vector=False,
            openai_api_key=has_key,
            allow_degraded=settings.semantic_allow_degraded,
        )

    def _has_ext(name: str) -> bool:
        return (
            session.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = :n"), {"n": name}
            ).first()
            is not None
        )

    pgvector = _has_ext("vector")
    pg_trgm = _has_ext("pg_trgm")

    row = session.execute(
        text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = 'document_chunks' "
            "AND column_name = 'embedding'"
        ),
        {"s": _schema()},
    ).first()
    embedding_is_vector = bool(row and row[0] == "vector")

    return SemanticInfraStatus(
        backend="postgresql",
        pgvector=pgvector,
        pg_trgm=pg_trgm,
        embedding_is_vector=embedding_is_vector,
        openai_api_key=has_key,
        allow_degraded=settings.semantic_allow_degraded,
    )


def enforce_semantic_infra(session: Session) -> SemanticInfraStatus:
    """Corre el preflight y aplica la política (estricto → raise; degradado → warn)."""
    status = check_semantic_infra(session)

    if status.ok:
        logger.info(
            "Preflight capa semántica OK (pgvector + pg_trgm + embedding vector + OPENAI_API_KEY)."
        )
        return status

    if status.allow_degraded:
        for issue in status.issues:
            logger.warning("Capa semántica DEGRADADA: %s", issue)
        logger.warning(
            "SEMANTIC_ALLOW_DEGRADED=true → se arranca en modo degradado (funcionalidad reducida)."
        )
        return status

    raise SemanticInfraError(
        "Preflight de la capa semántica FALLÓ (SEMANTIC_ALLOW_DEGRADED=false):\n  - "
        + "\n  - ".join(status.issues)
        + "\n\nAcciones para resolver:\n"
        "  1) Habilitar extensiones:  CREATE EXTENSION IF NOT EXISTS vector;  "
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;\n"
        "  2) Con pgvector ya instalado, correr `alembic upgrade head` para que "
        "document_chunks.embedding quede en tipo 'vector'.\n"
        "  3) Setear OPENAI_API_KEY.\n"
        "  (o poné SEMANTIC_ALLOW_DEGRADED=true para arrancar en modo degradado)."
    )
