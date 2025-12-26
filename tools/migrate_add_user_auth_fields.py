"""
Script de migración para agregar campos de autenticación a la tabla users.

Agrega:
- external_id
- auth_provider
- auth_metadata_json
- updated_at
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from process_ai_core.db.database import get_db_engine


def migrate_user_table():
    """Agrega campos de autenticación a la tabla users."""
    engine = get_db_engine()
    inspector = inspect(engine)

    if "users" not in inspector.get_table_names():
        print("⚠️  La tabla 'users' no existe. Creándola...")
        from process_ai_core.db.database import Base
        from process_ai_core.db.models import User
        Base.metadata.create_all(engine, tables=[User.__table__])
        print("✅ Tabla 'users' creada.")
        return

    columns = [col["name"] for col in inspector.get_columns("users")]
    missing_columns = []

    if "external_id" not in columns:
        missing_columns.append("external_id VARCHAR(255)")
    if "auth_provider" not in columns:
        missing_columns.append("auth_provider VARCHAR(50) DEFAULT 'local'")
    if "auth_metadata_json" not in columns:
        missing_columns.append("auth_metadata_json TEXT DEFAULT '{}'")
    if "updated_at" not in columns:
        missing_columns.append("updated_at DATETIME")

    if not missing_columns:
        print("✅ Todas las columnas ya existen en la tabla 'users'.")
        return

    print(f"📦 Agregando {len(missing_columns)} columnas a la tabla 'users'...")

    with engine.connect() as conn:
        for col_def in missing_columns:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_def}"))
                print(f"  ✅ Agregada columna: {col_def.split()[0]}")
            except Exception as e:
                print(f"  ⚠️  Error agregando columna {col_def.split()[0]}: {e}")

        conn.commit()

    print("✅ Migración completada.")


if __name__ == "__main__":
    print("🚀 Iniciando migración de tabla users...")
    migrate_user_table()
    print("✅ Migración finalizada!")


