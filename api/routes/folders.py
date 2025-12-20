"""
Endpoint para gestionar carpetas dentro de workspaces.

Este endpoint maneja:
- POST /api/v1/folders: Crear una nueva carpeta
- GET /api/v1/folders: Listar carpetas de un workspace
- GET /api/v1/folders/{folder_id}: Obtener una carpeta
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import create_folder, get_folders_by_workspace, get_folder_by_id, update_folder, delete_folder
from process_ai_core.db.models import Folder

from ..models.requests import FolderCreateRequest, FolderResponse, FolderUpdateRequest

router = APIRouter(prefix="/api/v1/folders", tags=["folders"])


@router.post("", response_model=FolderResponse)
async def create_folder_endpoint(request: FolderCreateRequest):
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
    with get_db_session() as session:
        try:
            # Verificar que el workspace existe
            from process_ai_core.db.models import Workspace
            workspace = session.query(Workspace).filter_by(id=request.workspace_id).first()
            if not workspace:
                raise HTTPException(
                    status_code=400,
                    detail=f"Workspace {request.workspace_id} no encontrado"
                )

            # Verificar que la carpeta padre existe si se especifica
            if request.parent_id:
                parent = get_folder_by_id(session, request.parent_id)
                if not parent:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Carpeta padre {request.parent_id} no encontrada"
                    )

            # Crear la carpeta
            folder = create_folder(
                session=session,
                workspace_id=request.workspace_id,
                name=request.name,
                path=request.path or request.name,
                parent_id=request.parent_id,
                sort_order=request.sort_order or 0,
                metadata=request.metadata,
            )

            # El commit se hace automáticamente por get_db_session, pero lo hacemos explícito
            # para asegurar que se persista antes de retornar
            session.flush()  # Flush para obtener el ID sin hacer commit aún

            return FolderResponse(
                id=folder.id,
                workspace_id=folder.workspace_id,
                name=folder.name,
                path=folder.path,
                parent_id=folder.parent_id,
                sort_order=folder.sort_order,
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
async def list_folders(workspace_id: str = None):
    """
    Lista todas las carpetas de un workspace.

    Args:
        workspace_id: ID del workspace (query parameter)

    Returns:
        Lista de FolderResponse
    """
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="workspace_id es requerido"
        )
    with get_db_session() as session:
        folders = get_folders_by_workspace(session, workspace_id)
        return [
            FolderResponse(
                id=f.id,
                workspace_id=f.workspace_id,
                name=f.name,
                path=f.path,
                parent_id=f.parent_id,
                sort_order=f.sort_order,
                created_at=f.created_at.isoformat(),
            )
            for f in folders
        ]


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(folder_id: str):
    """
    Obtiene una carpeta por su ID.

    Args:
        folder_id: ID de la carpeta

    Returns:
        FolderResponse

    Raises:
        404: Si la carpeta no existe
    """
    with get_db_session() as session:
        folder = get_folder_by_id(session, folder_id)
        if not folder:
            raise HTTPException(
                status_code=404,
                detail=f"Carpeta {folder_id} no encontrada"
            )

        return FolderResponse(
            id=folder.id,
            workspace_id=folder.workspace_id,
            name=folder.name,
            path=folder.path,
            parent_id=folder.parent_id,
            sort_order=folder.sort_order,
            created_at=folder.created_at.isoformat(),
        )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder_endpoint(folder_id: str, request: FolderUpdateRequest):
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
    with get_db_session() as session:
        try:
            folder = update_folder(
                session=session,
                folder_id=folder_id,
                name=request.name,
                path=request.path,
                parent_id=request.parent_id,
                sort_order=request.sort_order,
                metadata=request.metadata,
            )

            session.commit()

            return FolderResponse(
                id=folder.id,
                workspace_id=folder.workspace_id,
                name=folder.name,
                path=folder.path,
                parent_id=folder.parent_id,
                sort_order=folder.sort_order,
                created_at=folder.created_at.isoformat(),
            )

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
async def delete_folder_endpoint(folder_id: str, move_documents_to: str = None):
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
    with get_db_session() as session:
        try:
            delete_folder(
                session=session,
                folder_id=folder_id,
                move_documents_to=move_documents_to if move_documents_to else None,
            )

            session.commit()

            return {
                "message": f"Carpeta {folder_id} eliminada exitosamente",
                "folder_id": folder_id,
            }

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

