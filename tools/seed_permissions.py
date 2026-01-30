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
    """Crea todos los permisos predefinidos (idempotente)."""
    with get_db_session() as session:
        # Verificar si ya existen permisos
        existing_permissions = session.query(Permission).count()
        if existing_permissions > 0:
            print(f"ℹ️  Ya existen {existing_permissions} permisos en la base de datos.")
            print("   El script actualizará/creará los permisos y roles necesarios (idempotente).")
            print()
        
        print("🌱 Creando/actualizando permisos predefinidos...")
        
        # Helper para obtener o crear permiso
        def get_or_create_permission(name, description, category):
            existing = session.query(Permission).filter_by(name=name).first()
            if existing:
                # Actualizar descripción si cambió
                if existing.description != description:
                    existing.description = description
                if existing.category != category:
                    existing.category = category
                return existing
            return create_permission(session, name, description, category)
        
        # Helper para obtener o crear rol
        def get_or_create_role(name, description, workspace_type, is_system):
            existing = session.query(Role).filter_by(name=name).first()
            if existing:
                # Actualizar si cambió
                if existing.description != description:
                    existing.description = description
                if existing.workspace_type != workspace_type:
                    existing.workspace_type = workspace_type
                if existing.is_system != is_system:
                    existing.is_system = is_system
                return existing
            return create_role(session, name, description, workspace_type, is_system)
        
        # ============================================================
        # Permisos de Documentos
        # ============================================================
        perm_docs_create = get_or_create_permission(
            name="documents.create",
            description="Crear nuevos documentos",
            category="documents",
        )
        
        perm_docs_view = get_or_create_permission(
            name="documents.view",
            description="Ver documentos",
            category="documents",
        )
        
        perm_docs_edit = get_or_create_permission(
            name="documents.edit",
            description="Editar documentos",
            category="documents",
        )
        
        perm_docs_delete = get_or_create_permission(
            name="documents.delete",
            description="Eliminar documentos",
            category="documents",
        )
        
        perm_docs_approve = get_or_create_permission(
            name="documents.approve",
            description="Aprobar documentos",
            category="documents",
        )
        
        perm_docs_reject = get_or_create_permission(
            name="documents.reject",
            description="Rechazar documentos con observaciones",
            category="documents",
        )
        
        perm_docs_export = get_or_create_permission(
            name="documents.export",
            description="Exportar documentos (PDF, etc.)",
            category="documents",
        )
        
        # ============================================================
        # Permisos de Workspaces
        # ============================================================
        perm_ws_view = get_or_create_permission(
            name="workspaces.view",
            description="Ver workspace",
            category="workspaces",
        )
        
        perm_ws_edit = get_or_create_permission(
            name="workspaces.edit",
            description="Editar configuración del workspace",
            category="workspaces",
        )
        
        perm_ws_manage_users = get_or_create_permission(
            name="workspaces.manage_users",
            description="Gestionar usuarios del workspace",
            category="workspaces",
        )
        
        perm_ws_manage_folders = get_or_create_permission(
            name="workspaces.manage_folders",
            description="Gestionar estructura de carpetas",
            category="workspaces",
        )
        
        # ============================================================
        # Permisos de Usuarios
        # ============================================================
        perm_users_view = get_or_create_permission(
            name="users.view",
            description="Ver usuarios",
            category="users",
        )
        
        perm_users_manage = get_or_create_permission(
            name="users.manage",
            description="Crear/editar usuarios",
            category="users",
        )
        
        session.flush()
        print("✅ Permisos creados.")
        
        # ============================================================
        # Roles para Workspaces de tipo "organization"
        # ============================================================
        print("🌱 Creando/actualizando roles predefinidos...")
        
        # Owner: todos los permisos
        role_owner = get_or_create_role(
            name="owner",
            description="Dueño del workspace. Tiene todos los permisos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Admin: gestión y aprobación
        role_admin = get_or_create_role(
            name="admin",
            description="Administrador. Puede gestionar usuarios, aprobar documentos y crear documentos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Approver: aprobar/rechazar documentos
        role_approver = get_or_create_role(
            name="approver",
            description="Aprobador. Puede aprobar y rechazar documentos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Creator: crear y editar documentos
        role_creator = get_or_create_role(
            name="creator",
            description="Creador. Puede crear y editar documentos.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Viewer: solo ver documentos aprobados
        role_viewer = get_or_create_role(
            name="viewer",
            description="Visualizador. Solo puede ver documentos aprobados.",
            workspace_type="organization",
            is_system=True,
        )
        
        # Superadmin: todos los permisos del sistema (global, no específico de workspace)
        role_superadmin = get_or_create_role(
            name="superadmin",
            description="Super administrador del sistema. Puede crear workspaces B2B y gestionar todo.",
            workspace_type=None,  # Global, no específico de workspace
            is_system=True,
        )
        
        session.flush()
        print("✅ Roles creados.")
        
        # ============================================================
        # Asignar Permisos a Roles
        # ============================================================
        print("🌱 Asignando permisos a roles...")
        
        # Helper para asignar permiso si no existe
        def ensure_permission_assigned(role_id, permission_id):
            existing = session.query(RolePermission).filter_by(
                role_id=role_id,
                permission_id=permission_id
            ).first()
            if not existing:
                assign_permission_to_role(session, role_id, permission_id)
        
        # Owner: todos los permisos
        for perm in [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_delete,
            perm_docs_approve, perm_docs_reject, perm_docs_export,
            perm_ws_view, perm_ws_edit, perm_ws_manage_users, perm_ws_manage_folders,
            perm_users_view, perm_users_manage,
        ]:
            ensure_permission_assigned(role_owner.id, perm.id)
        
        # Admin: gestión y aprobación
        for perm in [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_approve,
            perm_docs_reject, perm_docs_export,
            perm_ws_view, perm_ws_edit, perm_ws_manage_users, perm_ws_manage_folders,
            perm_users_view, perm_users_manage,
        ]:
            ensure_permission_assigned(role_admin.id, perm.id)
        
        # Approver: aprobar/rechazar y ver
        for perm in [
            perm_docs_view, perm_docs_approve, perm_docs_reject, perm_docs_export,
            perm_ws_view,
        ]:
            ensure_permission_assigned(role_approver.id, perm.id)
        
        # Creator: crear, editar y ver
        for perm in [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_export,
            perm_ws_view, perm_ws_manage_folders,
        ]:
            ensure_permission_assigned(role_creator.id, perm.id)
        
        # Viewer: solo ver
        for perm in [
            perm_docs_view, perm_docs_export,
            perm_ws_view,
        ]:
            ensure_permission_assigned(role_viewer.id, perm.id)
        
        # Superadmin: TODOS los permisos (acceso completo al sistema)
        all_permissions = [
            perm_docs_create, perm_docs_view, perm_docs_edit, perm_docs_delete,
            perm_docs_approve, perm_docs_reject, perm_docs_export,
            perm_ws_view, perm_ws_edit, perm_ws_manage_users, perm_ws_manage_folders,
            perm_users_view, perm_users_manage,
        ]
        for perm in all_permissions:
            ensure_permission_assigned(role_superadmin.id, perm.id)
        
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
        print("\n💡 Roles creados:")
        print("  - superadmin: Super administrador del sistema (todos los permisos)")
        print("  - owner: Dueño del workspace (todos los permisos)")
        print("  - admin: Administrador (gestión y aprobación)")
        print("  - approver: Aprobador (aprobar/rechazar documentos)")
        print("  - creator: Creador (crear y editar documentos)")
        print("  - viewer: Visualizador (solo lectura)")


if __name__ == "__main__":
    seed_permissions()



