"""
Migración: Agregar tabla context_files para archivos de contexto del negocio.

Ejecutar:
    python tools/migrate_add_context_files.py
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session


def migrate():
    """Ejecuta la migración."""
    with get_db_session() as session:
        try:
            print("Creando tabla 'context_files'...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS context_files (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_id VARCHAR(36) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    content TEXT,
                    file_type VARCHAR(50) DEFAULT '',
                    size INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                )
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_context_files_workspace_id ON context_files(workspace_id)
            """))
            session.commit()
            print("\nMigracion completada exitosamente")
        except Exception as e:
            session.rollback()
            print(f"\nError en la migracion: {e}")
            raise


if __name__ == "__main__":
    migrate()
