"""
Migración: Agregar campo created_by a document_versions.

Este campo representa al usuario que creó la versión.
En esta primera migración puede ser NULL, pero está preparado para backfill y futura constraint NOT NULL.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Agrega la columna created_by a document_versions."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        print("=" * 70)
        print("  MIGRACIÓN: Agregar campo created_by a document_versions")
        print("=" * 70)
        print()
        
        # Verificar qué columnas ya existen
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('document_versions')]
        
        if "created_by" in columns:
            print("✅ La columna created_by ya existe en document_versions. Migración ya aplicada.")
            return
        
        print("🔨 Agregando columna created_by a document_versions...")
        session.execute(text("""
            ALTER TABLE document_versions
            ADD COLUMN created_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL
        """))
        
        print("📊 Creando índice por created_by...")
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_versions_created_by 
            ON document_versions(created_by)
        """))
        
        session.commit()
        print("✅ Migración completada exitosamente.")


if __name__ == "__main__":
    migrate()
