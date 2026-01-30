#!/usr/bin/env python3
"""
Script para resetear la base de datos a estado "primer día en producción".

Mantiene solo los datos estáticos:
- permissions
- catalog_options (catalog_option)
- role_permissions
- roles
- subscription_plans

Elimina todos los datos dinámicos:
- workspaces, documents, folders, users, workspace_memberships
- runs, artifacts, validations, audit_logs, document_versions
- workspace_subscriptions, workspace_invitations

Ejecutar:
    python tools/reset_to_production_ready.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from process_ai_core.db.database import get_db_session, get_db_engine
from process_ai_core.db.models import Base


# Tablas estáticas que se mantienen
STATIC_TABLES = [
    "permissions",
    "catalog_option",  # Nombre real de la tabla
    "role_permissions",
    "roles",
    "subscription_plans",
]

# Tablas dinámicas que se eliminan (en orden de dependencias)
DYNAMIC_TABLES = [
    # Tablas con más dependencias primero
    "audit_logs",
    "document_versions",
    "validations",
    "artifacts",
    "runs",
    "workspace_invitations",
    "workspace_subscriptions",
    "workspace_memberships",
    "documents",  # Esto eliminará también processes y recipes (tablas heredadas)
    "folders",
    "workspaces",
    "users",
]


def get_all_tables(session):
    """Obtiene todas las tablas de la base de datos."""
    engine = get_db_engine()
    inspector = inspect(engine)
    return inspector.get_table_names()


def reset_database():
    """Resetea la base de datos eliminando solo datos dinámicos."""
    with get_db_session() as session:
        print("=" * 70)
        print("  RESET DE BASE DE DATOS A ESTADO PRODUCCIÓN INICIAL")
        print("=" * 70)
        print()
        
        # Obtener todas las tablas
        all_tables = get_all_tables(session)
        print(f"📊 Tablas encontradas: {len(all_tables)}")
        print()
        
        # Verificar que las tablas estáticas existen
        print("🔍 Verificando tablas estáticas...")
        missing_static = []
        for table in STATIC_TABLES:
            if table not in all_tables:
                missing_static.append(table)
        
        if missing_static:
            print(f"⚠️  Advertencia: Faltan tablas estáticas: {', '.join(missing_static)}")
            print("   Se recomienda ejecutar los scripts de seed primero:")
            print("   - python tools/seed_permissions.py")
            print("   - python tools/seed_subscription_plans.py")
            print("   - python tools/seed_catalogs.py")
            print()
            response = input("¿Deseas continuar de todas formas? (s/n): ").strip().lower()
            if response != "s":
                print("❌ Cancelado.")
                return
        else:
            print("✅ Todas las tablas estáticas están presentes")
        print()
        
        # Confirmación
        print("⚠️  ADVERTENCIA: Esta operación eliminará TODOS los datos dinámicos:")
        print("   - Workspaces, documentos, carpetas")
        print("   - Usuarios, membresías, invitaciones")
        print("   - Runs, validaciones, versiones, logs de auditoría")
        print("   - Suscripciones")
        print()
        print("✅ Se MANTENDRÁN los datos estáticos:")
        print("   - Permisos, roles, asignaciones de permisos")
        print("   - Planes de suscripción")
        print("   - Opciones de catálogo")
        print()
        response = input("¿Estás seguro de que deseas continuar? (escribe 'RESET' para confirmar): ").strip()
        if response != "RESET":
            print("❌ Cancelado.")
            return
        
        print()
        print("🗑️  Eliminando datos dinámicos...")
        print()
        
        # Desactivar foreign keys temporalmente para SQLite
        try:
            session.execute(text("PRAGMA foreign_keys=OFF"))
        except Exception:
            pass  # No es SQLite o ya está desactivado
        
        deleted_count = 0
        
        # Eliminar datos de tablas dinámicas
        for table in DYNAMIC_TABLES:
            if table in all_tables:
                try:
                    result = session.execute(text(f"DELETE FROM {table}"))
                    count = result.rowcount
                    if count > 0:
                        print(f"   ✓ {table}: {count} registros eliminados")
                        deleted_count += count
                    else:
                        print(f"   - {table}: (vacía)")
                except Exception as e:
                    print(f"   ⚠️  {table}: Error - {e}")
        
        # Reactivar foreign keys
        try:
            session.execute(text("PRAGMA foreign_keys=ON"))
        except Exception:
            pass
        
        print()
        print(f"✅ Eliminados {deleted_count} registros en total")
        print()
        
        # Verificar que las tablas estáticas siguen intactas
        print("🔍 Verificando integridad de tablas estáticas...")
        static_counts = {}
        for table in STATIC_TABLES:
            if table in all_tables:
                try:
                    result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    static_counts[table] = count
                    print(f"   ✓ {table}: {count} registros")
                except Exception as e:
                    print(f"   ⚠️  {table}: Error al contar - {e}")
        
        print()
        print("=" * 70)
        print("  ✅ RESET COMPLETADO")
        print("=" * 70)
        print()
        print("📋 Próximos pasos recomendados:")
        print("   1. Verificar que los datos estáticos estén completos:")
        print("      - python tools/seed_permissions.py")
        print("      - python tools/seed_subscription_plans.py")
        print("      - python tools/seed_catalogs.py")
        print()
        print("   2. Crear usuarios de prueba (super admin):")
        print("      - python tools/create_test_users.py")
        print()
        print("   3. Crear el primer workspace B2B desde la UI o API")
        print()
        
        # Commit
        session.commit()
        print("✅ Cambios guardados en la base de datos")


if __name__ == "__main__":
    reset_database()
