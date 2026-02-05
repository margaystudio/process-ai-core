"""
Endpoint para gestionar usuarios.

Este endpoint maneja:
- POST /api/v1/users: Crear un nuevo usuario
- GET /api/v1/users: Listar usuarios
- GET /api/v1/users/{user_id}: Obtener un usuario
- POST /api/v1/users/{user_id}/workspaces/{workspace_id}/membership: Agregar usuario a workspace con rol
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User, Workspace, WorkspaceMembership
from process_ai_core.db.permissions import has_permission
from ..dependencies import get_db, get_current_user_id

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("")
async def create_user(
    email: str,
    name: str,
):
    """
    Crea un nuevo usuario.
    
    Args:
        email: Email del usuario (único)
        name: Nombre del usuario
    
    Returns:
        Datos del usuario creado
    """
    with get_db_session() as session:
        try:
            # Verificar que el email no exista
            existing = session.query(User).filter_by(email=email).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe un usuario con el email '{email}'"
                )
            
            user = User(
                email=email,
                name=name,
            )
            session.add(user)
            session.flush()
            
            return {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
            }
        
        except HTTPException:
            raise
        except IntegrityError as e:
            session.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Error al crear usuario: {str(e)}"
            ) from e
        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error interno: {str(e)}"
            ) from e


@router.get("")
async def list_users():
    """
    Lista todos los usuarios.
    
    Returns:
        Lista de usuarios
    """
    with get_db_session() as session:
        users = session.query(User).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]


@router.get("/{user_id}")
async def get_user(user_id: str):
    """
    Obtiene un usuario por su ID.
    
    Args:
        user_id: ID del usuario
    
    Returns:
        Datos del usuario
    
    Raises:
        404: Si el usuario no existe
    """
    with get_db_session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no encontrado"
            )
        
        # Obtener memberships con roles
        memberships = session.query(WorkspaceMembership).filter_by(user_id=user_id).all()
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at.isoformat(),
            "workspaces": [
                {
                    "workspace_id": m.workspace_id,
                    "role": m.role,
                    "created_at": m.created_at.isoformat(),
                }
                for m in memberships
            ],
        }


@router.post("/{user_id}/workspaces/{workspace_id}/membership")
async def add_user_to_workspace(
    user_id: str,
    workspace_id: str,
    role_name: str = Query(default="owner", description="Rol del usuario en el workspace"),  # "owner" | "admin" | "creator" | "viewer" | "approver"
):
    """
    Agrega un usuario a un workspace con un rol específico.
    
    Ahora usa role_id (FK a Role) en lugar de role (string).
    
    Args:
        user_id: ID del usuario
        workspace_id: ID del workspace
        role_name: Nombre del rol del usuario en el workspace
    
    Returns:
        Datos del membership creado
    """
    with get_db_session() as session:
        from process_ai_core.db.models import Role
        
        # Verificar que el usuario existe
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no encontrado"
            )
        
        # Verificar que el workspace existe
        workspace = session.query(Workspace).filter_by(id=workspace_id).first()
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace {workspace_id} no encontrado"
            )
        
        # Buscar el rol por nombre
        role = session.query(Role).filter_by(name=role_name).first()
        if not role:
            raise HTTPException(
                status_code=400,
                detail=f"Rol '{role_name}' no encontrado. Roles disponibles: owner, admin, approver, creator, viewer"
            )
        
        # Verificar que no exista ya el membership
        existing = session.query(WorkspaceMembership).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
        ).first()
        
        if existing:
            # Actualizar el role_id si ya existe
            existing.role_id = role.id
            # Mantener role como string para compatibilidad (deprecated)
            existing.role = role_name
        else:
            # Crear nuevo membership
            membership = WorkspaceMembership(
                user_id=user_id,
                workspace_id=workspace_id,
                role_id=role.id,
                role=role_name,  # Deprecated, mantener para compatibilidad
            )
            session.add(membership)
            session.flush()
            existing = membership
        
        session.commit()
        
        return {
            "id": existing.id,
            "user_id": existing.user_id,
            "workspace_id": existing.workspace_id,
            "role_id": existing.role_id,
            "role": role_name,  # Retornar nombre del rol para compatibilidad
            "created_at": existing.created_at.isoformat(),
        }


@router.get("/{user_id}/workspaces")
async def get_user_workspaces(user_id: str, session: Session = Depends(get_db)):
    """
    Obtiene todos los workspaces a los que pertenece un usuario.
    
    Args:
        user_id: ID del usuario
    
    Returns:
        Lista de workspaces con información de membresía
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Obteniendo workspaces para usuario: {user_id}")
    
    # Usar la sesión proporcionada por la dependencia en lugar de crear una nueva
    # Esto asegura que veamos los cambios recientes
    from process_ai_core.db.models import Workspace, Role, User
    
    # Verificar que el usuario existe
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        logger.warning(f"Usuario {user_id} no encontrado")
        return []
    
    logger.info(f"Usuario encontrado: {user.email}")
    
    # Obtener todas las membresías del usuario
    memberships = session.query(WorkspaceMembership).filter_by(user_id=user_id).all()
    logger.info(f"Membresías encontradas: {len(memberships)}")
    
    if len(memberships) == 0:
        logger.warning(f"⚠️  Usuario {user_id} no tiene membresías. Verificando en BD directamente...")
        # Hacer una query directa para verificar
        direct_memberships = session.execute(
            f"SELECT * FROM workspace_memberships WHERE user_id = '{user_id}'"
        ).fetchall()
        logger.info(f"Query directa devolvió {len(direct_memberships)} membresías")
    
    workspaces = []
    for membership in memberships:
        workspace = session.query(Workspace).filter_by(id=membership.workspace_id).first()
        if not workspace:
            logger.warning(f"Workspace {membership.workspace_id} no encontrado para membresía {membership.id}")
            continue
        
        # Obtener el nombre del rol
        role_name = None
        if membership.role_id:
            role = session.query(Role).filter_by(id=membership.role_id).first()
            if role:
                role_name = role.name
        else:
            # Compatibilidad: usar role string si role_id no existe
            role_name = membership.role
        
        workspace_data = {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "workspace_type": workspace.workspace_type,
            "role": role_name,
            "created_at": workspace.created_at.isoformat(),
        }
        workspaces.append(workspace_data)
        logger.info(f"Workspace agregado: {workspace.name} ({workspace.workspace_type}) - Rol: {role_name}")
    
    logger.info(f"Total workspaces devueltos: {len(workspaces)}")
    return workspaces


@router.get("/{user_id}/role/{workspace_id}")
async def get_user_role_in_workspace(
    user_id: str,
    workspace_id: str,
):
    """
    Obtiene el rol de un usuario en un workspace específico.
    
    Args:
        user_id: ID del usuario
        workspace_id: ID del workspace
    
    Returns:
        Rol del usuario o None si no pertenece al workspace
    """
    with get_db_session() as session:
        membership = session.query(WorkspaceMembership).filter_by(
            user_id=user_id,
            workspace_id=workspace_id,
        ).first()
        
        if not membership:
            return {"role": None}
        
        # Obtener el nombre del rol desde role_id si existe
        role_name = None
        if membership.role_id:
            from process_ai_core.db.models import Role
            role = session.query(Role).filter_by(id=membership.role_id).first()
            if role:
                role_name = role.name
        else:
            # Compatibilidad: usar role string si role_id no existe
            role_name = membership.role
        
        return {"role": role_name}


@router.get("/{user_id}/permission/{workspace_id}/{permission_name}")
async def check_user_permission(
    user_id: str,
    workspace_id: str,
    permission_name: str,
    session: Session = Depends(get_db),
):
    """
    Verifica si un usuario tiene un permiso específico en un workspace.
    
    Args:
        user_id: ID del usuario
        workspace_id: ID del workspace
        permission_name: Nombre del permiso (ej: "workspaces.edit", "documents.approve")
    
    Returns:
        { has_permission: bool }
    """
    has_perm = has_permission(session, user_id, workspace_id, permission_name)
    return {"has_permission": has_perm}

