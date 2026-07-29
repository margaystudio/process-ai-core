"""acta_snapshot — congelar los datos del acta en la versión

Agrega a `document_versions` los campos del acta de aprobación como TEXTO:

    acta_elaborated_by_name / acta_elaborated_by_role
    acta_reviewed_by_name   / acta_reviewed_by_role
    acta_approved_by_name   / acta_approved_by_role
    acta_client_name

Por qué
-------
Hasta ahora estos valores se resolvían por lookup al construir el
`DocumentContext`. Mientras el PDF esté congelado da igual: el impreso es
correcto para siempre. Pero el RE-FREEZE —una versión APPROVED sin
`pdf_storage_key` se congela al servirla— toma los valores ACTUALES. Si quien
aprobó como "Encargado de turno" después ascendió a "Gerente", el PDF
regenerado le atribuiría a esa aprobación una autoridad que no tenía.

Y el riesgo creció: desde que el freeze aborta cuando falta una evidencia, un
documento aprobado hoy puede terminar congelándose semanas después.

TEXTO y no FK
-------------
Una FK sigue los renombres. Si el rol "Encargado de turno" pasa a llamarse
"Supervisor de playa", el acta de una aprobación vieja diría el nombre nuevo. El
acta registra qué decía el cargo ESE día.

Sin backfill
------------
Las versiones aprobadas antes de esta migración quedan en NULL y el
`DocumentContext` cae al lookup, que es exactamente lo que hacía hasta ahora.
Rellenarlas con los valores de hoy sería fabricar el dato que esto viene a
proteger.

Revision ID: 0017_acta_snapshot
Revises: 0016_version_validity
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "0017_acta_snapshot"
down_revision = "0016_version_validity"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


_COLUMNAS = (
    "acta_elaborated_by_name",
    "acta_elaborated_by_role",
    "acta_reviewed_by_name",
    "acta_reviewed_by_role",
    "acta_approved_by_name",
    "acta_approved_by_role",
    "acta_client_name",
)


def upgrade() -> None:
    conn = op.get_bind()
    for columna in _COLUMNAS:
        conn.execute(
            text(
                f"ALTER TABLE {SCHEMA}.document_versions "
                f"ADD COLUMN IF NOT EXISTS {columna} VARCHAR(300)"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    for columna in _COLUMNAS:
        conn.execute(
            text(f"ALTER TABLE {SCHEMA}.document_versions DROP COLUMN IF EXISTS {columna}")
        )
