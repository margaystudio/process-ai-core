"""
Migración: Agregar tabla folders y columna folder_id a documents.

Ejecutar:
    python tools/migrate_add_folders.py
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session


def migrate():
    """Ejecuta la migración."""
    with get_db_session() as session:
        try:
            # 1. Crear tabla folders
            print("Creando tabla 'folders'...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS folders (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_id VARCHAR(36) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    path VARCHAR(500) DEFAULT '',
                    parent_id VARCHAR(36),
                    sort_order INTEGER DEFAULT 0,
                    metadata_json TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY (parent_id) REFERENCES folders(id)
                )
            """))
            
            # 2. Crear índices
            print("Creando índices...")
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_folders_workspace_id ON folders(workspace_id)
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id)
            """))
            
            # 3. Agregar columna folder_id a documents si no existe
            print("Agregando columna 'folder_id' a 'documents'...")
            try:
                session.execute(text("""
                    ALTER TABLE documents ADD COLUMN folder_id VARCHAR(36)
                """))
                print("  ✓ Columna folder_id agregada")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("  ✓ Columna folder_id ya existe")
                else:
                    raise
            
            # 4. Crear índice en folder_id
            print("Creando índice en folder_id...")
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_folder_id ON documents(folder_id)
                """))
            except Exception as e:
                print(f"  ⚠ Error creando índice (puede que ya exista): {e}")
            
            # 5. Agregar foreign key constraint
            print("Agregando foreign key constraint...")
            try:
                session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_folder_id_fk ON documents(folder_id)
                """))
            except Exception as e:
                print(f"  ⚠ Nota sobre foreign key: {e}")
            
            session.commit()
            print("\n✅ Migración completada exitosamente")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error en la migración: {e}")
            raise


if __name__ == "__main__":
    migrate()

