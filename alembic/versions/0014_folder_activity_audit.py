"""folder_activity_audit

Amplia audit_logs para conservar el contexto de carpeta y registrar acciones
de configuracion/permisos que no pertenecen a un documento.

Revision ID: 0014_folder_activity_audit
Revises: 0013_perf_indexes
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_folder_activity_audit"
down_revision = "0013_perf_indexes"
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
        "audit_logs",
        sa.Column("folder_id", sa.String(length=36), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_audit_logs_folder_id",
        "audit_logs",
        "folders",
        ["folder_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_audit_logs_folder_created",
        "audit_logs",
        ["folder_id", sa.text("created_at DESC")],
        unique=False,
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f'UPDATE "{SCHEMA}".audit_logs AS audit '
            "SET folder_id = document.folder_id "
            f'FROM "{SCHEMA}".documents AS document '
            "WHERE audit.document_id = document.id AND audit.folder_id IS NULL"
        )
    )
    op.alter_column(
        "audit_logs",
        "document_id",
        existing_type=sa.String(length=36),
        nullable=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.execute(
        sa.text(f'DELETE FROM "{SCHEMA}".audit_logs WHERE document_id IS NULL')
    )
    op.alter_column(
        "audit_logs",
        "document_id",
        existing_type=sa.String(length=36),
        nullable=False,
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_audit_logs_folder_created",
        table_name="audit_logs",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_audit_logs_folder_id",
        "audit_logs",
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_column("audit_logs", "folder_id", schema=SCHEMA)
