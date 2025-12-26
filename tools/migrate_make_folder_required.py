"""
Migración: Hacer folder_id obligatorio y crear carpetas raíz.

1. Crea una carpeta raíz para cada workspace que no tenga una
2. Asigna documentos huérfanos a la carpeta raíz de su workspace
3. Hace folder_id NOT NULL en documents
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session, get_db_engine
import uuid


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        try:
            # 1. Obtener todos los workspaces
            print("Obteniendo workspaces...")
            workspaces = session.execute(text("SELECT id, name FROM workspaces")).fetchall()
            print(f"  ✓ Encontrados {len(workspaces)} workspaces")
            
            # 2. Para cada workspace, crear carpeta raíz si no existe
            root_folders = {}
            for workspace_id, workspace_name in workspaces:
                # Verificar si ya tiene una carpeta raíz (sin parent_id)
                result = session.execute(text("""
                    SELECT id FROM folders 
                    WHERE workspace_id = :workspace_id AND parent_id IS NULL
                    LIMIT 1
                """), {"workspace_id": workspace_id})
                
                existing_root = result.fetchone()
                
                if existing_root:
                    root_folders[workspace_id] = existing_root[0]
                    print(f"  ✓ Workspace '{workspace_name}' ya tiene carpeta raíz")
                else:
                    # Crear carpeta raíz
                    root_folder_id = str(uuid.uuid4())
                    session.execute(text("""
                        INSERT INTO folders (id, workspace_id, name, path, parent_id, sort_order, metadata_json, created_at)
                        VALUES (:id, :workspace_id, :name, :name, NULL, 0, '{}', CURRENT_TIMESTAMP)
                    """), {
                        "id": root_folder_id,
                        "workspace_id": workspace_id,
                        "name": workspace_name
                    })
                    root_folders[workspace_id] = root_folder_id
                    print(f"  ✓ Creada carpeta raíz para workspace '{workspace_name}'")
            
            # 3. Asignar documentos huérfanos a la carpeta raíz de su workspace
            print("\nAsignando documentos huérfanos a carpetas raíz...")
            orphan_docs = session.execute(text("""
                SELECT id, workspace_id FROM documents WHERE folder_id IS NULL
            """)).fetchall()
            
            if orphan_docs:
                print(f"  Encontrados {len(orphan_docs)} documentos sin carpeta")
                for doc_id, doc_workspace_id in orphan_docs:
                    if doc_workspace_id in root_folders:
                        root_folder_id = root_folders[doc_workspace_id]
                        session.execute(text("""
                            UPDATE documents SET folder_id = :folder_id WHERE id = :doc_id
                        """), {
                            "folder_id": root_folder_id,
                            "doc_id": doc_id
                        })
                        print(f"    ✓ Documento {doc_id} asignado a carpeta raíz")
                    else:
                        print(f"    ⚠ Documento {doc_id} sin workspace válido")
            else:
                print("  ✓ No hay documentos huérfanos")
            
            # 4. Verificar que todos los documentos tengan folder_id
            result = session.execute(text("SELECT COUNT(*) FROM documents WHERE folder_id IS NULL"))
            remaining_orphans = result.scalar()
            
            if remaining_orphans > 0:
                raise Exception(f"Quedan {remaining_orphans} documentos sin folder_id")
            
            # 5. Hacer folder_id NOT NULL
            print("\nHaciendo folder_id NOT NULL...")
            # SQLite no soporta ALTER COLUMN directamente, necesitamos recrear la tabla
            session.execute(text("""
                CREATE TABLE documents_new (
                    id VARCHAR(36) PRIMARY KEY,
                    workspace_id VARCHAR(36) NOT NULL,
                    document_type VARCHAR(20) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    description TEXT DEFAULT '',
                    status VARCHAR(20) DEFAULT 'draft',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    folder_id VARCHAR(36) NOT NULL,
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                    FOREIGN KEY (folder_id) REFERENCES folders(id)
                )
            """))
            
            # Copiar datos
            session.execute(text("""
                INSERT INTO documents_new 
                SELECT id, workspace_id, document_type, name, description, status, created_at, folder_id
                FROM documents
            """))
            
            # Eliminar tabla vieja y renombrar nueva
            session.execute(text("DROP TABLE documents"))
            session.execute(text("ALTER TABLE documents_new RENAME TO documents"))
            
            # Recrear índices
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_workspace_id ON documents(workspace_id)"))
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_folder_id ON documents(folder_id)"))
            
            print("  ✓ folder_id ahora es NOT NULL")
            
            session.commit()
            print("\n✅ Migración completada exitosamente")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error en la migración: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    migrate()


