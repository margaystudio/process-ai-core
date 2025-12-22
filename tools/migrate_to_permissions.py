"""
Script de migración para actualizar WorkspaceMembership a usar role_id.

Este script:
1. Crea las tablas roles, permissions, role_permissions si no existen
2. Ejecuta el seed de permisos si no existen roles
3. Migra WorkspaceMembership.role (string) a WorkspaceMembership.role_id (FK)
4. Mapea roles antiguos a nuevos roles:
   - "owner" -> role "owner"
   - "admin" -> role "admin"
   - "member" -> role "creator" (asumimos que "member" puede crear)
   - "viewer" -> role "viewer"
   - "approver" -> role "approver" (si existe)
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from process_ai_core.db.database import get_db_engine, Base, get_db_session
# Importar todos los modelos para que SQLAlchemy los registre
from process_ai_core.db.models import (
    Role, Permission, RolePermission, WorkspaceMembership,
    User, Workspace, Document, Process, Recipe, Folder,
    Run, Artifact, Validation, AuditLog, DocumentVersion,
)


def create_tables_if_not_exist():
    """Crea las tablas de roles y permisos si no existen."""
    engine = get_db_engine()
    inspector = inspect(engine)
    
    tables_to_create = ["roles", "permissions", "role_permissions"]
    existing_tables = inspector.get_table_names()
    
    missing_tables = [t for t in tables_to_create if t not in existing_tables]
    
    if missing_tables:
        print(f"📦 Creando tablas faltantes: {', '.join(missing_tables)}")
        # Crear solo las tablas de roles y permisos
        Base.metadata.create_all(engine, tables=[
            Role.__table__,
            Permission.__table__,
            RolePermission.__table__,
        ])
        print("✅ Tablas creadas.")
    else:
        print("✅ Todas las tablas ya existen.")
    
    # Agregar columna role_id a workspace_memberships si no existe
    if "workspace_memberships" in existing_tables:
        columns = [col["name"] for col in inspector.get_columns("workspace_memberships")]
        if "role_id" not in columns:
            print("📦 Agregando columna role_id a workspace_memberships...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE workspace_memberships ADD COLUMN role_id VARCHAR(36)"))
                conn.commit()
            print("✅ Columna role_id agregada.")
        else:
            print("✅ Columna role_id ya existe en workspace_memberships.")


def migrate_workspace_memberships():
    """Migra WorkspaceMembership.role (string) a WorkspaceMembership.role_id (FK)."""
    with get_db_session() as session:
        # Verificar si hay roles en la base de datos
        roles_count = session.query(Role).count()
        if roles_count == 0:
            print("⚠️  No hay roles en la base de datos. Ejecutando seed...")
            from tools.seed_permissions import seed_permissions
            seed_permissions()
            print("✅ Seed completado.")
        
        # Mapeo de roles antiguos a nuevos
        role_mapping = {
            "owner": "owner",
            "admin": "admin",
            "member": "creator",  # Asumimos que "member" puede crear
            "viewer": "viewer",
            "approver": "approver",
        }
        
        # Obtener todos los memberships que aún tienen role como string
        memberships = session.query(WorkspaceMembership).filter(
            WorkspaceMembership.role_id.is_(None)
        ).all()
        
        if not memberships:
            print("✅ No hay memberships para migrar.")
            return
        
        print(f"🔄 Migrando {len(memberships)} memberships...")
        
        migrated = 0
        skipped = 0
        errors = []
        
        for membership in memberships:
            old_role = membership.role
            
            if not old_role:
                print(f"⚠️  Membership {membership.id} no tiene rol asignado. Saltando...")
                skipped += 1
                continue
            
            # Buscar el rol correspondiente
            new_role_name = role_mapping.get(old_role)
            if not new_role_name:
                error_msg = f"⚠️  Rol '{old_role}' no tiene mapeo. Saltando membership {membership.id}."
                print(error_msg)
                errors.append(error_msg)
                skipped += 1
                continue
            
            # Buscar el rol en la base de datos
            role = session.query(Role).filter_by(name=new_role_name).first()
            if not role:
                error_msg = f"⚠️  Rol '{new_role_name}' no encontrado en la base de datos. Saltando membership {membership.id}."
                print(error_msg)
                errors.append(error_msg)
                skipped += 1
                continue
            
            # Asignar role_id
            membership.role_id = role.id
            migrated += 1
        
        session.commit()
        
        print(f"\n✅ Migración completada:")
        print(f"  - Migrados: {migrated}")
        print(f"  - Saltados: {skipped}")
        if errors:
            print(f"  - Errores: {len(errors)}")
            for error in errors:
                print(f"    {error}")


def verify_migration():
    """Verifica que la migración se completó correctamente."""
    with get_db_session() as session:
        # Contar memberships con role_id
        with_role_id = session.query(WorkspaceMembership).filter(
            WorkspaceMembership.role_id.isnot(None)
        ).count()
        
        # Contar memberships con role como string (sin role_id)
        with_role_string = session.query(WorkspaceMembership).filter(
            WorkspaceMembership.role_id.is_(None),
            WorkspaceMembership.role.isnot(None),
        ).count()
        
        total = session.query(WorkspaceMembership).count()
        
        print(f"\n📊 Verificación:")
        print(f"  - Total memberships: {total}")
        print(f"  - Con role_id: {with_role_id}")
        print(f"  - Solo con role (string): {with_role_string}")
        
        if with_role_string > 0:
            print(f"⚠️  Aún hay {with_role_string} memberships sin migrar.")
        else:
            print("✅ Todos los memberships tienen role_id asignado.")


if __name__ == "__main__":
    print("🚀 Iniciando migración a modelo de permisos...")
    print("=" * 60)
    
    # Paso 1: Crear tablas si no existen
    print("\n1️⃣  Creando tablas...")
    create_tables_if_not_exist()
    
    # Paso 2: Migrar memberships
    print("\n2️⃣  Migrando workspace memberships...")
    migrate_workspace_memberships()
    
    # Paso 3: Verificar
    print("\n3️⃣  Verificando migración...")
    verify_migration()
    
    print("\n" + "=" * 60)
    print("✅ Migración completada!")

