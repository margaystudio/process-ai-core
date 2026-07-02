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


def upgrade() -> None:
    op.add_column(
        'validations',
        sa.Column('assigned_approver_ids', sa.Text(), nullable=False, server_default='[]'),
        schema='process_ai',
    )
    op.add_column(
        'validations',
        sa.Column('submit_comment', sa.Text(), nullable=False, server_default=''),
        schema='process_ai',
    )


def downgrade() -> None:
    op.drop_column('validations', 'submit_comment', schema='process_ai')
    op.drop_column('validations', 'assigned_approver_ids', schema='process_ai')
