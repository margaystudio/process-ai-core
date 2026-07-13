"""limpieza: retirar document_type del catálogo

Ahora que document_type es una entidad por-tenant (tabla document_type, migración 0008),
se limpia lo vestigial en catalog_option:
- Borra las filas domain='document_type' (ya no las lee nadie; el front pega al API nuevo).
- Dropea la columna behaviors_json (la agregó la 0007; quedó sin uso).

Revision ID: 0009_drop_catalog_document_type
Revises: 0008_document_types
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


revision = "0009_drop_catalog_document_type"
down_revision = "0008_document_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Filas document_type del catálogo viejo (no hay FK; Document.document_type es string key).
    op.execute(
        sa.text(f"DELETE FROM \"{SCHEMA}\".catalog_option WHERE domain = 'document_type'")
    )
    # Columna vestigial de behaviors (de la 0007).
    op.drop_column("catalog_option", "behaviors_json", schema=SCHEMA)


def downgrade() -> None:
    # Restaura solo el esquema; las filas document_type borradas no se re-insertan
    # (cleanup de datos irreversible — están en la tabla document_type por-tenant).
    op.add_column(
        "catalog_option",
        sa.Column("behaviors_json", sa.Text(), nullable=False, server_default="{}"),
        schema=SCHEMA,
    )
