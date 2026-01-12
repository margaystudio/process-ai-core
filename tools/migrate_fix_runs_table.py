"""
Migración: Corregir estructura de la tabla runs.

Elimina columnas obsoletas (process_id, mode) y agrega/corrige columnas necesarias:
- Elimina process_id (reemplazado por document_id)
- Elimina mode (reemplazado por profile)
- Agrega profile si no existe
- Asegura que document_id y document_type sean NOT NULL
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        try:
            # Verificar estructura actual
            result = session.execute(text("PRAGMA table_info(runs)"))
            columns = {row[1]: row for row in result.fetchall()}
            
            print("Estructura actual de 'runs':")
            for col_name in columns.keys():
                print(f"  - {col_name}")
            
            # Verificar si necesita corrección
            has_obsolete = 'process_id' in columns or 'mode' in columns
            missing_profile = 'profile' not in columns
            document_id_nullable = columns.get('document_id', [None, None, None, None, None, None])[3] == 0
            
            if has_obsolete or missing_profile or document_id_nullable:
                print("\nCorrigiendo estructura de 'runs'...")
                
                # Crear nueva tabla con estructura correcta
                session.execute(text("""
                    CREATE TABLE runs_new (
                        id VARCHAR(36) PRIMARY KEY,
                        document_id VARCHAR(36) NOT NULL,
                        document_type VARCHAR(20) NOT NULL,
                        profile VARCHAR(50) DEFAULT '',
                        input_manifest_json TEXT DEFAULT '{}',
                        prompt_hash VARCHAR(64) DEFAULT '',
                        model_text VARCHAR(100) DEFAULT '',
                        model_transcribe VARCHAR(100) DEFAULT '',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (document_id) REFERENCES documents(id)
                    )
                """))
                
                # Copiar datos existentes
                # Mapear process_id -> document_id si existe
                select_cols = []
                if 'id' in columns:
                    select_cols.append('id')
                else:
                    select_cols.append("'' as id")
                
                # document_id: usar document_id si existe, sino process_id, sino NULL
                if 'document_id' in columns and columns['document_id'][3] == 1:  # NOT NULL
                    select_cols.append('document_id')
                elif 'document_id' in columns:
                    select_cols.append('COALESCE(document_id, process_id) as document_id')
                elif 'process_id' in columns:
                    select_cols.append('process_id as document_id')
                else:
                    select_cols.append("NULL as document_id")
                
                # document_type: usar si existe, sino NULL
                if 'document_type' in columns:
                    select_cols.append('document_type')
                else:
                    select_cols.append("'process' as document_type")  # Default para datos antiguos
                
                # profile: usar mode si existe, sino ''
                if 'profile' in columns:
                    select_cols.append('profile')
                elif 'mode' in columns:
                    select_cols.append('mode as profile')
                else:
                    select_cols.append("'' as profile")
                
                # Otros campos
                for col in ['input_manifest_json', 'prompt_hash', 'model_text', 'model_transcribe', 'created_at']:
                    if col in columns:
                        select_cols.append(col)
                    else:
                        if col == 'input_manifest_json':
                            select_cols.append("'{}' as input_manifest_json")
                        elif col in ['prompt_hash', 'model_text', 'model_transcribe']:
                            select_cols.append(f"'' as {col}")
                        elif col == 'created_at':
                            select_cols.append("CURRENT_TIMESTAMP as created_at")
                
                select_sql = f"SELECT {', '.join(select_cols)} FROM runs"
                
                # Solo copiar si hay datos
                count_result = session.execute(text("SELECT COUNT(*) FROM runs"))
                count = count_result.scalar()
                
                if count > 0:
                    session.execute(text(f"""
                        INSERT INTO runs_new (id, document_id, document_type, profile, input_manifest_json, prompt_hash, model_text, model_transcribe, created_at)
                        {select_sql}
                    """))
                    print(f"  ✓ Copiados {count} registros")
                
                # Eliminar tabla vieja y renombrar nueva
                session.execute(text("DROP TABLE runs"))
                session.execute(text("ALTER TABLE runs_new RENAME TO runs"))
                
                # Recrear índices
                session.execute(text("CREATE INDEX IF NOT EXISTS idx_runs_document_id ON runs(document_id)"))
                
                print("  ✓ Tabla runs corregida")
            else:
                print("  ✓ Tabla runs ya tiene la estructura correcta")
            
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



