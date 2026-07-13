"""document_type (entidad por-tenant)

Promueve `document_type` de `catalog_option` (global) a su propia tabla, por-tenant
(workspace_id NOT NULL). Crea la tabla y **backfillea** cada workspace existente con el
set de defaults (mismo template que usa la provisión de tenants nuevos).

Ver docs/PLAN_DOCUMENT_TYPES.md.

Nota: encadena tras la 0007 (behaviors en catalog_option, de la rama de Nacho, ya
aplicada al sandbox). Ese `behaviors_json` de catalog_option queda vestigial: document_type
se mueve a su propia tabla. Se puede dropear en la fase de retiro del catálogo.

Revision ID: 0008_document_types
Revises: 0007_catalog_option_behaviors
Create Date: 2026-07-13
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


revision = "0008_document_types"
down_revision = "0007_catalog_option_behaviors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_type",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey(f"{SCHEMA}.workspaces.id"), nullable=False),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("behaviors_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="custom"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "key", name="uq_document_type_workspace_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_document_type_workspace", "document_type", ["workspace_id"], schema=SCHEMA
    )

    # ── Backfill: cada workspace existente arranca con el set de defaults ──────
    from process_ai_core.domains.document_types import build_default_rows

    bind = op.get_bind()
    workspace_ids = [row[0] for row in bind.execute(
        sa.text(f'SELECT id FROM "{SCHEMA}".workspaces')
    )]

    if workspace_ids:
        now = datetime.utcnow()
        table = sa.table(
            "document_type",
            sa.column("id", sa.String),
            sa.column("workspace_id", sa.String),
            sa.column("key", sa.String),
            sa.column("label", sa.String),
            sa.column("prompt_text", sa.Text),
            sa.column("behaviors_json", sa.Text),
            sa.column("is_active", sa.Boolean),
            sa.column("sort_order", sa.Integer),
            sa.column("origin", sa.String),
            sa.column("icon", sa.String),
            sa.column("color", sa.String),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
            schema=SCHEMA,
        )
        rows: list[dict] = []
        for ws_id in workspace_ids:
            rows.extend(build_default_rows(ws_id, now=now))
        op.bulk_insert(table, rows)


def downgrade() -> None:
    op.drop_index("ix_document_type_workspace", table_name="document_type", schema=SCHEMA)
    op.drop_table("document_type", schema=SCHEMA)
