"""version_validity — vigencia de la aprobación

Agrega `document_versions.validity_until` (DATE, nullable).

Por qué es un campo de la VERSIÓN y no una política del workspace
------------------------------------------------------------------
Una política del workspace es mutable: cambiarla reescribiría retroactivamente
la vigencia de documentos ya aprobados, y por eso no se podría imprimir. Fijada
en el momento de aprobar es un hecho consumado —igual que el aprobador y la
fecha— y entra legítimamente al acta de la portada del PDF.

Eso resuelve el problema del papel offline: una copia impresa sin red no tiene
forma de consultar si el documento sigue vigente, pero sí puede llevar impresa
la fecha hasta la que la aprobación se comprometió. Es lo que ISO 9001 espera
para revisión periódica.

Nullable a propósito, con dos significados distintos que NO conviene colapsar:
  - NULL en una versión APPROVED anterior a esta migración: no se registró.
  - NULL en una versión nueva: quien aprobó eligió no fijar vencimiento.
En los dos casos la portada omite la fila, en vez de inventar una fecha.

Sin backfill: poner una vigencia retroactiva a aprobaciones que no la
comprometieron sería fabricar un dato del acta.

Revision ID: 0015_version_validity
Revises: 0014_document_code
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "0015_version_validity"
down_revision = "0014_document_code"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            f"ALTER TABLE {SCHEMA}.document_versions "
            f"ADD COLUMN IF NOT EXISTS validity_until DATE"
        )
    )
    # Índice para la revisión periódica: "qué vence en los próximos 30 días".
    # Parcial sobre las vigentes, que es el único conjunto que interesa consultar.
    conn.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_document_versions_validity_until "
            f"ON {SCHEMA}.document_versions (validity_until) "
            f"WHERE validity_until IS NOT NULL AND is_current = true"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(f"DROP INDEX IF EXISTS {SCHEMA}.ix_document_versions_validity_until"))
    conn.execute(
        text(f"ALTER TABLE {SCHEMA}.document_versions DROP COLUMN IF EXISTS validity_until")
    )
