"""folder_activity_audit

Amplia audit_logs para conservar el contexto de carpeta y registrar acciones
de configuracion/permisos que no pertenecen a un documento.

LIMITACION DEL BACKFILL — leer antes de interpretar la actividad historica
--------------------------------------------------------------------------
El backfill hace `SET folder_id = document.folder_id`, o sea la carpeta donde el
documento esta HOY. Si alguna vez se movio de carpeta, sus eventos anteriores al
movimiento quedan atribuidos a la carpeta actual, no a la que estaba cuando el
evento ocurrio. No hay forma de arreglarlo hacia atras: la carpeta de origen
nunca se registro. Queda dicho porque en una traza de auditoria una atribucion
silenciosamente incorrecta es peor que un hueco: de aca en adelante el folder_id
lo escribe `create_audit_log` en el momento del evento y es exacto.

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
    # Volver a NOT NULL exige que no queden filas sin documento. Antes esto las
    # BORRABA, que es la unica operacion de esta migracion sin vuelta atras: los
    # eventos de carpeta no se reconstruyen desde ningun lado. Ahora falla y
    # deja la decision —y el DELETE explicito— en manos de quien baja.
    conn = op.get_bind()
    huerfanas = conn.execute(
        sa.text(f'SELECT count(*) FROM "{SCHEMA}".audit_logs WHERE document_id IS NULL')
    ).scalar()
    if huerfanas:
        raise RuntimeError(
            f"{huerfanas} evento(s) de auditoria sin document_id (acciones de carpeta). "
            f"Bajar esta migracion los destruye. Si es lo que querés, corré primero:\n"
            f'  DELETE FROM "{SCHEMA}".audit_logs WHERE document_id IS NULL;'
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
