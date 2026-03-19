"""
Migración: Tablas de roles operativos y permisos por carpeta.

Crea:
- operational_roles
- user_operational_roles (asignación rol operativo a membership)
- folder_permissions
- Columna inherits_permissions en folders

Ejecutar:
    python tools/migrate_add_operational_roles.py
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session


def migrate():
    """Ejecuta la migración."""
    with get_db_session() as session:
        try:
            # 1. Tabla operational_roles
            print("Creando tabla 'operational_roles'...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS operational_roles (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_id VARCHAR(36) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    slug VARCHAR(100) NOT NULL,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                )
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_operational_roles_workspace_id
                ON operational_roles(workspace_id)
            """))
            session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_operational_roles_workspace_slug
                ON operational_roles(workspace_id, slug)
            """))

            # 2. Tabla user_operational_roles (workspace_user_id = workspace_memberships.id)
            print("Creando tabla 'user_operational_roles'...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS user_operational_roles (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_membership_id VARCHAR(36) NOT NULL,
                    operational_role_id VARCHAR(36) NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    assigned_by VARCHAR(36),
                    FOREIGN KEY (workspace_membership_id) REFERENCES workspace_memberships(id) ON DELETE CASCADE,
                    FOREIGN KEY (operational_role_id) REFERENCES operational_roles(id) ON DELETE CASCADE,
                    FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL
                )
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_operational_roles_membership
                ON user_operational_roles(workspace_membership_id)
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_operational_roles_role
                ON user_operational_roles(operational_role_id)
            """))
            session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_operational_roles_membership_role
                ON user_operational_roles(workspace_membership_id, operational_role_id)
            """))

            # 3. Tabla folder_permissions
            print("Creando tabla 'folder_permissions'...")
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS folder_permissions (
                    id VARCHAR(36) PRIMARY KEY,
                    folder_id VARCHAR(36) NOT NULL,
                    operational_role_id VARCHAR(36) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE,
                    FOREIGN KEY (operational_role_id) REFERENCES operational_roles(id) ON DELETE CASCADE
                )
            """))
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_folder_permissions_folder_id
                ON folder_permissions(folder_id)
            """))
            session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_folder_permissions_folder_role
                ON folder_permissions(folder_id, operational_role_id)
            """))

            # 4. Columna inherits_permissions en folders
            print("Agregando columna 'inherits_permissions' a 'folders'...")
            try:
                session.execute(text("""
                    ALTER TABLE folders ADD COLUMN inherits_permissions INTEGER DEFAULT 1
                """))
                print("  OK Columna inherits_permissions agregada")
            except Exception as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("  OK Columna inherits_permissions ya existe")
                else:
                    raise

            session.commit()
            print("\nMigracion completada exitosamente")

        except Exception as e:
            session.rollback()
            print(f"\nError en la migracion: {e}")
            raise


if __name__ == "__main__":
    migrate()
