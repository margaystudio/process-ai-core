"""
Funciones helper para trabajar con los modelos genéricos (Workspace/Document).

Estas funciones facilitan:
- Crear workspaces/documents con metadata apropiada
- Obtener workspaces/documents por dominio
- Trabajar con metadata JSON
"""

from __future__ import annotations

import json
import uuid
from typing import Dict, Any

from sqlalchemy.orm import Session

from .models import Workspace, Document, Process, Recipe, User, WorkspaceMembership, Folder, Validation, AuditLog, DocumentVersion, Run
from datetime import datetime


def create_organization_workspace(
    session: Session,
    name: str,
    slug: str,
    country: str = "UY",
    business_type: str = "",
    language_style: str = "es_uy_formal",
    default_audience: str = "operativo",
    context_text: str = "",
) -> Workspace:
    """
    Crea un Workspace de tipo "organization" (equivalente a Client).
    Automáticamente crea una carpeta raíz con el nombre del workspace.
    
    Args:
        session: Sesión de base de datos
        name: Nombre de la organización
        slug: Slug único
        country: Código de país (ISO2)
        business_type: Tipo de negocio
        language_style: Estilo de idioma
        default_audience: Audiencia por defecto
        context_text: Contexto libre del negocio
    
    Returns:
        Workspace creado (con carpeta raíz creada)
    """
    metadata = {
        "country": country,
        "business_type": business_type,
        "language_style": language_style,
        "default_audience": default_audience,
        "context_text": context_text,
    }

    workspace = Workspace(
        slug=slug,
        name=name,
        workspace_type="organization",
        metadata_json=json.dumps(metadata),
    )
    session.add(workspace)
    session.flush()  # Para obtener el ID del workspace
    
    # Crear carpeta raíz automáticamente
    root_folder = create_folder(
        session=session,
        workspace_id=workspace.id,
        name=name,  # Nombre de la carpeta = nombre del workspace
        path=name,
        parent_id=None,
        sort_order=0,
    )
    
    return workspace


def create_user_workspace(
    session: Session,
    name: str,
    slug: str,
    preferences: Dict[str, Any] | None = None,
) -> Workspace:
    """
    Crea un Workspace de tipo "user" (para recetas personales, etc.).
    Automáticamente crea una carpeta raíz con el nombre del usuario.
    
    Args:
        session: Sesión de base de datos
        name: Nombre del usuario
        slug: Slug único
        preferences: Preferencias del usuario (cuisine, diet, etc.)
    
    Returns:
        Workspace creado (con carpeta raíz creada)
    """
    metadata = {"preferences": preferences or {}}

    workspace = Workspace(
        slug=slug,
        name=name,
        workspace_type="user",
        metadata_json=json.dumps(metadata),
    )
    session.add(workspace)
    session.flush()  # Para obtener el ID del workspace
    
    # Crear carpeta raíz automáticamente
    root_folder = create_folder(
        session=session,
        workspace_id=workspace.id,
        name=name,  # Nombre de la carpeta = nombre del usuario
        path=name,
        parent_id=None,
        sort_order=0,
    )
    
    return workspace


def create_folder(
    session: Session,
    workspace_id: str,
    name: str,
    path: str = "",
    parent_id: str | None = None,
    sort_order: int = 0,
    metadata: Dict[str, Any] | None = None,
) -> Folder:
    """
    Crea una carpeta dentro de un workspace.
    
    Args:
        session: Sesión de base de datos
        workspace_id: ID del workspace
        name: Nombre de la carpeta
        path: Path completo de la carpeta (ej: "RRHH/Recursos Humanos")
        parent_id: ID de la carpeta padre (opcional, para estructura jerárquica)
        sort_order: Orden de visualización
        metadata: Metadata adicional (JSON)
    
    Returns:
        Folder creado
    """
    folder = Folder(
        workspace_id=workspace_id,
        name=name,
        path=path or name,
        parent_id=parent_id,
        sort_order=sort_order,
        metadata_json=json.dumps(metadata or {}),
    )
    session.add(folder)
    return folder


def get_folders_by_workspace(session: Session, workspace_id: str) -> list[Folder]:
    """
    Obtiene todas las carpetas de un workspace, ordenadas por sort_order y nombre.
    """
    return (
        session.query(Folder)
        .filter_by(workspace_id=workspace_id)
        .order_by(Folder.sort_order, Folder.name)
        .all()
    )


def get_folder_by_id(session: Session, folder_id: str) -> Folder | None:
    """
    Obtiene una carpeta por su ID.
    """
    return session.query(Folder).filter_by(id=folder_id).first()


def update_folder(
    session: Session,
    folder_id: str,
    name: str | None = None,
    path: str | None = None,
    parent_id: str | None = None,
    sort_order: int | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Folder:
    """
    Actualiza una carpeta existente.
    
    Args:
        session: Sesión de base de datos
        folder_id: ID de la carpeta a actualizar
        name: Nuevo nombre (opcional)
        path: Nuevo path (opcional)
        parent_id: Nuevo parent_id (opcional, None para quitar parent)
        sort_order: Nuevo sort_order (opcional)
        metadata: Metadata adicional (opcional, se mergea con la existente)
    
    Returns:
        Folder actualizado
    
    Raises:
        ValueError: Si la carpeta no existe
    """
    folder = get_folder_by_id(session, folder_id)
    if not folder:
        raise ValueError(f"Carpeta {folder_id} no encontrada")
    
    if name is not None:
        folder.name = name
    if path is not None:
        folder.path = path
    if parent_id is not None:
        # Validar que no se cree un ciclo (la carpeta padre no puede ser la misma ni un hijo)
        if parent_id == folder_id:
            raise ValueError("Una carpeta no puede ser su propia padre")
        if parent_id:
            parent = get_folder_by_id(session, parent_id)
            if not parent:
                raise ValueError(f"Carpeta padre {parent_id} no encontrada")
            # Verificar que no sea un hijo (evitar ciclos)
            current = parent
            while current:
                if current.id == folder_id:
                    raise ValueError("No se puede crear un ciclo en la jerarquía de carpetas")
                current = get_folder_by_id(session, current.parent_id) if current.parent_id else None
        folder.parent_id = parent_id
    if sort_order is not None:
        folder.sort_order = sort_order
    if metadata is not None:
        # Mergear metadata existente con la nueva
        existing_meta = json.loads(folder.metadata_json) if folder.metadata_json else {}
        existing_meta.update(metadata)
        folder.metadata_json = json.dumps(existing_meta)
    
    return folder


def delete_folder(session: Session, folder_id: str, move_documents_to: str | None = None) -> bool:
    """
    Elimina una carpeta.
    
    Args:
        session: Sesión de base de datos
        folder_id: ID de la carpeta a eliminar
        move_documents_to: ID de carpeta destino para mover documentos (opcional)
                          Si es None, los documentos quedan sin carpeta (folder_id = None)
    
    Returns:
        True si se eliminó correctamente
    
    Raises:
        ValueError: Si la carpeta no existe o tiene hijos
    """
    folder = get_folder_by_id(session, folder_id)
    if not folder:
        raise ValueError(f"Carpeta {folder_id} no encontrada")
    
    # Verificar si tiene hijos
    children = session.query(Folder).filter_by(parent_id=folder_id).all()
    if children:
        raise ValueError(f"No se puede eliminar la carpeta porque tiene {len(children)} subcarpeta(s). Eliminá primero las subcarpetas.")
    
    # Mover documentos si es necesario
    documents = session.query(Document).filter_by(folder_id=folder_id).all()
    if documents:
        if move_documents_to:
            # Validar que la carpeta destino existe
            dest_folder = get_folder_by_id(session, move_documents_to)
            if not dest_folder:
                raise ValueError(f"Carpeta destino {move_documents_to} no encontrada")
            for doc in documents:
                doc.folder_id = move_documents_to
        else:
            # Mover documentos a la carpeta raíz del workspace
            workspace_id = folder.workspace_id
            root_folder = session.query(Folder).filter_by(
                workspace_id=workspace_id,
                parent_id=None
            ).first()
            
            if not root_folder:
                raise ValueError(f"No se puede eliminar la carpeta porque no hay carpeta raíz para mover los documentos")
            
            for doc in documents:
                doc.folder_id = root_folder.id
    
    # Eliminar la carpeta
    session.delete(folder)
    return True


def create_process_document(
    session: Session,
    workspace_id: str,
    name: str,
    description: str = "",
    folder_id: str = None,  # Requerido, pero None para compatibilidad con código legacy
    audience: str = "",
    detail_level: str = "",
    context_text: str = "",
) -> Process:
    """
    Crea un Process (hereda de Document).
    
    Args:
        session: Sesión de base de datos
        workspace_id: ID del workspace
        name: Nombre del proceso
        description: Descripción breve
        folder_id: ID de la carpeta donde se ubica el proceso (REQUERIDO)
        audience: Audiencia (si vacío, usa default del workspace)
        detail_level: Nivel de detalle (si vacío, usa default del workspace)
        context_text: Contexto específico del proceso
    
    Returns:
        Process creado
    
    Raises:
        ValueError: Si folder_id no está especificado
    """
    # folder_id es requerido
    if not folder_id:
        raise ValueError("folder_id es requerido. Debe seleccionar una carpeta para crear el proceso.")
    
    process = Process(
        workspace_id=workspace_id,
        folder_id=folder_id,
        document_type="process",
        name=name,
        description=description,
        audience=audience,
        detail_level=detail_level,
        context_text=context_text,
    )
    session.add(process)
    return process


def create_run(
    session: Session,
    document_id: str,
    document_type: str,
    profile: str = "",
    run_id: str | None = None,
) -> "Run":
    """
    Crea un Run (ejecución del pipeline).
    
    Args:
        session: Sesión de base de datos
        document_id: ID del documento asociado
        document_type: Tipo de documento ("process" | "recipe" | ...)
        profile: Perfil usado
        run_id: ID opcional para el run (si no se proporciona, se genera uno)
    
    Returns:
        Run creado
    """
    from process_ai_core.db.models import Run
    run = Run(
        id=run_id or str(uuid.uuid4()),
        document_id=document_id,
        document_type=document_type,
        profile=profile,
    )
    session.add(run)
    return run


def create_artifact(
    session: Session,
    run_id: str,
    artifact_type: str,
    file_path: str,
) -> "Artifact":
    """
    Crea un Artifact (artefacto generado por un run).
    
    Args:
        session: Sesión de base de datos
        run_id: ID del run asociado
        artifact_type: Tipo ("json" | "md" | "pdf")
        file_path: Ruta relativa al archivo
    
    Returns:
        Artifact creado
    """
    from process_ai_core.db.models import Artifact
    artifact = Artifact(
        run_id=run_id,
        type=artifact_type,
        path=file_path,
    )
    session.add(artifact)
    return artifact


def get_workspace_metadata(workspace: Workspace) -> Dict[str, Any]:
    """
    Obtiene la metadata de un workspace como dict.
    """
    try:
        return json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except:
        return {}


def get_workspace_by_slug(session: Session, slug: str) -> Workspace | None:
    """
    Obtiene un workspace por su slug.
    """
    return session.query(Workspace).filter_by(slug=slug).first()


def get_documents_by_type(session: Session, workspace_id: str, document_type: str) -> list[Document]:
    """
    Obtiene todos los documentos de un tipo específico en un workspace.
    
    Args:
        session: Sesión de base de datos
        workspace_id: ID del workspace
        document_type: Tipo de documento ("process" | "recipe" | ...)
    
    Returns:
        Lista de documentos (pueden ser Process, Recipe, etc. según document_type)
    """
    return (
        session.query(Document)
        .filter_by(workspace_id=workspace_id, document_type=document_type)
        .order_by(Document.created_at.desc())
        .all()
    )


def get_processes_by_workspace(session: Session, workspace_id: str) -> list[Process]:
    """
    Obtiene todos los procesos de un workspace.
    """
    return (
        session.query(Process)
        .filter_by(workspace_id=workspace_id)
        .order_by(Process.created_at.desc())
        .all()
    )


def get_recipes_by_workspace(session: Session, workspace_id: str) -> list[Recipe]:
    """
    Obtiene todas las recetas de un workspace.
    """
    return (
        session.query(Recipe)
        .filter_by(workspace_id=workspace_id)
        .order_by(Recipe.created_at.desc())
        .all()
    )


# ============================================================
# Helpers de Validación y Auditoría
# ============================================================

def create_validation(
    session: Session,
    document_id: str,
    run_id: str | None = None,
    validator_user_id: str | None = None,
    observations: str = "",
    checklist_json: str = "{}",
) -> Validation:
    """
    Crea una nueva validación para un documento o run.
    
    Args:
        session: Sesión de base de datos
        document_id: ID del documento
        run_id: ID del run (opcional, si es validación de un run específico)
        validator_user_id: ID del usuario validador (opcional)
        observations: Observaciones del validador
        checklist_json: Checklist en formato JSON
    
    Returns:
        Validation creada
    """
    validation = Validation(
        id=str(uuid.uuid4()),
        document_id=document_id,
        run_id=run_id,
        validator_user_id=validator_user_id,
        status="pending",
        observations=observations,
        checklist_json=checklist_json,
    )
    session.add(validation)
    
    # Crear audit log
    create_audit_log(
        session=session,
        document_id=document_id,
        run_id=run_id,
        user_id=validator_user_id,
        action="validated",
        entity_type="validation",
        entity_id=validation.id,
        metadata_json=json.dumps({"status": "pending"}),
    )
    
    return validation


def approve_validation(
    session: Session,
    validation_id: str,
    user_id: str | None = None,
) -> Validation:
    """
    Aprueba una validación.
    
    Args:
        session: Sesión de base de datos
        validation_id: ID de la validación
        user_id: ID del usuario que aprueba (opcional)
    
    Returns:
        Validation aprobada
    """
    validation = session.query(Validation).filter_by(id=validation_id).first()
    if not validation:
        raise ValueError(f"Validación {validation_id} no encontrada")
    
    validation.status = "approved"
    validation.completed_at = datetime.utcnow()
    
    # Actualizar estado del documento
    document = session.query(Document).filter_by(id=validation.document_id).first()
    if document:
        document.status = "approved"
    
    # Si hay un run asociado, marcarlo como aprobado
    if validation.run_id:
        run = session.query(Run).filter_by(id=validation.run_id).first()
        if run:
            run.is_approved = True
            run.validation_id = validation_id
    
    # Crear audit log
    create_audit_log(
        session=session,
        document_id=validation.document_id,
        run_id=validation.run_id,
        user_id=user_id,
        action="approved",
        entity_type="validation",
        entity_id=validation_id,
        metadata_json=json.dumps({"status": "approved"}),
    )
    
    return validation


def reject_validation(
    session: Session,
    validation_id: str,
    observations: str,
    user_id: str | None = None,
) -> Validation:
    """
    Rechaza una validación con observaciones.
    
    Args:
        session: Sesión de base de datos
        validation_id: ID de la validación
        observations: Observaciones del rechazo
        user_id: ID del usuario que rechaza (opcional)
    
    Returns:
        Validation rechazada
    """
    validation = session.query(Validation).filter_by(id=validation_id).first()
    if not validation:
        raise ValueError(f"Validación {validation_id} no encontrada")
    
    validation.status = "rejected"
    validation.observations = observations
    validation.completed_at = datetime.utcnow()
    
    # Actualizar estado del documento
    document = session.query(Document).filter_by(id=validation.document_id).first()
    if document:
        document.status = "rejected"
    
    # Crear audit log
    create_audit_log(
        session=session,
        document_id=validation.document_id,
        run_id=validation.run_id,
        user_id=user_id,
        action="rejected",
        entity_type="validation",
        entity_id=validation_id,
        changes_json=json.dumps({"observations": observations}),
        metadata_json=json.dumps({"status": "rejected"}),
    )
    
    return validation


def create_audit_log(
    session: Session,
    document_id: str,
    action: str,
    run_id: str | None = None,
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    changes_json: str = "{}",
    metadata_json: str = "{}",
) -> AuditLog:
    """
    Crea un registro de auditoría.
    
    Args:
        session: Sesión de base de datos
        document_id: ID del documento
        action: Acción realizada (created, updated, validated, rejected, etc.)
        run_id: ID del run (opcional)
        user_id: ID del usuario (opcional)
        entity_type: Tipo de entidad relacionada (opcional)
        entity_id: ID de la entidad relacionada (opcional)
        changes_json: Cambios realizados en formato JSON
        metadata_json: Metadata adicional en formato JSON
    
    Returns:
        AuditLog creado
    """
    audit_log = AuditLog(
        id=str(uuid.uuid4()),
        document_id=document_id,
        run_id=run_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes_json=changes_json,
        metadata_json=metadata_json,
    )
    session.add(audit_log)
    return audit_log


def create_document_version(
    session: Session,
    document_id: str,
    run_id: str | None,
    content_type: str,
    content_json: str,
    content_markdown: str,
    validation_id: str | None = None,
    approved_by: str | None = None,
) -> DocumentVersion:
    """
    Crea una nueva versión aprobada de un documento.
    
    Args:
        session: Sesión de base de datos
        document_id: ID del documento
        run_id: ID del run (opcional, NULL si es edición manual)
        content_type: Tipo de contenido (generated | manual_edit | ai_patch)
        content_json: JSON del documento
        content_markdown: Markdown del documento
        validation_id: ID de la validación asociada (opcional)
        approved_by: ID del usuario que aprobó (opcional)
    
    Returns:
        DocumentVersion creada
    """
    # Obtener el número de versión siguiente
    last_version = (
        session.query(DocumentVersion)
        .filter_by(document_id=document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )
    version_number = (last_version.version_number + 1) if last_version else 1
    
    # Marcar todas las versiones anteriores como no actuales
    session.query(DocumentVersion).filter_by(
        document_id=document_id,
        is_current=True
    ).update({"is_current": False})
    
    # Crear nueva versión
    version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=document_id,
        run_id=run_id,
        version_number=version_number,
        content_type=content_type,
        content_json=content_json,
        content_markdown=content_markdown,
        approved_at=datetime.utcnow(),
        approved_by=approved_by,
        validation_id=validation_id,
        is_current=True,
    )
    session.add(version)
    
    # Actualizar documento con la versión aprobada
    document = session.query(Document).filter_by(id=document_id).first()
    if document:
        document.approved_version_id = version.id
        document.status = "approved"
    
    # Crear audit log
    create_audit_log(
        session=session,
        document_id=document_id,
        run_id=run_id,
        user_id=approved_by,
        action="approved",
        entity_type="version",
        entity_id=version.id,
        metadata_json=json.dumps({
            "version_number": version_number,
            "content_type": content_type,
        }),
    )
    
    return version


def update_document_status(
    session: Session,
    document_id: str,
    status: str,
) -> Document:
    """
    Actualiza el estado de un documento.
    
    Args:
        session: Sesión de base de datos
        document_id: ID del documento
        status: Nuevo estado (draft | pending_validation | approved | rejected | archived)
    
    Returns:
        Document actualizado
    """
    document = session.query(Document).filter_by(id=document_id).first()
    if not document:
        raise ValueError(f"Documento {document_id} no encontrado")
    
    old_status = document.status
    document.status = status
    
    # Crear audit log
    create_audit_log(
        session=session,
        document_id=document_id,
        action="updated",
        changes_json=json.dumps({
            "status": {"old": old_status, "new": status}
        }),
    )
    
    return document


def delete_document(
    session: Session,
    document_id: str,
) -> bool:
    """
    Elimina un documento y todos sus datos asociados.
    
    Elimina:
    - El documento (y su registro específico Process/Recipe)
    - Todos los runs asociados
    - Todos los artifacts asociados
    - Todas las validaciones asociadas
    - Todos los audit logs asociados
    - Todas las versiones asociadas
    
    Args:
        session: Sesión de base de datos
        document_id: ID del documento a eliminar
    
    Returns:
        True si se eliminó correctamente
    
    Raises:
        ValueError: Si el documento no existe
    """
    from process_ai_core.db.models import Run, Artifact, Validation, AuditLog, DocumentVersion
    
    document = session.query(Document).filter_by(id=document_id).first()
    if not document:
        raise ValueError(f"Documento {document_id} no encontrado")
    
    # Eliminar en orden (respetando foreign keys)
    # 1. Artifacts (dependen de Runs)
    runs = session.query(Run).filter_by(document_id=document_id).all()
    for run in runs:
        session.query(Artifact).filter_by(run_id=run.id).delete()
    
    # 2. Runs
    session.query(Run).filter_by(document_id=document_id).delete()
    
    # 3. Validations
    session.query(Validation).filter_by(document_id=document_id).delete()
    
    # 4. Document Versions
    session.query(DocumentVersion).filter_by(document_id=document_id).delete()
    
    # 5. Audit Logs
    session.query(AuditLog).filter_by(document_id=document_id).delete()
    
    # 6. Documento específico (Process/Recipe)
    if document.document_type == "process":
        session.query(Process).filter_by(id=document_id).delete()
    elif document.document_type == "recipe":
        session.query(Recipe).filter_by(id=document_id).delete()
    
    # 7. Documento base
    session.delete(document)
    
    return True

