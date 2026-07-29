"""validation_approvers

Aprobadores sugeridos + comentario del autor al enviar a revisión.
Semántica: sugerencia + notificación (NO restringe quién puede aprobar).

Revision ID: 0003_validation_approvers
Revises: 0002_source_file
Create Date: 2026-07-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# identificadores usados por Alembic.
revision = '0003_validation_approvers'
down_revision = '0002_source_file'
branch_labels = None
depends_on = None

# Mismo schema que usa la app (default process_ai); permite correr el smoke de
# migraciones contra un schema descartable. El autogenerate de Alembic dejaba
# 'process_ai' escrito a mano.
try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:
    SCHEMA = 'process_ai'
if not SCHEMA:
    SCHEMA = 'process_ai'


def upgrade() -> None:
    op.add_column(
        'validations',
        sa.Column('assigned_approver_ids', sa.Text(), nullable=False, server_default='[]'),
        schema=SCHEMA,
    )
    op.add_column(
        'validations',
        sa.Column('submit_comment', sa.Text(), nullable=False, server_default=''),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column('validations', 'submit_comment', schema=SCHEMA)
    op.drop_column('validations', 'assigned_approver_ids', schema=SCHEMA)
