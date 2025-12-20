"""
Migración: Eliminar tablas obsoletas.

Elimina tablas que ya no se usan:
- clients (reemplazado por workspaces)
- artifacts_v2 (reemplazado por artifacts)
- runs_v2 (reemplazado por runs)
"""

from sqlalchemy import text

from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    with get_db_session() as session:
        try:
            obsolete_tables = ['clients', 'artifacts_v2', 'runs_v2']
            
            for table_name in obsolete_tables:
                result = session.execute(text(f"""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='{table_name}'
                """))
                
                if result.fetchone():
                    print(f"Eliminando tabla obsoleta '{table_name}'...")
                    session.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                    print(f"  ✓ Tabla {table_name} eliminada")
                else:
                    print(f"  ✓ Tabla {table_name} no existe (ya fue eliminada)")
            
            session.commit()
            print("\n✅ Limpieza completada exitosamente")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error en la limpieza: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    migrate()

