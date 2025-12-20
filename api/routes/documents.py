"""
Endpoint para gestionar documentos (procesos, recetas, etc.).

Este endpoint maneja:
- GET /api/v1/documents: Listar documentos de un workspace (opcionalmente filtrados por folder)
- GET /api/v1/documents/{document_id}: Obtener un documento por ID
- PUT /api/v1/documents/{document_id}: Actualizar un documento
"""

from fastapi import APIRouter, HTTPException

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Process, Recipe

from ..models.requests import DocumentResponse, DocumentUpdateRequest

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
                document_type=doc.document_type,
                name=doc.name,
                description=doc.description,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Obtiene un documento por su ID.

    Args:
        document_id: ID del documento

    Returns:
        DocumentResponse

    Raises:
        404: Si el documento no existe
    """
    with get_db_session() as session:
        # Usar polymorphic_identity para obtener el tipo correcto
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )

        # Si es un Process, obtener los campos específicos
        if doc.document_type == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if process:
                # Retornar con campos extendidos (aunque DocumentResponse no los incluye,
                # los podemos agregar en metadata o crear un response extendido)
                # Por ahora, solo retornamos los campos básicos
                pass

        return DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            folder_id=doc.folder_id,
            document_type=doc.document_type,
            name=doc.name,
            description=doc.description,
            status=doc.status,
            created_at=doc.created_at.isoformat(),
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(document_id: str, request: DocumentUpdateRequest):
    """
    Actualiza un documento.

    Args:
        document_id: ID del documento
        request: Datos a actualizar

    Returns:
        DocumentResponse actualizado

    Raises:
        404: Si el documento no existe
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )

        # Actualizar campos básicos
        if request.name is not None:
            doc.name = request.name
        if request.description is not None:
            doc.description = request.description
        if request.status is not None:
            doc.status = request.status
        if request.folder_id is not None:
            doc.folder_id = request.folder_id

        # Actualizar campos específicos según el tipo
        if doc.document_type == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if not process:
                # Si no existe el Process, crearlo (no debería pasar, pero por seguridad)
                process = Process(
                    id=document_id,
                    workspace_id=doc.workspace_id,
                    folder_id=doc.folder_id,
                    document_type="process",
                    name=doc.name,
                    description=doc.description,
                    status=doc.status,
                )
                session.add(process)
            
            if request.audience is not None:
                process.audience = request.audience
            if request.detail_level is not None:
                process.detail_level = request.detail_level
            if request.context_text is not None:
                process.context_text = request.context_text
        elif doc.document_type == "recipe":
            recipe = session.query(Recipe).filter_by(id=document_id).first()
            if recipe:
                if request.cuisine is not None:
                    recipe.cuisine = request.cuisine
                if request.difficulty is not None:
                    recipe.difficulty = request.difficulty
                if request.servings is not None:
                    recipe.servings = request.servings
                if request.prep_time is not None:
                    recipe.prep_time = request.prep_time
                if request.cook_time is not None:
                    recipe.cook_time = request.cook_time

        session.commit()
        session.refresh(doc)
        
        # Si es Process, refrescar también el Process
        if doc.document_type == "process":
            process = session.query(Process).filter_by(id=document_id).first()
            if process:
                session.refresh(process)

        return DocumentResponse(
            id=doc.id,
            workspace_id=doc.workspace_id,
            folder_id=doc.folder_id,
            document_type=doc.document_type,
            name=doc.name,
            description=doc.description,
            status=doc.status,
            created_at=doc.created_at.isoformat(),
        )


@router.get("/{document_id}/process")
async def get_process_details(document_id: str):
    """
    Obtiene los campos específicos de un Process.
    
    Solo funciona para documentos de tipo "process".
    """
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        if doc.document_type != "process":
            raise HTTPException(
                status_code=400,
                detail=f"El documento {document_id} no es un proceso"
            )
        
        process = session.query(Process).filter_by(id=document_id).first()
        if not process:
            # Si no existe el Process, devolver valores vacíos
            return {
                "audience": "",
                "detail_level": "",
                "context_text": "",
            }
        
        return {
            "audience": process.audience or "",
            "detail_level": process.detail_level or "",
            "context_text": process.context_text or "",
        }


@router.get("/{document_id}/runs")
async def get_document_runs(document_id: str):
    """
    Obtiene todos los runs asociados a un documento.
    """
    from process_ai_core.db.models import Run, Artifact
    
    with get_db_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Documento {document_id} no encontrado"
            )
        
        runs = session.query(Run).filter_by(document_id=document_id).order_by(Run.created_at.desc()).all()
        
        result = []
        for run in runs:
            artifacts = session.query(Artifact).filter_by(run_id=run.id).all()
            artifact_dict = {}
            for artifact in artifacts:
                # Construir URL del artifact
                # El path puede ser "output/{run_id}/process.pdf" o solo el filename
                filename = artifact.path.split('/')[-1]
                artifact_url = f"/api/v1/artifacts/{run.id}/{filename}"
                artifact_dict[artifact.type] = artifact_url
            
            result.append({
                "run_id": run.id,
                "created_at": run.created_at.isoformat(),
                "artifacts": artifact_dict,
            })
        
        return result

