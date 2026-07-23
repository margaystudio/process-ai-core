"""tyto_query_log (registro de consultas a Tyto)

Una fila por pregunta a Tyto: qué se preguntó, si se respondió o se rechazó, y
qué fuentes se usaron (spec "Tyto — Capa de respuesta" §1 "Segura"). Alimenta el
futuro dashboard de "preguntas sin respuesta" (ADR-011). Tabla de auditoría
desacoplada: sin FKs duras, el rastro sobrevive a borrados de documentos/usuarios.

NO aplicar al sandbox hasta que la rama entre a develop (acuerdo de proceso en
docs/HANDOFF_DOCUMENT_TYPES.md).

Revision ID: 0012_tyto_query_log
Revises: 0011_ko_name_embedding
Create Date: 2026-07-23
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


revision = "0012_tyto_query_log"
down_revision = "0011_ko_name_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tyto_query_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answered", sa.Boolean(), nullable=False),
        sa.Column("refusal_reason", sa.Text(), nullable=True),
        sa.Column("sources_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_tyto_query_log_workspace_id", "tyto_query_log", ["workspace_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_tyto_query_log_user_id", "tyto_query_log", ["user_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_tyto_query_log_ws_created",
        "tyto_query_log",
        ["workspace_id", "created_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_tyto_query_log_ws_created", table_name="tyto_query_log", schema=SCHEMA)
    op.drop_index("ix_tyto_query_log_user_id", table_name="tyto_query_log", schema=SCHEMA)
    op.drop_index("ix_tyto_query_log_workspace_id", table_name="tyto_query_log", schema=SCHEMA)
    op.drop_table("tyto_query_log", schema=SCHEMA)
