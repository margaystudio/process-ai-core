"""
Script para crear usuarios de prueba con diferentes roles.

Este script crea usuarios de ejemplo y los asigna a un workspace con diferentes roles
para facilitar las pruebas de la UI.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User, Workspace, WorkspaceMembership, Role


def create_test_users():
    """Crea usuarios de prueba con diferentes roles."""
    with get_db_session() as session:
        # Verificar que hay roles en la base de datos
        roles_count = session.query(Role).count()
        if roles_count == 0:
            print("⚠️  No hay roles en la base de datos. Ejecutando seed de permisos...")
            from tools.seed_permissions import seed_permissions
            seed_permissions()
            print("✅ Seed completado.")

        # Obtener workspace "margay" (o el primero disponible)
        workspace = session.query(Workspace).filter_by(slug="margay").first()
        if not workspace:
            workspace = session.query(Workspace).filter_by(workspace_type="organization").first()
        
        if not workspace:
            print("⚠️  No hay workspaces en la base de datos.")
            print("   Por favor, crea un workspace primero desde la UI o usando:")
            print("   POST /api/v1/workspaces")
            return

        print(f"📦 Usando workspace: {workspace.name} (slug: {workspace.slug}, ID: {workspace.id})")

        # Obtener roles
        role_owner = session.query(Role).filter_by(name="owner").first()
        role_admin = session.query(Role).filter_by(name="admin").first()
        role_approver = session.query(Role).filter_by(name="approver").first()
        role_creator = session.query(Role).filter_by(name="creator").first()
        role_viewer = session.query(Role).filter_by(name="viewer").first()

        if not all([role_owner, role_admin, role_approver, role_creator, role_viewer]):
            print("❌ Faltan roles en la base de datos. Ejecuta tools/seed_permissions.py primero.")
            return

        # Usuarios de prueba
        test_users = [
            {
                "email": "owner@test.com",
                "name": "Usuario Owner",
                "role": role_owner,
            },
            {
                "email": "admin@test.com",
                "name": "Usuario Admin",
                "role": role_admin,
            },
            {
                "email": "approver@test.com",
                "name": "Usuario Aprobador",
                "role": role_approver,
            },
            {
                "email": "creator@test.com",
                "name": "Usuario Creador",
                "role": role_creator,
            },
            {
                "email": "viewer@test.com",
                "name": "Usuario Viewer",
                "role": role_viewer,
            },
        ]

        print("\n🌱 Creando usuarios de prueba...")
        created_users = []

        for user_data in test_users:
            # Verificar si el usuario ya existe
            existing_user = session.query(User).filter_by(email=user_data["email"]).first()
            
            if existing_user:
                user = existing_user
                print(f"  ⚠️  Usuario {user_data['email']} ya existe, actualizando...")
            else:
                user = User(
                    email=user_data["email"],
                    name=user_data["name"],
                )
                session.add(user)
                session.flush()
                print(f"  ✅ Creado usuario: {user_data['email']}")

            # Verificar o crear membership
            membership = session.query(WorkspaceMembership).filter_by(
                user_id=user.id,
                workspace_id=workspace.id,
            ).first()

            if membership:
                # Actualizar rol
                membership.role_id = user_data["role"].id
                membership.role = user_data["role"].name  # Deprecated, pero mantener para compatibilidad
                print(f"  🔄 Actualizado rol de {user_data['email']} a {user_data['role'].name}")
            else:
                # Crear membership
                membership = WorkspaceMembership(
                    user_id=user.id,
                    workspace_id=workspace.id,
                    role_id=user_data["role"].id,
                    role=user_data["role"].name,  # Deprecated, pero mantener para compatibilidad
                )
                session.add(membership)
                print(f"  ✅ Asignado rol {user_data['role'].name} a {user_data['email']}")

            created_users.append({
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user_data["role"].name,
            })

        session.commit()

        print("\n✅ Usuarios de prueba creados exitosamente!")
        print("\n📋 Resumen de usuarios:")
        print("=" * 60)
        for user in created_users:
            print(f"  Email: {user['email']}")
            print(f"  Nombre: {user['name']}")
            print(f"  Rol: {user['role']}")
            print(f"  ID: {user['id']}")
            print()

        print("💡 Para usar estos usuarios en la UI:")
        print("   1. Abre la consola del navegador (F12)")
        print("   2. Ejecuta: localStorage.setItem('userId', 'USER_ID_AQUI')")
        print("   3. Recarga la página")
        print("\n   Ejemplo:")
        print(f"   localStorage.setItem('userId', '{created_users[0]['id']}')")
        print("\n📝 Usuarios disponibles:")
        for user in created_users:
            print(f"   - {user['email']} ({user['role']}): {user['id']}")


if __name__ == "__main__":
    create_test_users()

