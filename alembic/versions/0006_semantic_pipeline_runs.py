"""semantic_pipeline_runs

Tabla de observabilidad del pipeline semántico (hardening — Tarea 2).
Registra una fila por corrida (por documento + versión) con status/stage/error/
timestamps, para diagnosticar fallos del pipeline best-effort sin voltear la aprobación.

Revision ID: 0006_semantic_pipeline_runs
Revises: 0005_semantic_layer
Create Date: 2026-07-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


revision = "0006_semantic_pipeline_runs"
down_revision = "0005_semantic_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "semantic_pipeline_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False, server_default="start"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("candidates_created", sa.Integer(), nullable=True),
        sa.Column("chunks_indexed", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="approval"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_pipeline_runs_doc_started",
        "semantic_pipeline_runs",
        ["document_id", "started_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_pipeline_runs_workspace",
        "semantic_pipeline_runs",
        ["workspace_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_semantic_pipeline_runs_version",
        "semantic_pipeline_runs",
        ["version_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("semantic_pipeline_runs", schema=SCHEMA)
