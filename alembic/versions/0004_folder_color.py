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
        'folders',
        sa.Column('color', sa.String(length=20), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column('folders', 'color', schema=SCHEMA)
