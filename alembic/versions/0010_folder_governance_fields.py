"""folder_governance_fields

Agrega campos de gobierno documental por carpeta:
- icon
- default_document_type
- tyto_enabled
- allow_document_override

Revision ID: 0010_folder_governance_fields
Revises: 0009_drop_catalog_document_type
Create Date: 2026-07-14
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


revision = "0010_folder_governance_fields"
down_revision = "0009_drop_catalog_document_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("folders", sa.Column("icon", sa.String(50), nullable=True), schema=SCHEMA)
    op.add_column(
        "folders",
        sa.Column("default_document_type", sa.String(50), nullable=True),
        schema=SCHEMA,
    )
    op.add_column("folders", sa.Column("tyto_enabled", sa.Boolean(), nullable=True), schema=SCHEMA)
    op.add_column(
        "folders",
        sa.Column(
            "allow_document_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("folders", "allow_document_override", schema=SCHEMA)
    op.drop_column("folders", "tyto_enabled", schema=SCHEMA)
    op.drop_column("folders", "default_document_type", schema=SCHEMA)
    op.drop_column("folders", "icon", schema=SCHEMA)
