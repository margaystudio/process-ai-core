"""
Helpers para gestión de permisos y roles.

Este módulo proporciona funciones para:
- Verificar permisos de usuarios
- Crear roles y permisos predefinidos
- Gestionar asignaciones de permisos a roles
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    Role, Permission, RolePermission, WorkspaceMembership, User,
    Folder, OperationalRole, UserOperationalRole, FolderPermission,
)
from .helpers import get_folder_by_id


def has_permission(
    session: Session,
    user_id: str,
    workspace_id: str,
    permission_name: str,
) -> bool:
    """
    Verifica si un usuario tiene un permiso específico en un workspace.
    
    Los superadmins tienen todos los permisos automáticamente.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
        permission_name: Nombre del permiso (ej: "documents.approve")
    
    Returns:
        True si el usuario tiene el permiso, False en caso contrario
    """
    # Verificar si el usuario es superadmin (tiene rol superadmin en algún workspace)
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if superadmin_role:
        superadmin_membership = session.query(WorkspaceMembership).filter_by(
            user_id=user_id,
            role_id=superadmin_role.id,
        ).first()
        if superadmin_membership:
            # Superadmin tiene todos los permisos
            return True
    
    # Obtener membership en el workspace específico
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    
    if not membership:
        return False
    
    # Obtener rol (usar role_id si existe, sino role como string para compatibilidad)
    if membership.role_id:
        role = session.query(Role).filter_by(id=membership.role_id).first()
        if not role:
            return False
    else:
        # Compatibilidad: buscar rol por nombre si role_id no existe
        role = session.query(Role).filter_by(name=membership.role).first()
        if not role:
            return False
    
    # Verificar si el rol tiene el permiso
    return any(p.name == permission_name for p in role.permissions)


def get_user_permissions(
    session: Session,
    user_id: str,
    workspace_id: str,
) -> list[str]:
    """
    Obtiene todos los permisos de un usuario en un workspace.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
    
    Returns:
        Lista de nombres de permisos
    """
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    
    if not membership:
        return []
    
    # Obtener rol
    if membership.role_id:
        role = session.query(Role).filter_by(id=membership.role_id).first()
    else:
        # Compatibilidad: buscar rol por nombre
        role = session.query(Role).filter_by(name=membership.role).first()
    
    if not role:
        return []
    
    return [p.name for p in role.permissions]


def get_user_role(
    session: Session,
    user_id: str,
    workspace_id: str,
) -> Role | None:
    """
    Obtiene el rol de un usuario en un workspace.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
    
    Returns:
        Role o None si no tiene rol
    """
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    
    if not membership:
        return None
    
    # Obtener rol
    if membership.role_id:
        return session.query(Role).filter_by(id=membership.role_id).first()
    else:
        # Compatibilidad: buscar rol por nombre
        return session.query(Role).filter_by(name=membership.role).first()


def can_approve_documents(
    session: Session,
    user_id: str,
    workspace_id: str,
) -> bool:
    """
    Verifica si un usuario puede aprobar documentos en un workspace.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
    
    Returns:
        True si puede aprobar, False en caso contrario
    """
    return has_permission(session, user_id, workspace_id, "documents.approve")


def can_create_documents(
    session: Session,
    user_id: str,
    workspace_id: str,
) -> bool:
    """
    Verifica si un usuario puede crear documentos en un workspace.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
    
    Returns:
        True si puede crear, False en caso contrario
    """
    return has_permission(session, user_id, workspace_id, "documents.create")


def create_role(
    session: Session,
    name: str,
    description: str = "",
    workspace_type: str | None = None,
    is_system: bool = False,
) -> Role:
    """
    Crea un nuevo rol.
    
    Args:
        session: Sesión de base de datos
        name: Nombre del rol
        description: Descripción del rol
        workspace_type: Tipo de workspace donde aplica
        is_system: Si es un rol del sistema
    
    Returns:
        Role creado
    """
    role = Role(
        name=name,
        description=description,
        workspace_type=workspace_type,
        is_system=is_system,
    )
    session.add(role)
    return role


def create_permission(
    session: Session,
    name: str,
    description: str = "",
    category: str = "",
) -> Permission:
    """
    Crea un nuevo permiso.
    
    Args:
        session: Sesión de base de datos
        name: Nombre del permiso
        description: Descripción del permiso
        category: Categoría del permiso
    
    Returns:
        Permission creado
    """
    permission = Permission(
        name=name,
        description=description,
        category=category,
    )
    session.add(permission)
    return permission


def assign_permission_to_role(
    session: Session,
    role_id: str,
    permission_id: str,
) -> RolePermission:
    """
    Asigna un permiso a un rol.
    
    Args:
        session: Sesión de base de datos
        role_id: ID del rol
        permission_id: ID del permiso
    
    Returns:
        RolePermission creado
    """
    role_permission = RolePermission(
        role_id=role_id,
        permission_id=permission_id,
    )
    session.add(role_permission)
    return role_permission


# --- Roles operativos y permisos por carpeta ---


def _is_superadmin(session: Session, user_id: str) -> bool:
    """True si el usuario es superadmin (rol superadmin en cualquier workspace)."""
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        return False
    return session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        role_id=superadmin_role.id,
    ).first() is not None


def _get_user_system_role_name(session: Session, user_id: str, workspace_id: str) -> str | None:
    """Devuelve el nombre del rol de sistema del usuario en el workspace (owner, admin, approver, creator, viewer)."""
    role = get_user_role(session, user_id, workspace_id)
    return role.name if role else None


def _get_user_operational_role_ids(session: Session, user_id: str, workspace_id: str) -> set[str]:
    """IDs de roles operativos asignados al usuario en el workspace."""
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    if not membership:
        return set()
    rows = (
        session.query(UserOperationalRole.operational_role_id)
        .filter_by(workspace_membership_id=membership.id)
        .all()
    )
    return {r[0] for r in rows}


def _get_folder_allowed_operational_role_ids(session: Session, folder_id: str) -> set[str]:
    """
    IDs de roles operativos que pueden acceder a la carpeta.
    Si inherits_permissions es True, sube al padre hasta encontrar permisos explícitos.
    Si la carpeta raíz hereda y no tiene permisos, se considera que no hay restricción (todos).
    """
    folder = get_folder_by_id(session, folder_id)
    if not folder:
        return set()
    visited: set[str] = set()
    current = folder
    while current:
        if current.id in visited:
            return set()
        visited.add(current.id)
        if not getattr(current, "inherits_permissions", True):
            rows = (
                session.query(FolderPermission.operational_role_id)
                .filter_by(folder_id=current.id)
                .all()
            )
            return {r[0] for r in rows}
        if current.parent_id:
            current = get_folder_by_id(session, current.parent_id)
        else:
            return set()
    return set()


def _has_folder_access_by_operational_roles(
    session: Session, user_id: str, workspace_id: str, folder_id: str
) -> bool:
    """
    True si el usuario tiene acceso a la carpeta por roles operativos.
    Si la carpeta no tiene restricciones (lista vacía o raíz heredando), True.
    """
    allowed = _get_folder_allowed_operational_role_ids(session, folder_id)
    if not allowed:
        # Sin restricciones en la carpeta: cualquier miembro del workspace puede (por rol de sistema)
        return True
    user_roles = _get_user_operational_role_ids(session, user_id, workspace_id)
    return bool(user_roles & allowed)


def can_view_folder(
    session: Session, user_id: str, workspace_id: str, folder_id: str
) -> bool:
    """
    Verifica si un usuario puede ver (acceder a) una carpeta.
    superadmin/owner/admin: bypass. Luego: membership + acceso por rol operativo + permiso documents.view.
    """
    if _is_superadmin(session, user_id):
        return True
    role_name = _get_user_system_role_name(session, user_id, workspace_id)
    if role_name in ("owner", "admin"):
        return True
    if not role_name:
        return False
    if not has_permission(session, user_id, workspace_id, "documents.view"):
        return False
    return _has_folder_access_by_operational_roles(session, user_id, workspace_id, folder_id)


def can_create_in_folder(
    session: Session, user_id: str, workspace_id: str, folder_id: str
) -> bool:
    """
    Verifica si un usuario puede crear documentos en una carpeta.
    superadmin/owner/admin: bypass. Luego: acceso por rol operativo + permiso documents.create.
    """
    if _is_superadmin(session, user_id):
        return True
    role_name = _get_user_system_role_name(session, user_id, workspace_id)
    if role_name in ("owner", "admin"):
        return True
    if not role_name:
        return False
    if not has_permission(session, user_id, workspace_id, "documents.create"):
        return False
    return _has_folder_access_by_operational_roles(session, user_id, workspace_id, folder_id)


def can_approve_in_folder(
    session: Session, user_id: str, workspace_id: str, folder_id: str
) -> bool:
    """
    Verifica si un usuario puede aprobar/rechazar documentos en una carpeta.
    superadmin/owner/admin: bypass. Luego: acceso por rol operativo + permiso documents.approve.
    """
    if _is_superadmin(session, user_id):
        return True
    role_name = _get_user_system_role_name(session, user_id, workspace_id)
    if role_name in ("owner", "admin"):
        return True
    if not role_name:
        return False
    if not has_permission(session, user_id, workspace_id, "documents.approve"):
        return False
    return _has_folder_access_by_operational_roles(session, user_id, workspace_id, folder_id)



