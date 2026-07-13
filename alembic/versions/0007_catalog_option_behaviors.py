"""catalog_option_behaviors

Comportamientos configurables para opciones de catalogo.

Revision ID: 0007_catalog_option_behaviors
Revises: 0006_semantic_pipeline_runs
Create Date: 2026-07-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_catalog_option_behaviors"
down_revision = "0006_semantic_pipeline_runs"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def upgrade() -> None:
    op.add_column(
        "catalog_option",
        sa.Column("behaviors_json", sa.Text(), nullable=False, server_default="{}"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("catalog_option", "behaviors_json", schema=SCHEMA)
