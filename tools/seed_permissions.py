"""
Script para crear roles y permisos predefinidos en la base de datos.

Este script crea:
- Permisos base (documents.*, workspaces.*, users.*)
- Roles predefinidos (owner, admin, approver, creator, viewer)
- Asignaciones de permisos a roles
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Role, Permission, RolePermission
from process_ai_core.db.permissions import (
    create_role,
    create_permission,
    assign_permission_to_role,
)


def seed_permissions():
    """Crea todos los permisos predefinidos."""
    with get_db_session() as session:
        # Verificar si ya existen permisos
        existing_permissions = session.query(Permission).count()
        if existing_permissions > 0:
            print("⚠️  Ya existen permisos en la base de datos. ¿Deseas continuar? (s/n): ", end="")
            response = input().strip().lower()
            if response != "s":
                print("❌ Cancelado.")
                return
        
        print("🌱 Creando permisos predefinidos...")
        
        # ============================================================
        # Permisos de Documentos
        # ============================================================
        perm_docs_create = create_permission(
            session=session,
            name="documents.create",
            description="Crear nuevos documentos",
            category="documents",
        )
        
        perm_docs_view = create_permission(
            session=session,
            name="documents.view",
            description="Ver documentos",
            category="documents",
        )
        
        perm_docs_edit = create_permission(
            session=session,
            name="documents.edit",
            description="Editar documentos",
            category="documents",
        )
        
        perm_docs_delete = create_permission(
            session=session,
            name="documents.delete",
            description="Eliminar documentos",
            category="documents",
        )
        
        perm_docs_approve = create_permission(
            session=session,
            name="documents.approve",
            description="Aprobar documentos",
            category="documents",
        )
        
        perm_docs_reject = create_permission(
            session=session,
            name="documents.reject",
            description="Rechazar documentos con observaciones",
            category="documents",
        )
        
        perm_docs_export = create_permission(
            session=session,
            name="documents.export",
            description="Exportar documentos (PDF, etc.)",
            category="documents",
        )
        
        # ============================================================
        # Permisos de Workspaces
        # ============================================================
        perm_ws_view = create_permission(
            session=session,
            name="workspaces.view",
            description="Ver workspace",
            category="workspaces",
        )
        
        perm_ws_edit = create_permission(
            session=session,
            name="workspaces.edit",
            description="Editar configuración del workspace",
            category="workspaces",
        )
        
        perm_ws_manage_users = create_permission(
            session=session,
            name="workspaces.manage_users",
            description="Gestionar usuarios del workspace",
            category="workspaces",
        )
        
        perm_ws_manage_folders = create_permission(
            session=session,
            name="workspaces.manage_folders",
            description="Gestionar estructura de carpetas",
            category="workspaces",
        )
        
        # ============================================================
        # Permisos de Usuarios
        # ============================================================
        perm_users_view = create_permission(
            session=session,
            name="users.view",
            description="Ver usuarios",
            category="users",
        )
        
        perm_users_manage = create_permission(
            session=session,
            name="users.manage",
            description="Crear/editar usuarios",
            category="users",
        )
        
        session.flush()
        print("✅ Permisos creados.")
        
        # ============================================================
        # Roles para Workspaces de tipo "organization"
        # ============================================================
        print("🌱 Creando roles predefinidos...")
        
        # Owner: todos los permisos
        role_owner = create_role(
            session=session,
            name="owner",
            description="Dueño del workspace. Tiene todos los permisos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Admin: gestión y aprobación
        role_admin = create_role(
            session=session,
            name="admin",
            description="Administrador. Puede gestionar usuarios, aprobar documentos y crear documentos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Approver: aprobar/rechazar documentos
        role_approver = create_role(
            session=session,
            name="approver",
            description="Aprobador. Puede aprobar y rechazar documentos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Creator: crear y editar documentos
        role_creator = create_role(
            session=session,
            name="creator",
            description="Creador. Puede crear y editar documentos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Viewer: solo ver documentos aprobados
        role_viewer = create_role(
            session=session,
            name="viewer",
            description="Visualizador. Solo puede ver documentos aprobados.",
            workspace_type="organization",
            is_system=True,
        )
        
        session.flush()
        print("✅ Roles creados.")
        
        # ============================================================
        # Asignar Permisos a Roles
        # ============================================================
        print("🌱 Asignando permisos a roles...")
        
        # Owner: todos los permisos
        for perm in [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_delete,
            perm_docs_approve, perm_docs_reject, perm_docs_export,
            perm_ws_view, perm_ws_edit, perm_ws_manage_users, perm_ws_manage_folders,
            perm_users_view, perm_users_manage,
        ]:
            assign_permission_to_role(session, role_owner.id, perm.id)
        
        # Admin: gestión y aprobación
        for perm in [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_approve,
            perm_docs_reject, perm_docs_export,
            perm_ws_view, perm_ws_edit, perm_ws_manage_users, perm_ws_manage_folders,
            perm_users_view, perm_users_manage,
        ]:
            assign_permission_to_role(session, role_admin.id, perm.id)
        
        # Approver: aprobar/rechazar y ver
        for perm in [
            perm_docs_view, perm_docs_approve, perm_docs_reject, perm_docs_export,
            perm_ws_view,
        ]:
            assign_permission_to_role(session, role_approver.id, perm.id)
        
        # Creator: crear, editar y ver
        for perm in [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_export,
            perm_ws_view, perm_ws_manage_folders,
        ]:
            assign_permission_to_role(session, role_creator.id, perm.id)
        
        # Viewer: solo ver
        for perm in [
            perm_docs_view, perm_docs_export,
            perm_ws_view,
        ]:
            assign_permission_to_role(session, role_viewer.id, perm.id)
        
        session.flush()
        print("✅ Permisos asignados a roles.")
        
        # Commit final
        session.commit()
        print("✅ Seed completado exitosamente!")
        
        # Resumen
        print("\n📊 Resumen:")
        print(f"  - Permisos creados: {session.query(Permission).count()}")
        print(f"  - Roles creados: {session.query(Role).count()}")
        print(f"  - Asignaciones: {session.query(RolePermission).count()}")


if __name__ == "__main__":
    seed_permissions()



