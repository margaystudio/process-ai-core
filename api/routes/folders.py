"""
Endpoint para gestionar carpetas dentro de workspaces.

Este endpoint maneja:
- POST /api/v1/folders: Crear una nueva carpeta
- GET /api/v1/folders: Listar carpetas de un workspace
- GET /api/v1/folders/{folder_id}: Obtener una carpeta
"""

import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from process_ai_core.db.helpers import create_folder, get_folders_by_workspace, get_folder_by_id, update_folder, delete_folder
from process_ai_core.db.models import Folder, FolderPermission, OperationalRole
from api.dependencies import get_db, get_current_user_id
from api.dependencies import is_superadmin
from process_ai_core.db.permissions import (
    get_user_role,
    can_view_folder,
    can_create_in_folder,
    has_permission,
)

from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)
from ..models.requests import (
    FolderCreateRequest, FolderResponse, FolderUpdateRequest,
    FolderPermissionsUpdateRequest,
)

router = APIRouter(
    prefix="/api/v1/folders",
    tags=["folders"],
    dependencies=[Depends(sync_workspace_access)],
)


def _require_workspace_member(session: Session, user_id: str, workspace_id: str) -> None:
    """Lanza 403 si el usuario no es miembro del workspace."""
    role = get_user_role(session, user_id, workspace_id)
    if not role:
        raise HTTPException(
            status_code=403,
            detail="No es miembro de este workspace",
        )


def _assert_folder_in_active_workspace(folder_workspace_id: str, active_workspace_id: str, folder_id: str) -> None:
    """Lanza 404 si la carpeta no pertenece al workspace activo del contexto."""
    if folder_workspace_id != active_workspace_id:
        raise HTTPException(status_code=404, detail=f"Carpeta {folder_id} no encontrada")


@router.post("", response_model=FolderResponse)
async def create_folder_endpoint(
    request: FolderCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Crea una nueva carpeta dentro de un workspace.

    Args:
        request: Datos de la carpeta a crear

    Returns:
        FolderResponse con los datos de la carpeta creada

    Raises:
        400: Si el workspace no existe
        500: Error interno del servidor
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    try:
        # Verificar que el workspace existe
        from process_ai_core.db.models import Workspace
        workspace = session.query(Workspace).filter_by(id=workspace_id).first()
        if not workspace:
            raise HTTPException(
                status_code=400,
                detail=f"Workspace {workspace_id} no encontrado"
            )

        _require_workspace_member(session, user_id, workspace_id)

        # Verificar permiso de creación en la carpeta padre (si aplica)
        if request.parent_id:
            parent = get_folder_by_id(session, request.parent_id)
            if not parent:
                raise HTTPException(
                    status_code=400,
                    detail=f"Carpeta padre {request.parent_id} no encontrada"
                )
            if parent.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=400,
                    detail="La carpeta padre no pertenece al workspace indicado",
                )
            if not can_create_in_folder(session, user_id, workspace_id, parent.id):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene permisos para crear en esta carpeta",
                )
        else:
            # Para carpetas raíz, exigir permiso global de creación en el workspace.
            user_role = get_user_role(session, user_id, workspace_id)
            role_name = user_role.name if user_role else None
            if role_name not in ("owner", "admin") and not has_permission(
                session, user_id, workspace_id, "documents.create"
            ):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene permisos para crear carpetas en este workspace",
                )

        # Crear la carpeta
        folder = create_folder(
            session=session,
            workspace_id=workspace_id,
            name=request.name,
            path=request.path or request.name,
            parent_id=request.parent_id,
            sort_order=request.sort_order or 0,
            metadata=request.metadata,
        )

        session.flush()

        return FolderResponse(
            id=folder.id,
            workspace_id=folder.workspace_id,
            name=folder.name,
            path=folder.path,
            parent_id=folder.parent_id,
            sort_order=folder.sort_order,
            inherits_permissions=getattr(folder, "inherits_permissions", True),
            created_at=folder.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error al crear carpeta: {str(e)}"
        ) from e
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        ) from e


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Lista todas las carpetas del workspace activo del usuario.

    Returns:
        Lista de FolderResponse
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    _require_workspace_member(session, user_id, workspace_id)

    folders = get_folders_by_workspace(session, workspace_id)
    visible_folders = [
        f for f in folders
        if can_view_folder(session, user_id, workspace_id, f.id)
    ]
    return [
        FolderResponse(
            id=f.id,
            workspace_id=f.workspace_id,
            name=f.name,
            path=f.path,
            parent_id=f.parent_id,
            sort_order=f.sort_order,
            inherits_permissions=getattr(f, "inherits_permissions", True),
            created_at=f.created_at.isoformat(),
        )
        for f in visible_folders
    ]


@router.get("/{folder_id}/permissions")
async def get_folder_permissions(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Obtiene los permisos de una carpeta (roles operativos con acceso).
    Requiere ser miembro del workspace (owner/admin para ver permisos).
    """
    folder = session.query(Folder).filter_by(id=folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    _assert_folder_in_active_workspace(folder.workspace_id, resolve_tenant_workspace_id(ctx), folder_id)

    # Superadmin tiene acceso global a la configuración.
    if is_superadmin(user_id, session):
        inherits = getattr(folder, "inherits_permissions", True)
        perms = session.query(FolderPermission).filter_by(folder_id=folder_id).all()
        role_ids = [p.operational_role_id for p in perms]
        roles = session.query(OperationalRole).filter(OperationalRole.id.in_(role_ids)).all() if role_ids else []
        role_list = [{"id": r.id, "name": r.name, "slug": r.slug} for r in roles]
        return {
            "folder_id": folder_id,
            "inherits_permissions": inherits,
            "operational_role_ids": role_ids,
            "operational_roles": role_list,
        }

    role = get_user_role(session, user_id, folder.workspace_id)
    if not role or role.name not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Se requiere rol owner o admin")
    inherits = getattr(folder, "inherits_permissions", True)
    perms = session.query(FolderPermission).filter_by(folder_id=folder_id).all()
    role_ids = [p.operational_role_id for p in perms]
    roles = session.query(OperationalRole).filter(OperationalRole.id.in_(role_ids)).all() if role_ids else []
    role_list = [{"id": r.id, "name": r.name, "slug": r.slug} for r in roles]
    return {
        "folder_id": folder_id,
        "inherits_permissions": inherits,
        "operational_role_ids": role_ids,
        "operational_roles": role_list,
    }


@router.put("/{folder_id}/permissions")
async def update_folder_permissions(
    folder_id: str,
    request: FolderPermissionsUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Actualiza los permisos de una carpeta (herencia y roles operativos con acceso).
    Requiere ser owner o admin del workspace.
    """
    folder = session.query(Folder).filter_by(id=folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    _assert_folder_in_active_workspace(folder.workspace_id, resolve_tenant_workspace_id(ctx), folder_id)
    role = get_user_role(session, user_id, folder.workspace_id)
    if not role or role.name not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Se requiere rol owner o admin")
    if request.inherits_permissions is not None:
        folder.inherits_permissions = request.inherits_permissions
    if request.operational_role_ids is not None:
        # Validar todos los roles de una (batch, no N+1) ANTES de reescribir permisos,
        # así un id inválido no deja los permisos borrados a medias.
        requested_role_ids = list(request.operational_role_ids)
        if requested_role_ids:
            valid_ids = {
                row[0]
                for row in session.query(OperationalRole.id)
                .filter(
                    OperationalRole.id.in_(requested_role_ids),
                    OperationalRole.workspace_id == folder.workspace_id,
                )
                .all()
            }
            missing = [rid for rid in requested_role_ids if rid not in valid_ids]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Rol operativo {missing[0]} no existe o no pertenece al workspace",
                )
        session.query(FolderPermission).filter_by(folder_id=folder_id).delete()
        for rid in requested_role_ids:
            session.add(
                FolderPermission(
                    id=str(uuid.uuid4()),
                    folder_id=folder_id,
                    operational_role_id=rid,
                )
            )
    session.commit()
    return {"message": "Permisos actualizados", "folder_id": folder_id}


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Obtiene una carpeta por su ID.

    Args:
        folder_id: ID de la carpeta

    Returns:
        FolderResponse

    Raises:
        404: Si la carpeta no existe
    """
    folder = get_folder_by_id(session, folder_id)
    if not folder:
        raise HTTPException(
            status_code=404,
            detail=f"Carpeta {folder_id} no encontrada"
        )
    _assert_folder_in_active_workspace(folder.workspace_id, resolve_tenant_workspace_id(ctx), folder_id)

    _require_workspace_member(session, user_id, folder.workspace_id)
    if not can_view_folder(session, user_id, folder.workspace_id, folder.id):
        raise HTTPException(
            status_code=403,
            detail="No tiene permisos para acceder a esta carpeta",
        )

    return FolderResponse(
        id=folder.id,
        workspace_id=folder.workspace_id,
        name=folder.name,
        path=folder.path,
        parent_id=folder.parent_id,
        sort_order=folder.sort_order,
        inherits_permissions=getattr(folder, "inherits_permissions", True),
        created_at=folder.created_at.isoformat(),
    )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder_endpoint(
    folder_id: str,
    request: FolderUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Actualiza una carpeta existente.

    Args:
        folder_id: ID de la carpeta a actualizar
        request: Datos a actualizar

    Returns:
        FolderResponse con los datos actualizados

    Raises:
        404: Si la carpeta no existe
        400: Si hay errores de validación (ciclos, etc.)
        500: Error interno del servidor
    """
    try:
        existing = get_folder_by_id(session, folder_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Carpeta {folder_id} no encontrada",
            )
        _assert_folder_in_active_workspace(existing.workspace_id, resolve_tenant_workspace_id(ctx), folder_id)

        _require_workspace_member(session, user_id, existing.workspace_id)
        if not can_create_in_folder(session, user_id, existing.workspace_id, existing.id):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para actualizar esta carpeta",
            )

        if request.parent_id:
            parent = get_folder_by_id(session, request.parent_id)
            if not parent:
                raise HTTPException(
                    status_code=400,
                    detail=f"Carpeta padre {request.parent_id} no encontrada",
                )
            if parent.workspace_id != existing.workspace_id:
                raise HTTPException(
                    status_code=400,
                    detail="La carpeta padre debe pertenecer al mismo workspace",
                )
            if not can_create_in_folder(session, user_id, existing.workspace_id, parent.id):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene permisos para mover/actualizar en la carpeta destino",
                )

        folder = update_folder(
            session=session,
            folder_id=folder_id,
            name=request.name,
            path=request.path,
            parent_id=request.parent_id,
            sort_order=request.sort_order,
            inherits_permissions=request.inherits_permissions,
            metadata=request.metadata,
        )

        session.flush()

        return FolderResponse(
            id=folder.id,
            workspace_id=folder.workspace_id,
            name=folder.name,
            path=folder.path,
            parent_id=folder.parent_id,
            sort_order=folder.sort_order,
            inherits_permissions=getattr(folder, "inherits_permissions", True),
            created_at=folder.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except ValueError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        ) from e


@router.delete("/{folder_id}")
async def delete_folder_endpoint(
    folder_id: str,
    move_documents_to: str = None,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_db),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Elimina una carpeta.

    Args:
        folder_id: ID de la carpeta a eliminar
        move_documents_to: ID de carpeta destino para mover documentos (query parameter, opcional)

    Returns:
        Mensaje de confirmación

    Raises:
        404: Si la carpeta no existe
        400: Si la carpeta tiene subcarpetas o hay otros errores
        500: Error interno del servidor
    """
    try:
        folder = get_folder_by_id(session, folder_id)
        if not folder:
            raise HTTPException(
                status_code=404,
                detail=f"Carpeta {folder_id} no encontrada",
            )
        _assert_folder_in_active_workspace(folder.workspace_id, resolve_tenant_workspace_id(ctx), folder_id)

        _require_workspace_member(session, user_id, folder.workspace_id)
        if not can_create_in_folder(session, user_id, folder.workspace_id, folder.id):
            raise HTTPException(
                status_code=403,
                detail="No tiene permisos para eliminar esta carpeta",
            )

        if move_documents_to:
            destination_folder = get_folder_by_id(session, move_documents_to)
            if not destination_folder:
                raise HTTPException(
                    status_code=400,
                    detail=f"Carpeta destino {move_documents_to} no encontrada",
                )
            if destination_folder.workspace_id != folder.workspace_id:
                raise HTTPException(
                    status_code=400,
                    detail="La carpeta destino debe pertenecer al mismo workspace",
                )
            if not can_create_in_folder(session, user_id, folder.workspace_id, destination_folder.id):
                raise HTTPException(
                    status_code=403,
                    detail="No tiene permisos para mover documentos a la carpeta destino",
                )

        delete_folder(
            session=session,
            folder_id=folder_id,
            move_documents_to=move_documents_to if move_documents_to else None,
        )

        session.flush()

        return {
            "message": f"Carpeta {folder_id} eliminada exitosamente",
            "folder_id": folder_id,
        }

    except HTTPException:
        raise
    except ValueError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        ) from e

