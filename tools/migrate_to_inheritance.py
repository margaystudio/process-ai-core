"""
Migración: Convertir Document a herencia (Process/Recipe heredan de Document).

Esta migración:
1. Renombra la columna `domain` a `document_type` en `documents`
2. Crea las tablas `processes` y `recipes`
3. Migra datos existentes de `documents` a las tablas específicas
4. Actualiza `runs.document_type` para que coincida con `documents.document_type`

Ejecutar:
    python tools/migrate_to_inheritance.py
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        try:
            # 1. Verificar si la tabla documents existe
            result = session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='documents'
            """))
            if not result.fetchone():
                print("⚠ Tabla 'documents' no existe. Creando tablas desde cero...")
                from process_ai_core.db.database import Base
                from process_ai_core.db.models import Document, Process, Recipe
                Base.metadata.create_all(bind=engine, tables=[Document.__table__, Process.__table__, Recipe.__table__])
                print("✅ Tablas creadas")
                return
            
            # 2. Renombrar columna `domain` a `document_type` si existe
            print("Verificando columna 'domain' en 'documents'...")
            result = session.execute(text("PRAGMA table_info(documents)"))
            columns = {row[1]: row for row in result.fetchall()}
            
            if 'domain' in columns and 'document_type' not in columns:
                print("Renombrando columna 'domain' a 'document_type'...")
                # SQLite no soporta ALTER TABLE RENAME COLUMN directamente en versiones antiguas
                # Usamos un enfoque de copia
                session.execute(text("""
                    CREATE TABLE documents_new (
                        id VARCHAR(36) PRIMARY KEY,
                        workspace_id VARCHAR(36) NOT NULL,
                        document_type VARCHAR(20) NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT DEFAULT '',
                        status VARCHAR(20) DEFAULT 'draft',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        folder_id VARCHAR(36),
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                        FOREIGN KEY (folder_id) REFERENCES folders(id)
                    )
                """))
                
                # Copiar datos
                session.execute(text("""
                    INSERT INTO documents_new (id, workspace_id, document_type, name, description, status, created_at, folder_id)
                    SELECT id, workspace_id, domain, name, description, status, created_at, folder_id
                    FROM documents
                """))
                
                # Eliminar tabla vieja y renombrar nueva
                session.execute(text("DROP TABLE documents"))
                session.execute(text("ALTER TABLE documents_new RENAME TO documents"))
                
                # Recrear índices
                session.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_workspace_id ON documents(workspace_id)"))
                session.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_folder_id ON documents(folder_id)"))
                
                print("  ✓ Columna renombrada")
            elif 'document_type' in columns:
                print("  ✓ Columna document_type ya existe")
            
            # 3. Crear tabla processes si no existe
            print("Creando tabla 'processes'...")
            result = session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='processes'
            """))
            if not result.fetchone():
                session.execute(text("""
                    CREATE TABLE processes (
                        id VARCHAR(36) PRIMARY KEY,
                        audience VARCHAR(50) DEFAULT '',
                        detail_level VARCHAR(50) DEFAULT '',
                        context_text TEXT DEFAULT '',
                        FOREIGN KEY (id) REFERENCES documents(id)
                    )
                """))
                print("  ✓ Tabla processes creada")
            else:
                print("  ✓ Tabla processes ya existe")
            
            # 4. Crear tabla recipes si no existe
            print("Creando tabla 'recipes'...")
            result = session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='recipes'
            """))
            if not result.fetchone():
                session.execute(text("""
                    CREATE TABLE recipes (
                        id VARCHAR(36) PRIMARY KEY,
                        cuisine VARCHAR(50) DEFAULT '',
                        difficulty VARCHAR(20) DEFAULT '',
                        servings INTEGER DEFAULT 0,
                        prep_time VARCHAR(50) DEFAULT '',
                        cook_time VARCHAR(50) DEFAULT '',
                        FOREIGN KEY (id) REFERENCES documents(id)
                    )
                """))
                print("  ✓ Tabla recipes creada")
            else:
                print("  ✓ Tabla recipes ya existe")
            
            # 5. Migrar datos existentes de documents a processes/recipes
            print("Migrando datos existentes...")
            
            # Obtener documentos que son procesos pero no están en processes
            result = session.execute(text("""
                SELECT d.id, d.document_type
                FROM documents d
                LEFT JOIN processes p ON d.id = p.id
                WHERE d.document_type = 'process' AND p.id IS NULL
            """))
            process_docs = result.fetchall()
            
            if process_docs:
                print(f"  Migrando {len(process_docs)} procesos...")
                # Extraer metadata de domain_metadata_json si existe
                # Por ahora, crear registros vacíos (los campos se pueden actualizar después)
                for doc_id, doc_type in process_docs:
                    session.execute(text("""
                        INSERT INTO processes (id, audience, detail_level, context_text)
                        VALUES (:id, '', '', '')
                    """), {"id": doc_id})
                print(f"  ✓ {len(process_docs)} procesos migrados")
            
            # Obtener documentos que son recetas pero no están en recipes
            result = session.execute(text("""
                SELECT d.id, d.document_type
                FROM documents d
                LEFT JOIN recipes r ON d.id = r.id
                WHERE d.document_type = 'recipe' AND r.id IS NULL
            """))
            recipe_docs = result.fetchall()
            
            if recipe_docs:
                print(f"  Migrando {len(recipe_docs)} recetas...")
                for doc_id, doc_type in recipe_docs:
                    session.execute(text("""
                        INSERT INTO recipes (id, cuisine, difficulty, servings, prep_time, cook_time)
                        VALUES (:id, '', '', 0, '', '')
                    """), {"id": doc_id})
                print(f"  ✓ {len(recipe_docs)} recetas migradas")
            
            # 6. Actualizar runs.document_type si existe la columna
            print("Actualizando runs.document_type...")
            result = session.execute(text("PRAGMA table_info(runs)"))
            run_columns = {row[1]: row for row in result.fetchall()}
            
            if 'document_type' not in run_columns:
                # Agregar columna document_type a runs
                session.execute(text("""
                    ALTER TABLE runs ADD COLUMN document_type VARCHAR(20)
                """))
                print("  ✓ Columna document_type agregada a runs")
            
            # Actualizar document_type en runs basado en documents
            session.execute(text("""
                UPDATE runs
                SET document_type = (
                    SELECT document_type
                    FROM documents
                    WHERE documents.id = runs.document_id
                )
                WHERE document_type IS NULL
            """))
            print("  ✓ document_type actualizado en runs")
            
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



