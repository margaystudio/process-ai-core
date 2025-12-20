"""
Endpoint para gestionar documentos (procesos, recetas, etc.).

Este endpoint maneja:
- GET /api/v1/documents: Listar documentos de un workspace (opcionalmente filtrados por folder)
"""

from fastapi import APIRouter, HTTPException

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document

from ..models.requests import DocumentResponse

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(workspace_id: str = None, folder_id: str = None, document_type: str = "process"):
    """
    Lista documentos de un workspace.

    Args:
        workspace_id: ID del workspace (query parameter, requerido)
        folder_id: ID de la carpeta (query parameter, opcional - si se especifica, solo documentos de esa carpeta)
                   Si es "null" (string), devuelve solo documentos sin carpeta
        document_type: Tipo de documento (query parameter, default: "process")

    Returns:
        Lista de DocumentResponse
    """
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="workspace_id es requerido"
        )
    
    with get_db_session() as session:
        query = session.query(Document).filter_by(
            workspace_id=workspace_id,
            document_type=document_type
        )
        
        if folder_id:
            if folder_id.lower() == "null":
                # Devolver solo documentos sin carpeta
                query = query.filter(Document.folder_id.is_(None))
            else:
                # Devolver documentos de esa carpeta específica
                query = query.filter_by(folder_id=folder_id)
        # Si folder_id no se especifica, devolver todos los documentos del workspace
        
        documents = query.order_by(Document.created_at.desc()).all()
        
        return [
            DocumentResponse(
                id=doc.id,
                workspace_id=doc.workspace_id,
                folder_id=doc.folder_id,
                domain=doc.document_type,  # Mantener "domain" en la respuesta por compatibilidad
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]

