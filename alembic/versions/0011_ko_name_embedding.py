"""ko_name_embedding

Persistencia del embedding del nombre de knowledge_objects (hardening de
performance del paso 3 de la cascada de matching):
- knowledge_objects.name_embedding        (vector(1536) pgvector; TEXT si degradado)
- knowledge_objects.name_embedding_model  (versionado del embedding, ADR-008)
- índice ANN HNSW sobre name_embedding (coseno)

Se elige HNSW (no IVFFlat): no requiere entrenamiento, se construye sobre tabla
vacía, mejor recall/latencia, y es consistente con ix_document_chunks_embedding_hnsw
(0005). Si pgvector no está o es <0.5, la columna queda TEXT y no se crea el índice
(degradación grácil, igual que 0005).

NOTA: los índices ix_document_chunks_embedding_hnsw y ix_knowledge_objects_name_trgm
YA los crea la migración 0005; esta migración NO los recrea.

Encadenada sobre 0010_folder_governance_fields (rama feat/config-carpetas), NO sobre
0009: 0010 ya cuelga de 0009 y dos hermanas 0010 bifurcarían la cadena. Implica que
feat/config-carpetas debe mergear a develop antes que esta rama.

Revision ID: 0011_ko_name_embedding
Revises: 0010_folder_governance_fields
Create Date: 2026-07-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "0011_ko_name_embedding"
down_revision = "0010_folder_governance_fields"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def _has_extension(conn, name: str) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = :n"), {"n": name}
        ).first()
        is not None
    )


def _extension_schema(conn, name: str) -> str | None:
    row = conn.execute(
        text(
            "SELECT n.nspname FROM pg_extension e "
            "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = :n"
        ),
        {"n": name},
    ).first()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    has_vector = _has_extension(conn, "vector")
    if has_vector:
        vec_schema = _extension_schema(conn, "vector")
        embedding_type = f'"{vec_schema}".vector(1536)' if vec_schema else "vector(1536)"
    else:
        # Degradado: sin pgvector la columna queda TEXT (mismo literal, sin índice ANN).
        embedding_type = "text"

    # name_embedding (vector/TEXT según disponibilidad)
    conn.execute(
        text(
            f'ALTER TABLE "{SCHEMA}".knowledge_objects '
            f"ADD COLUMN IF NOT EXISTS name_embedding {embedding_type}"
        )
    )
    # name_embedding_model (versionado del embedding)
    op.add_column(
        "knowledge_objects",
        sa.Column("name_embedding_model", sa.String(length=100), nullable=True),
        schema=SCHEMA,
    )

    if has_vector:
        try:
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_knowledge_objects_name_embedding_hnsw "
                    f'ON "{SCHEMA}".knowledge_objects USING hnsw (name_embedding vector_cosine_ops)'
                )
            )
        except Exception:
            # pgvector < 0.5 no soporta hnsw; el matching funciona igual (seq scan).
            pass


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            f'DROP INDEX IF EXISTS "{SCHEMA}".ix_knowledge_objects_name_embedding_hnsw'
        )
    )
    op.drop_column("knowledge_objects", "name_embedding_model", schema=SCHEMA)
    conn.execute(
        text(
            f'ALTER TABLE "{SCHEMA}".knowledge_objects DROP COLUMN IF EXISTS name_embedding'
        )
    )
