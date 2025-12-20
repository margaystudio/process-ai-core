"""
Migración: Agregar columna document_id a la tabla runs.

Ejecutar:
    python tools/migrate_add_document_id_to_runs.py
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    # Verificar si la tabla runs existe
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='runs'
        """))
        if not result.fetchone():
            print("⚠ Tabla 'runs' no existe. Creando tabla completa...")
            # Si la tabla no existe, usar create_all
            from process_ai_core.db.database import Base
            from process_ai_core.db.models import Run, Artifact
            Base.metadata.create_all(bind=engine, tables=[Run.__table__, Artifact.__table__])
            print("✅ Tabla 'runs' creada con el esquema completo")
            return
    
    with get_db_session() as session:
        try:
            # Verificar si la columna document_id ya existe
            print("Verificando si la columna 'document_id' existe en 'runs'...")
            result = session.execute(text("""
                PRAGMA table_info(runs)
            """))
            columns = [row[1] for row in result.fetchall()]
            
            if 'document_id' in columns:
                print("  ✓ Columna document_id ya existe")
            else:
                # Agregar columna document_id
                print("Agregando columna 'document_id' a 'runs'...")
                session.execute(text("""
                    ALTER TABLE runs ADD COLUMN document_id VARCHAR(36)
                """))
                print("  ✓ Columna document_id agregada")
                
                # Crear índice en document_id
                print("Creando índice en document_id...")
                try:
                    session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_runs_document_id ON runs(document_id)
                    """))
                    print("  ✓ Índice creado")
                except Exception as e:
                    print(f"  ⚠ Error creando índice (puede que ya exista): {e}")
            
            session.commit()
            print("\n✅ Migración completada exitosamente")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error en la migración: {e}")
            raise


if __name__ == "__main__":
    migrate()

