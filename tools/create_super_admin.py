#!/usr/bin/env python3
"""
Script para crear un usuario super admin.

Por defecto crea sdalto@margaystudio.io. Puede agregar otros super admins
pasando email y nombre como argumentos.

Ejecutar:
    python tools/create_super_admin.py
    python tools/create_super_admin.py ignacioazaso@gmail.com "Ignacio Azareto"
"""

import sys
import uuid
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User, Role, Workspace, WorkspaceMembership

# Super admins por defecto (se pueden agregar más con args)
DEFAULT_SUPERADMINS = [
    ("sdalto@margaystudio.io", "Santiago Dalto"),
    ("ignacioazaso@gmail.com", "Ignacio Azareto"),
]


def create_super_admin(email: str | None = None, name: str | None = None):
    """Crea o actualiza un usuario super admin.
    Si no se pasan email/name, crea todos los de DEFAULT_SUPERADMINS."""
    with get_db_session() as session:
        users_to_create = []
        if email and name:
            users_to_create = [(email, name)]
        else:
            users_to_create = DEFAULT_SUPERADMINS

        for email, name in users_to_create:
            _create_one_super_admin(session, email, name)


def _create_one_super_admin(session, email: str, name: str):
    """Crea un solo super admin."""
    print("=" * 70)
    print("  CREAR USUARIO SUPER ADMIN")
    print("=" * 70)
    print("  📧 Email:", email)
    print("  👤 Nombre:", name)
    print()
    
    # Verificar que hay roles en la base de datos
    roles_count = session.query(Role).count()
    if roles_count == 0:
        print("⚠️  No hay roles en la base de datos.")
        print("   Ejecutando seed de permisos...")
        from tools.seed_permissions import seed_permissions
        seed_permissions()
        session.expire_all()  # Refrescar para ver los roles recién creados
        print("✅ Seed completado.")
        print()
    
    # Obtener rol "superadmin" (debe ser creado por seed_permissions.py)
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        print("❌ Rol 'superadmin' no encontrado.")
        print("   Ejecuta tools/seed_permissions.py primero para crear el rol con todos los permisos.")
        return
    
    # Obtener o crear workspace "sistema" para superadmins
    system_workspace = session.query(Workspace).filter_by(slug="sistema").first()
    if not system_workspace:
        print("⚠️  Workspace 'sistema' no encontrado. Creándolo...")
        system_workspace = Workspace(
            slug="sistema",
            name="Sistema",
            workspace_type="system",
            description="Workspace del sistema para superadmins",
            country=None,
            business_type=None,
            language_style=None,
            default_audience=None,
            default_detail_level=None,
            context_text=None,
            metadata_json="{}"
        )
        session.add(system_workspace)
        session.flush()
        print("✅ Workspace 'sistema' creado.")
    
    # Verificar si el usuario ya existe
    existing_user = session.query(User).filter_by(email=email).first()
    
    if existing_user:
        print(f"⚠️  Usuario {email} ya existe.")
        print(f"   ID: {existing_user.id}")
        print(f"   Nombre: {existing_user.name}")
        print(f"   Auth Provider: {existing_user.auth_provider or 'local'}")
        print(f"   External ID (Supabase): {existing_user.external_id or '(no vinculado)'}")
        print()
        
        response = input("¿Deseas actualizar el usuario? (s/n): ").strip().lower()
        if response != "s":
            print("❌ Cancelado.")
            return
        
        user = existing_user
        user.name = name
        print(f"✅ Usuario actualizado: {email}")
    else:
        # Crear nuevo usuario
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            auth_provider="local",
            external_id=None,
        )
        session.add(user)
        session.flush()
        print(f"✅ Usuario creado: {email}")
        print(f"   ID: {user.id}")
    
    # Asignar usuario al workspace "sistema" con rol "superadmin"
    existing_membership = session.query(WorkspaceMembership).filter_by(
        user_id=user.id,
        workspace_id=system_workspace.id,
    ).first()
    
    if existing_membership:
        existing_membership.role_id = superadmin_role.id
        existing_membership.role = "superadmin"
        print("✅ Rol 'superadmin' actualizado en workspace 'sistema'")
    else:
        membership = WorkspaceMembership(
            user_id=user.id,
            workspace_id=system_workspace.id,
            role_id=superadmin_role.id,
            role="superadmin",
        )
        session.add(membership)
        print("✅ Usuario asignado como 'superadmin' en workspace 'sistema'")
    
    session.commit()
    
    print()
    print("=" * 70)
    print("  ✅ USUARIO CREADO/ACTUALIZADO")
    print("=" * 70)
    print()
    print(f"📧 Email: {user.email}")
    print(f"👤 Nombre: {user.name}")
    print(f"🆔 ID Local: {user.id}")
    print(f"🔗 External ID (Supabase): {user.external_id or '(no vinculado aún)'}")
    print("👑 Rol: superadmin (en workspace 'sistema')")
    print()
    print("📋 PRÓXIMOS PASOS PARA VINCULAR CON SUPABASE:")
    print()
    print("OPCIÓN 1: Vinculación automática (recomendado)")
    print("  Cuando el usuario se autentique en Supabase por primera vez,")
    print("  el sistema lo vinculará automáticamente mediante el endpoint")
    print("  POST /api/v1/auth/sync-user")
    print()
    print("  Pasos:")
    print("  1. Crear el usuario en Supabase Auth (Dashboard o API)")
    print("  2. El usuario inicia sesión en la UI")
    print("  3. El callback de auth llama a sync-user con el supabase_user_id")
    print("  4. El sistema vincula automáticamente por email o crea el usuario")
    print()
    print("OPCIÓN 2: Vinculación manual")
    print("  Si ya tienes el usuario en Supabase, puedes vincularlo manualmente:")
    print()
    print("  1. Obtener el Supabase User ID (sub del JWT):")
    print("     - Desde el Dashboard de Supabase: Users > [usuario] > UUID")
    print("     - O desde el JWT después de login: data.user.id")
    print()
    print("  2. Ejecutar este script de vinculación:")
    print("     python tools/link_user_to_supabase.py")
    print()
    print("  3. O actualizar manualmente en la BD:")
    print(f"     UPDATE users SET external_id='<SUPABASE_USER_ID>' WHERE email='{email}';")
    print()
    print("💡 NOTA: El usuario ya está asignado como 'superadmin' en el workspace 'sistema'.")
    print("   Puede crear workspaces B2B y gestionar todo el sistema.")
    print()
    print("📖 Para más información:")
    print("   - Vinculación con Supabase: docs/SUPABASE_USER_LINKING.md")
    print("   - Rol de superadmin: docs/SUPERADMIN_ROLE.md")
    print()


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        # email y nombre como argumentos
        create_super_admin(email=sys.argv[1], name=sys.argv[2])
    else:
        # por defecto: crea todos los de DEFAULT_SUPERADMINS
        create_super_admin()
