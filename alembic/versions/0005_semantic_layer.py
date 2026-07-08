"""semantic_layer

Capa semántica (brief "Capa de relaciones y conocimiento"):
- knowledge_objects   (entidades semánticas: sistema, rol, área, formulario, ...)
- document_relations  (relaciones candidate/confirmed/rejected/obsolete)
- document_chunks     (chunks + embeddings pgvector para RAG de Tyto)
- evidence            (evidencias asociadas a un documento)

Extensiones: pgvector (embedding vector(1536)) y pg_trgm (matching fuzzy).
Si las extensiones no están disponibles (sin privilegios), la migración degrada:
- embedding queda como TEXT (mismo literal pgvector, sin índice ANN)
- no se crea el índice trigram

Revision ID: 0005_semantic_layer
Revises: 0004_folder_color
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = '0005_semantic_layer'
down_revision = '0004_folder_color'
branch_labels = None
depends_on = None

# Mismo schema que usa la app (default process_ai); permite correr el smoke
# de migraciones contra un schema descartable.
try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:
    SCHEMA = 'process_ai'
if not SCHEMA:
    SCHEMA = 'process_ai'


def _ensure_extension(conn, name: str) -> bool:
    """Intenta habilitar una extensión; devuelve True si queda disponible."""
    installed = conn.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = :n"), {"n": name}
    ).first()
    if installed:
        return True
    # Supabase recomienda instalarlas en el schema `extensions`; si no existe
    # ese schema (Postgres vanilla) se instala en el schema por defecto.
    for ddl in (
        f'CREATE EXTENSION IF NOT EXISTS "{name}" WITH SCHEMA extensions',
        f'CREATE EXTENSION IF NOT EXISTS "{name}"',
    ):
        try:
            conn.execute(text(ddl))
            return True
        except Exception:
            pass
    return False


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

    has_vector = _ensure_extension(conn, "vector")
    has_trgm = _ensure_extension(conn, "pg_trgm")

    if has_vector:
        vec_schema = _extension_schema(conn, "vector")
        embedding_type = f'"{vec_schema}".vector(1536)' if vec_schema else 'vector(1536)'
    else:
        embedding_type = 'text'

    # ── knowledge_objects ────────────────────────────────────────────────────
    op.create_table(
        'knowledge_objects',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.workspaces.id'), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('canonical_name', sa.String(length=300), nullable=False),
        sa.Column('normalized_name', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('workspace_id', 'type', 'normalized_name', name='uq_knowledge_object_identity'),
        schema=SCHEMA,
    )
    op.create_index('ix_knowledge_objects_workspace_id', 'knowledge_objects', ['workspace_id'], schema=SCHEMA)
    op.create_index('ix_knowledge_objects_normalized_name', 'knowledge_objects', ['normalized_name'], schema=SCHEMA)

    if has_trgm:
        # Índice trigram para el paso "fuzzy" de la cascada de matching.
        trgm_schema = _extension_schema(conn, "pg_trgm")
        opclass = f'"{trgm_schema}".gin_trgm_ops' if trgm_schema else 'gin_trgm_ops'
        try:
            conn.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS ix_knowledge_objects_name_trgm '
                    f'ON "{SCHEMA}".knowledge_objects USING gin (normalized_name {opclass})'
                )
            )
        except Exception:
            pass

    # ── document_relations ───────────────────────────────────────────────────
    op.create_table(
        'document_relations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.workspaces.id'), nullable=False),
        sa.Column('document_id', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.documents.id'), nullable=False),
        sa.Column('source_type', sa.String(length=30), nullable=False),
        sa.Column('source_id', sa.String(length=36), nullable=False),
        sa.Column('relation_type', sa.String(length=30), nullable=False),
        sa.Column('target_type', sa.String(length=30), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence_text', sa.Text(), nullable=True),
        sa.Column('source_document_version_id', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.document_versions.id'), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='candidate'),
        sa.Column('created_by_ai', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('confirmed_by', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.users.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        schema=SCHEMA,
    )
    op.create_index('ix_document_relations_workspace_id', 'document_relations', ['workspace_id'], schema=SCHEMA)
    op.create_index('ix_document_relations_document_id', 'document_relations', ['document_id'], schema=SCHEMA)
    op.create_index('ix_document_relations_status', 'document_relations', ['status'], schema=SCHEMA)
    op.create_index('ix_document_relations_doc_status', 'document_relations', ['document_id', 'status'], schema=SCHEMA)
    op.create_index('ix_document_relations_target', 'document_relations', ['target_type', 'target_id'], schema=SCHEMA)
    op.create_index('ix_document_relations_source', 'document_relations', ['source_type', 'source_id'], schema=SCHEMA)
    op.create_index('ix_document_relations_source_version', 'document_relations', ['source_document_version_id'], schema=SCHEMA)

    # ── document_chunks (embedding vector/TEXT según disponibilidad) ─────────
    conn.execute(
        text(
            f'''
            CREATE TABLE "{SCHEMA}".document_chunks (
                id                   varchar(36) PRIMARY KEY,
                document_version_id  varchar(36) NOT NULL
                    REFERENCES "{SCHEMA}".document_versions(id) ON DELETE CASCADE,
                chunk_index          integer NOT NULL,
                content              text NOT NULL,
                page_number          integer,
                section_title        varchar(500),
                embedding            {embedding_type},
                metadata_json        text NOT NULL DEFAULT '{{}}',
                CONSTRAINT uq_document_chunk_index UNIQUE (document_version_id, chunk_index)
            )
            '''
        )
    )
    op.create_index('ix_document_chunks_document_version_id', 'document_chunks', ['document_version_id'], schema=SCHEMA)

    if has_vector:
        # Índice ANN (HNSW, coseno) para retrieval de Tyto.
        try:
            conn.execute(
                text(
                    f'CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw '
                    f'ON "{SCHEMA}".document_chunks USING hnsw (embedding vector_cosine_ops)'
                )
            )
        except Exception:
            # pgvector < 0.5 no soporta hnsw; el retrieval funciona igual (seq scan).
            pass

    # ── evidence ─────────────────────────────────────────────────────────────
    op.create_table(
        'evidence',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.workspaces.id'), nullable=False),
        sa.Column('document_id', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.documents.id'), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('storage_url', sa.Text(), nullable=True),
        sa.Column('hash', sa.String(length=128), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('added_by', sa.String(length=36), sa.ForeignKey(f'{SCHEMA}.users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        schema=SCHEMA,
    )
    op.create_index('ix_evidence_workspace_id', 'evidence', ['workspace_id'], schema=SCHEMA)
    op.create_index('ix_evidence_document_id', 'evidence', ['document_id'], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table('evidence', schema=SCHEMA)
    op.drop_table('document_chunks', schema=SCHEMA)
    op.drop_table('document_relations', schema=SCHEMA)
    op.drop_table('knowledge_objects', schema=SCHEMA)
