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
    """Deja el schema vacío. Enumera del CATÁLOGO, no de `Base.metadata`.

    Antes iteraba `Base.metadata.tables`, o sea las tablas que los modelos
    definen HOY, y eso deja atrás dos clases de tabla:

      - las que una migración posterior **recrea al bajar** y el modelo ya no
        tiene (`workspace_invitations`: la 0020 la recrea en su downgrade, pero
        el modelo se eliminó, así que acá era invisible);
      - las que **nunca tuvieron modelo** porque son de infraestructura de una
        migración (`users_id_remap`, de la 0022).

    Es la misma trampa que la del inventario congelado de la 0022: una migración
    que le pregunta al código vivo cómo era el mundo se desincroniza sola. El
    catálogo, en cambio, dice lo que hay de verdad en este momento.

    Se dropea con CASCADE porque el schema tiene FKs circulares sin nombre que
    impiden ordenar los DROP. `alembic_version` se excluye: la maneja Alembic.
    """
    from sqlalchemy import text

    conn = op.get_bind()
    schema = DATABASE_SCHEMA or "public"
    tablas = conn.execute(
        text(
            """
            SELECT tablename FROM pg_tables
             WHERE schemaname = :s AND tablename <> 'alembic_version'
            """
        ),
        {"s": schema},
    ).fetchall()
    prefix = f'"{schema}".' if DATABASE_SCHEMA else ""
    for (nombre,) in tablas:
        op.execute(f'DROP TABLE IF EXISTS {prefix}"{nombre}" CASCADE')
