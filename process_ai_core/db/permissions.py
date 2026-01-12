"""
Helpers para gestión de permisos y roles.

Este módulo proporciona funciones para:
- Verificar permisos de usuarios
- Crear roles y permisos predefinidos
- Gestionar asignaciones de permisos a roles
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Role, Permission, RolePermission, WorkspaceMembership, User


def has_permission(
    session: Session,
    user_id: str,
    workspace_id: str,
    permission_name: str,
) -> bool:
    """
    Verifica si un usuario tiene un permiso específico en un workspace.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
        permission_name: Nombre del permiso (ej: "documents.approve")
    
    Returns:
        True si el usuario tiene el permiso, False en caso contrario
    """
    # Obtener membership
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



