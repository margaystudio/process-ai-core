"""source_file_columns

Revision ID: 7c6a45873aa0
Revises: 0001_baseline
Create Date: 2026-06-30 09:56:35.875261
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# identificadores usados por Alembic.
revision = '0002_source_file'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None

# Mismo schema que usa la app (default process_ai); permite correr el smoke de
# migraciones contra un schema descartable. El autogenerate de Alembic dejaba
# 'process_ai' escrito a mano — acá, en la 0003 y en la 0004. Con eso el smoke se
# caía en la 0002 sin llegar nunca a ejercitar el resto de la cadena.
try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:
    SCHEMA = 'process_ai'
if not SCHEMA:
    SCHEMA = 'process_ai'


def upgrade() -> None:
    op.add_column('document_versions', sa.Column('source_file_key', sa.Text(), nullable=True), schema=SCHEMA)
    op.add_column('document_versions', sa.Column('source_file_name', sa.String(length=500), nullable=True), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column('document_versions', 'source_file_name', schema=SCHEMA)
    op.drop_column('document_versions', 'source_file_key', schema=SCHEMA)
