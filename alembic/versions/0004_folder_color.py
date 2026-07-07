"""folder_color

Color de acento por carpeta para la UI de Biblioteca.

Revision ID: 0004_folder_color
Revises: 0003_validation_approvers
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0004_folder_color'
down_revision = '0003_validation_approvers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'folders',
        sa.Column('color', sa.String(length=20), nullable=True),
        schema='process_ai',
    )


def downgrade() -> None:
    op.drop_column('folders', 'color', schema='process_ai')
