"""
Script de migración para agregar campos de teléfono a la tabla users.

Agrega:
- phone_e164
- phone_verified
- phone_verified_at
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from process_ai_core.db.database import get_db_engine


def migrate_user_table():
    """Agrega campos de teléfono a la tabla users."""
    engine = get_db_engine()
    inspector = inspect(engine)

    if "users" not in inspector.get_table_names():
        print("⚠️  La tabla 'users' no existe. Ejecutá primero las migraciones base.")
        return

    columns = [col["name"] for col in inspector.get_columns("users")]
    missing = []

    if "phone_e164" not in columns:
        missing.append(("phone_e164", "ALTER TABLE users ADD COLUMN phone_e164 VARCHAR(20)"))
    if "phone_verified" not in columns:
        missing.append(("phone_verified", "ALTER TABLE users ADD COLUMN phone_verified BOOLEAN DEFAULT 0"))
    if "phone_verified_at" not in columns:
        missing.append(("phone_verified_at", "ALTER TABLE users ADD COLUMN phone_verified_at DATETIME"))

    if not missing:
        print("✅ Todas las columnas de teléfono ya existen en la tabla 'users'.")
        return

    print(f"📦 Agregando {len(missing)} columnas a la tabla 'users'...")
    with engine.connect() as conn:
        for name, sql in missing:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  ✅ Agregada columna: {name}")
            except Exception as e:
                print(f"  ⚠️  Error agregando columna {name}: {e}")
    print("✅ Migración completada.")


if __name__ == "__main__":
    print("🚀 Iniciando migración user phone...")
    migrate_user_table()
    print("✅ Migración finalizada!")
