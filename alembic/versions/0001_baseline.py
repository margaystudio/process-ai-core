"""baseline: schema process_ai + todas las tablas actuales (esquema congelado)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-29

Migración base **congelada**. Crea el schema del módulo y todas las tablas a partir
de un snapshot DDL fijo (`0001_baseline.sql`), generado desde los modelos. A
diferencia de un baseline por `create_all`, este NO sigue cambiando con los modelos:
las modificaciones posteriores se hacen con migraciones normales
(`alembic revision --autogenerate`), sin guards ni trucos.

El DDL usa el schema literal `process_ai`; en runtime se sustituye por
`DATABASE_SCHEMA` (permite schemas descartables en tests). Requiere modo online.
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

from process_ai_core.db.database import Base, DATABASE_SCHEMA

# Importar los modelos asegura que Base.metadata tenga todas las tablas (downgrade).
import process_ai_core.db.models  # noqa: F401
import process_ai_core.db.models_catalog  # noqa: F401

# identificadores usados por Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).with_suffix(".sql")
_FROZEN_SCHEMA = "process_ai"  # schema literal usado al generar el DDL


def upgrade() -> None:
    schema = DATABASE_SCHEMA or _FROZEN_SCHEMA

    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')

    ddl = _SQL_FILE.read_text(encoding="utf-8")
    if schema != _FROZEN_SCHEMA:
        ddl = ddl.replace(_FROZEN_SCHEMA, schema)

    for statement in ddl.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)

    # Grants de Supabase (anon/authenticated/service_role). Guardado por existencia
    # de rol para que corra también en un Postgres vanilla (tests/CI).
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
            EXECUTE format('GRANT USAGE ON SCHEMA %I TO anon, authenticated, service_role', '{schema}');
            EXECUTE format('GRANT ALL ON ALL TABLES IN SCHEMA %I TO postgres, service_role', '{schema}');
            EXECUTE format('GRANT ALL ON ALL SEQUENCES IN SCHEMA %I TO postgres, service_role', '{schema}');
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Dropea cada tabla con CASCADE (el modelo tiene FKs circulares sin nombre que
    # impiden ordenar el DROP). No toca `alembic_version` (no está en metadata).
    prefix = f'"{DATABASE_SCHEMA}".' if DATABASE_SCHEMA else ""
    for table in Base.metadata.tables.values():
        op.execute(f'DROP TABLE IF EXISTS {prefix}"{table.name}" CASCADE')
