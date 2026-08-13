"""
Script para crear usuarios de prueba con los accesos del modelo vigente.

Crea en el primer workspace (o el de slug "margay"):
  - admin@test.com    → base_access 'admin'   (gestión total)
  - member@test.com   → base_access 'member'  (edición en carpetas sin restricción)
  - aprobador@test.com→ base_access 'member' + rol operativo "Gerencia" (aprobación)
  - external@test.com → base_access 'external' (solo lectura)

Los roles de sistema (owner/admin/approver/creator/viewer) se eliminaron en la
fase 3 del rediseño de permisos; ver process_ai_core/db/permissions.py.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    OperationalRole,
    User,
    UserOperationalRole,
    Workspace,
    WorkspaceMembership,
)


def create_test_users():
    """Crea usuarios de prueba con los tres accesos base + un rol operativo."""
    with get_db_session() as session:
        workspace = session.query(Workspace).filter_by(slug="margay").first()
        if not workspace:
            workspace = (
                session.query(Workspace).filter_by(workspace_type="organization").first()
            )
        if not workspace:
            print("⚠️  No hay workspaces en la base de datos.")
            print("   Ingresá con un usuario del tenant para que el sync lo cree.")
            return

        print(f"📦 Usando workspace: {workspace.name} (slug: {workspace.slug}, ID: {workspace.id})")

        gerencia = (
            session.query(OperationalRole)
            .filter_by(workspace_id=workspace.id, slug="gerencia")
            .first()
        )
        if not gerencia:
            gerencia = OperationalRole(
                id=str(uuid.uuid4()),
                workspace_id=workspace.id,
                name="Gerencia",
                slug="gerencia",
                access_level="aprobacion",
            )
            session.add(gerencia)
            session.flush()
            print("  ✅ Rol operativo 'Gerencia' (aprobación) creado")

        test_users = [
            {"email": "admin@test.com", "name": "Usuario Admin", "base": "admin", "ops": []},
            {"email": "member@test.com", "name": "Usuario Miembro", "base": "member", "ops": []},
            {"email": "aprobador@test.com", "name": "Usuario Aprobador", "base": "member", "ops": [gerencia]},
            {"email": "external@test.com", "name": "Cliente Externo", "base": "external", "ops": []},
        ]

        print("\n🌱 Creando usuarios de prueba...")
        for data in test_users:
            user = session.query(User).filter_by(email=data["email"]).first()
            if user:
                print(f"  ⚠️  Usuario {data['email']} ya existe, actualizando...")
            else:
                user = User(email=data["email"], name=data["name"])
                session.add(user)
                session.flush()
                print(f"  ✅ Creado usuario: {data['email']}")

            membership = session.query(WorkspaceMembership).filter_by(
                user_id=user.id, workspace_id=workspace.id
            ).first()
            if membership:
                membership.base_access = data["base"]
            else:
                membership = WorkspaceMembership(
                    user_id=user.id,
                    workspace_id=workspace.id,
                    base_access=data["base"],
                )
                session.add(membership)
                session.flush()

            for op in data["ops"]:
                existing = session.query(UserOperationalRole).filter_by(
                    workspace_membership_id=membership.id, operational_role_id=op.id
                ).first()
                if not existing:
                    session.add(
                        UserOperationalRole(
                            id=str(uuid.uuid4()),
                            workspace_membership_id=membership.id,
                            operational_role_id=op.id,
                        )
                    )
            print(f"     → base_access={data['base']}"
                  + (f" + roles: {[o.name for o in data['ops']]}" if data["ops"] else ""))

        session.commit()
        print("\n✅ Listo.")


if __name__ == "__main__":
    create_test_users()
