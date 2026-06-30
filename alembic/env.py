"""Entorno de migraciones Alembic para process-ai-core.

Reutiliza la capa de BD de la app (`process_ai_core.db.database`): el mismo
`Base.metadata`, la misma `DATABASE_URL` y el mismo `DATABASE_SCHEMA` (default
`process_ai`). Así las migraciones y la aplicación nunca divergen de configuración.

Importante — la base es **compartida** con margay-workspace (schema `workspace`).
Por eso el autogenerate se **scopea exclusivamente al schema del módulo**: nunca
considera tablas de `workspace` ni de `public`.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Capa de BD de la app: Base + URL + schema (importarla carga .env).
from process_ai_core.db.database import Base, DATABASE_URL, DATABASE_SCHEMA

# Importar los modelos puebla Base.metadata con todas las tablas del módulo.
import process_ai_core.db.models  # noqa: F401,E402

try:  # catálogos opcionales, si existen como tablas
    import process_ai_core.db.models_catalog  # noqa: F401,E402
except Exception:  # pragma: no cover - el módulo puede no declarar tablas
    pass

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_name(name, type_, parent_names):
    """Limita autogenerate al schema del módulo. Jamás `workspace`/`public`."""
    if type_ == "schema":
        return name == DATABASE_SCHEMA
    return True


def run_migrations_offline() -> None:
    """Modo offline (`--sql`): emite SQL sin conectar.

    Nota: la migración baseline crea las tablas vía `metadata.create_all` y por
    eso requiere modo online. Las migraciones autogeneradas posteriores
    (op.create_table/alter) sí renderizan en offline.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=DATABASE_SCHEMA,
        include_schemas=True,
        include_name=_include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = DATABASE_URL

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # El schema del módulo debe existir antes de que Alembic cree su tabla
        # de versiones (alembic_version) dentro de él.
        if DATABASE_SCHEMA:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DATABASE_SCHEMA}"'))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=DATABASE_SCHEMA,
            include_schemas=True,
            include_name=_include_name,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
