"""
Migración: Agregar carpetas jerárquicas para archivos de contexto.

Ejecutar:
    python tools/migrate_add_context_folders.py
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session


def migrate():
    """Ejecuta la migración."""
    with get_db_session() as session:
        try:
            print("Creando tabla 'context_folders'...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS context_folders (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_id VARCHAR(36) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    path VARCHAR(500) DEFAULT '',
                    parent_id VARCHAR(36),
                    sort_order INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY (parent_id) REFERENCES context_folders(id)
                )
            """))

            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_context_folders_workspace_id
                ON context_folders(workspace_id)
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_context_folders_parent_id
                ON context_folders(parent_id)
            """))

            print("Agregando columna 'folder_id' a 'context_files'...")
            try:
                session.execute(text("""
                    ALTER TABLE context_files ADD COLUMN folder_id VARCHAR(36)
                """))
                print("  Columna folder_id agregada")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("  Columna folder_id ya existe")
                else:
                    raise

            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_context_files_folder_id
                ON context_files(folder_id)
            """))

            session.commit()
            print("\nMigracion completada exitosamente")
        except Exception as e:
            session.rollback()
            print(f"\nError en la migracion: {e}")
            raise


if __name__ == "__main__":
    migrate()
