"""
Migración: Corregir estructura de la tabla processes.

Elimina columnas obsoletas (client_id, name, description, etc.) que ya están en documents,
y deja solo los campos específicos de Process.
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        try:
            # Verificar si la tabla processes existe
            result = session.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='processes'
            """))
            if not result.fetchone():
                print("⚠ Tabla 'processes' no existe. Creando...")
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
                session.commit()
                return
            
            # Obtener estructura actual
            result = session.execute(text("PRAGMA table_info(processes)"))
            columns = {row[1]: row for row in result.fetchall()}
            
            # Verificar si tiene columnas obsoletas
            obsolete_columns = ['client_id', 'name', 'description', 'status', 'process_type', 
                              'formality', 'preferences_json', 'created_at']
            has_obsolete = any(col in columns for col in obsolete_columns)
            
            if has_obsolete:
                print("Eliminando columnas obsoletas de 'processes'...")
                
                # Crear nueva tabla con estructura correcta
                session.execute(text("""
                    CREATE TABLE processes_new (
                        id VARCHAR(36) PRIMARY KEY,
                        audience VARCHAR(50) DEFAULT '',
                        detail_level VARCHAR(50) DEFAULT '',
                        context_text TEXT DEFAULT '',
                        FOREIGN KEY (id) REFERENCES documents(id)
                    )
                """))
                
                # Copiar datos existentes (solo los campos que nos interesan)
                # Primero verificar qué columnas existen
                existing_cols = list(columns.keys())
                select_cols = []
                if 'id' in existing_cols:
                    select_cols.append('id')
                if 'audience' in existing_cols:
                    select_cols.append('audience')
                else:
                    select_cols.append("'' as audience")
                if 'detail_level' in existing_cols:
                    select_cols.append('detail_level')
                else:
                    select_cols.append("'' as detail_level")
                if 'context_text' in existing_cols:
                    select_cols.append('context_text')
                else:
                    select_cols.append("'' as context_text")
                
                select_sql = f"SELECT {', '.join(select_cols)} FROM processes"
                session.execute(text(f"""
                    INSERT INTO processes_new (id, audience, detail_level, context_text)
                    {select_sql}
                """))
                
                # Eliminar tabla vieja y renombrar nueva
                session.execute(text("DROP TABLE processes"))
                session.execute(text("ALTER TABLE processes_new RENAME TO processes"))
                
                print("  ✓ Tabla processes corregida")
            else:
                # Verificar que tenga las columnas correctas
                required_cols = ['id', 'audience', 'detail_level', 'context_text']
                missing_cols = [col for col in required_cols if col not in columns]
                
                if missing_cols:
                    print(f"Agregando columnas faltantes: {missing_cols}...")
                    for col in missing_cols:
                        if col == 'id':
                            continue  # id ya existe
                        elif col == 'audience':
                            session.execute(text("ALTER TABLE processes ADD COLUMN audience VARCHAR(50) DEFAULT ''"))
                        elif col == 'detail_level':
                            session.execute(text("ALTER TABLE processes ADD COLUMN detail_level VARCHAR(50) DEFAULT ''"))
                        elif col == 'context_text':
                            session.execute(text("ALTER TABLE processes ADD COLUMN context_text TEXT DEFAULT ''"))
                    print("  ✓ Columnas agregadas")
                else:
                    print("  ✓ Tabla processes ya tiene la estructura correcta")
            
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

