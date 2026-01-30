#!/usr/bin/env python3
"""
Migración: Agregar columnas comunes a la tabla workspaces.

Esta migración agrega las columnas:
- country
- business_type
- language_style
- default_audience
- default_detail_level
- context_text

Ejecutar:
    python tools/migrate_add_workspace_columns.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from process_ai_core.db.database import get_db_session, get_db_engine


def add_workspace_columns():
    """Agrega las columnas comunes a la tabla workspaces."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        print("=" * 70)
        print("  MIGRACIÓN: Agregar columnas a workspaces")
        print("=" * 70)
        print()
        
        # Columnas a agregar
        columns = [
            ("country", "VARCHAR(2)", "NULL"),
            ("business_type", "VARCHAR(50)", "NULL"),
            ("language_style", "VARCHAR(50)", "NULL"),
            ("default_audience", "VARCHAR(50)", "NULL"),
            ("default_detail_level", "VARCHAR(50)", "NULL"),
            ("context_text", "TEXT", "NULL"),
            ("description", "TEXT", "NULL"),
        ]
        
        # Verificar qué columnas ya existen
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_columns = {col["name"] for col in inspector.get_columns("workspaces")}
        
        print("📊 Columnas existentes en workspaces:")
        for col in existing_columns:
            print(f"   ✓ {col}")
        print()
        
        # Agregar columnas que no existen
        added_count = 0
        for col_name, col_type, default in columns:
            if col_name in existing_columns:
                print(f"⏭️  Columna '{col_name}' ya existe, saltando...")
                continue
            
            try:
                # SQLite no soporta ADD COLUMN IF NOT EXISTS, así que verificamos antes
                sql = f"ALTER TABLE workspaces ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                session.execute(text(sql))
                print(f"✅ Columna '{col_name}' agregada")
                added_count += 1
            except Exception as e:
                print(f"⚠️  Error agregando columna '{col_name}': {e}")
        
        # Crear índices para campos que se usan en filtros
        if "country" not in existing_columns:
            try:
                session.execute(text("CREATE INDEX IF NOT EXISTS ix_workspaces_country ON workspaces(country)"))
                print("✅ Índice en 'country' creado")
            except Exception as e:
                print(f"⚠️  Error creando índice en 'country': {e}")
        
        if "business_type" not in existing_columns:
            try:
                session.execute(text("CREATE INDEX IF NOT EXISTS ix_workspaces_business_type ON workspaces(business_type)"))
                print("✅ Índice en 'business_type' creado")
            except Exception as e:
                print(f"⚠️  Error creando índice en 'business_type': {e}")
        
        session.commit()
        
        print()
        print("=" * 70)
        print("  ✅ MIGRACIÓN COMPLETADA")
        print("=" * 70)
        print()
        print(f"📊 Resumen:")
        print(f"  - Columnas agregadas: {added_count}")
        print(f"  - Columnas ya existentes: {len(columns) - added_count}")
        print()


if __name__ == "__main__":
    add_workspace_columns()
