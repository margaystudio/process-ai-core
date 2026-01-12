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

from .models import (
    Workspace, Document, Process, Recipe, User, WorkspaceMembership, Folder, 
    Validation, AuditLog, DocumentVersion, Run, SubscriptionPlan, 
    WorkspaceSubscription, WorkspaceInvitation, Role
)
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


# ============================================================================
# Funciones helper para usuarios y autenticación
# ============================================================================

def get_user_by_external_id(session: Session, external_id: str) -> User | None:
    """
    Busca un usuario por su external_id (ID del proveedor de autenticación).
    
    Args:
        session: Sesión de base de datos
        external_id: ID del usuario en el proveedor externo (ej: Supabase user ID)
    
    Returns:
        User si existe, None si no
    """
    return session.query(User).filter_by(external_id=external_id).first()


def get_user_by_email(session: Session, email: str) -> User | None:
    """
    Busca un usuario por su email.
    
    Args:
        session: Sesión de base de datos
        email: Email del usuario
    
    Returns:
        User si existe, None si no
    """
    return session.query(User).filter_by(email=email).first()


def create_or_update_user_from_supabase(
    session: Session,
    supabase_user_id: str,
    email: str,
    name: str,
    auth_provider: str = "supabase",
    metadata: dict | None = None,
) -> tuple[User, bool]:
    """
    Crea o actualiza un usuario desde datos de Supabase Auth.
    
    Si el usuario ya existe (por external_id o email), lo actualiza.
    Si no existe, lo crea.
    
    Args:
        session: Sesión de base de datos
        supabase_user_id: ID del usuario en Supabase (sub del JWT)
        email: Email del usuario
        name: Nombre del usuario
        auth_provider: Proveedor de autenticación (default: "supabase")
        metadata: Metadata adicional del usuario (avatar, etc.)
    
    Returns:
        Tupla (User, created) donde created es True si se creó, False si se actualizó
    """
    # Buscar por external_id primero
    user = get_user_by_external_id(session, supabase_user_id)
    created = False
    
    if not user:
        # Si no existe por external_id, buscar por email
        user = get_user_by_email(session, email)
        
        if user:
            # Usuario existe pero no tiene external_id, actualizarlo
            user.external_id = supabase_user_id
            user.auth_provider = auth_provider
            if metadata:
                user.metadata_json = json.dumps(metadata)
            user.updated_at = datetime.utcnow()
        else:
            # Crear nuevo usuario
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                name=name,
                external_id=supabase_user_id,
                auth_provider=auth_provider,
                metadata_json=json.dumps(metadata or {}),
                auth_metadata_json=json.dumps({}),
            )
            session.add(user)
            created = True
    else:
        # Usuario existe, actualizar datos
        user.email = email
        user.name = name
        user.auth_provider = auth_provider
        if metadata:
            user.metadata_json = json.dumps(metadata)
        user.updated_at = datetime.utcnow()
    
    return user, created


# ============================================================================
# SUSCRIPCIONES Y LÍMITES
# ============================================================================

def get_subscription_plan(session: Session, plan_id: str) -> SubscriptionPlan | None:
    """Obtiene un plan de suscripción por ID."""
    return session.query(SubscriptionPlan).filter_by(id=plan_id).first()


def get_subscription_plan_by_name(session: Session, name: str) -> SubscriptionPlan | None:
    """Obtiene un plan de suscripción por nombre."""
    return session.query(SubscriptionPlan).filter_by(name=name, is_active=True).first()


def list_subscription_plans(
    session: Session, 
    plan_type: str | None = None,
    active_only: bool = True
) -> list[SubscriptionPlan]:
    """Lista planes de suscripción, opcionalmente filtrados por tipo."""
    query = session.query(SubscriptionPlan)
    if active_only:
        query = query.filter_by(is_active=True)
    if plan_type:
        query = query.filter_by(plan_type=plan_type)
    return query.order_by(SubscriptionPlan.sort_order).all()


def get_active_subscription(session: Session, workspace_id: str) -> WorkspaceSubscription | None:
    """Obtiene la suscripción activa de un workspace."""
    return session.query(WorkspaceSubscription).filter_by(
        workspace_id=workspace_id,
        status="active"
    ).first()


def get_subscription(session: Session, workspace_id: str) -> WorkspaceSubscription | None:
    """Obtiene la suscripción de un workspace (puede estar inactiva)."""
    return session.query(WorkspaceSubscription).filter_by(workspace_id=workspace_id).first()


def create_workspace_subscription(
    session: Session,
    workspace_id: str,
    plan_id: str,
    status: str = "active",
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
) -> WorkspaceSubscription:
    """
    Crea una suscripción para un workspace.
    
    Args:
        session: Sesión de base de datos
        workspace_id: ID del workspace
        plan_id: ID del plan de suscripción
        status: Estado inicial ("active", "trial", etc.)
        current_period_start: Inicio del período (default: ahora)
        current_period_end: Fin del período (default: +1 mes)
    
    Returns:
        WorkspaceSubscription creada
    """
    if current_period_start is None:
        current_period_start = datetime.utcnow()
    if current_period_end is None:
        from datetime import timedelta
        current_period_end = current_period_start + timedelta(days=30)
    
    subscription = WorkspaceSubscription(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        plan_id=plan_id,
        status=status,
        current_period_start=current_period_start,
        current_period_end=current_period_end,
        current_users_count=0,
        current_documents_count=0,
        current_documents_this_month=0,
        current_storage_gb=0.0,
    )
    session.add(subscription)
    return subscription


def check_workspace_limit(
    session: Session,
    workspace_id: str,
    limit_type: str,  # "users" | "documents" | "storage" | "documents_per_month"
) -> tuple[bool, str | None]:
    """
    Verifica si el workspace puede realizar una acción según su plan.
    
    Returns:
        (allowed: bool, error_message: str | None)
    """
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        return False, "Workspace sin suscripción activa"
    
    plan = subscription.plan
    
    if limit_type == "users":
        if plan.max_users is not None and subscription.current_users_count >= plan.max_users:
            return False, f"Límite de usuarios alcanzado ({plan.max_users})"
    
    elif limit_type == "documents":
        if plan.max_documents is not None and subscription.current_documents_count >= plan.max_documents:
            return False, f"Límite de documentos alcanzado ({plan.max_documents})"
    
    elif limit_type == "documents_per_month":
        if plan.max_documents_per_month is not None and subscription.current_documents_this_month >= plan.max_documents_per_month:
            return False, f"Límite mensual de documentos alcanzado ({plan.max_documents_per_month})"
    
    elif limit_type == "storage":
        if plan.max_storage_gb is not None and subscription.current_storage_gb >= plan.max_storage_gb:
            return False, f"Límite de almacenamiento alcanzado ({plan.max_storage_gb} GB)"
    
    return True, None


def increment_workspace_counter(
    session: Session,
    workspace_id: str,
    counter_type: str,  # "users" | "documents" | "storage"
    amount: int | float = 1,
):
    """Incrementa un contador del workspace."""
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        return
    
    if counter_type == "users":
        subscription.current_users_count += int(amount)
    elif counter_type == "documents":
        subscription.current_documents_count += int(amount)
        subscription.current_documents_this_month += int(amount)
    elif counter_type == "storage":
        subscription.current_storage_gb += float(amount)
    
    subscription.updated_at = datetime.utcnow()
    session.flush()


def decrement_workspace_counter(
    session: Session,
    workspace_id: str,
    counter_type: str,  # "users" | "documents" | "storage"
    amount: int | float = 1,
):
    """Decrementa un contador del workspace."""
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        return
    
    if counter_type == "users":
        subscription.current_users_count = max(0, subscription.current_users_count - int(amount))
    elif counter_type == "documents":
        subscription.current_documents_count = max(0, subscription.current_documents_count - int(amount))
    elif counter_type == "storage":
        subscription.current_storage_gb = max(0.0, subscription.current_storage_gb - float(amount))
    
    subscription.updated_at = datetime.utcnow()
    session.flush()


def reset_monthly_counters(session: Session, workspace_id: str):
    """Resetea los contadores mensuales del workspace."""
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        return
    
    subscription.current_documents_this_month = 0
    subscription.updated_at = datetime.utcnow()
    session.flush()


# ============================================================================
# INVITACIONES
# ============================================================================

def create_workspace_invitation(
    session: Session,
    workspace_id: str,
    invited_by_user_id: str,
    email: str,
    role_id: str,
    expires_in_days: int = 7,
    message: str | None = None,
) -> WorkspaceInvitation:
    """
    Crea una invitación para unirse a un workspace.
    
    Args:
        session: Sesión de base de datos
        workspace_id: ID del workspace
        invited_by_user_id: ID del usuario que invita
        email: Email del usuario invitado
        role_id: ID del rol que tendrá al aceptar
        expires_in_days: Días hasta que expire (default: 7)
        message: Mensaje opcional para el invitado
    
    Returns:
        WorkspaceInvitation creada
    """
    from datetime import timedelta
    import secrets
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    invitation = WorkspaceInvitation(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        invited_by_user_id=invited_by_user_id,
        email=email,
        role_id=role_id,
        token=token,
        status="pending",
        expires_at=expires_at,
        message=message,
    )
    session.add(invitation)
    return invitation


def get_invitation_by_token(session: Session, token: str) -> WorkspaceInvitation | None:
    """Obtiene una invitación por su token."""
    return session.query(WorkspaceInvitation).filter_by(token=token).first()


def accept_invitation(
    session: Session,
    invitation_id: str,
    user_id: str,
) -> WorkspaceInvitation:
    """
    Acepta una invitación y crea la membresía del usuario.
    
    Args:
        session: Sesión de base de datos
        invitation_id: ID de la invitación
        user_id: ID del usuario que acepta
    
    Returns:
        WorkspaceInvitation actualizada
    """
    invitation = session.query(WorkspaceInvitation).filter_by(id=invitation_id).first()
    if not invitation:
        raise ValueError("Invitación no encontrada")
    
    if invitation.status != "pending":
        raise ValueError(f"Invitación ya procesada (status: {invitation.status})")
    
    if datetime.utcnow() > invitation.expires_at:
        invitation.status = "expired"
        session.flush()
        raise ValueError("Invitación expirada")
    
    # Verificar límite de usuarios
    allowed, error_msg = check_workspace_limit(session, invitation.workspace_id, "users")
    if not allowed:
        raise ValueError(error_msg)
    
    # Aceptar invitación
    invitation.status = "accepted"
    invitation.accepted_at = datetime.utcnow()
    invitation.accepted_by_user_id = user_id
    
    # Crear membresía
    membership = WorkspaceMembership(
        id=str(uuid.uuid4()),
        workspace_id=invitation.workspace_id,
        user_id=user_id,
        role_id=invitation.role_id,
    )
    session.add(membership)
    
    # Incrementar contador de usuarios
    increment_workspace_counter(session, invitation.workspace_id, "users")
    
    session.flush()
    return invitation


def add_user_to_workspace_helper(
    session: Session,
    user_id: str,
    workspace_id: str,
    role_name: str,
) -> WorkspaceMembership:
    """
    Agrega un usuario a un workspace con un rol específico.
    
    Args:
        session: Sesión de base de datos
        user_id: ID del usuario
        workspace_id: ID del workspace
        role_name: Nombre del rol (ej: "owner", "admin", "creator", "viewer", "approver")
    
    Returns:
        WorkspaceMembership creado o actualizado
    """
    
    # Verificar que el usuario existe
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        raise ValueError(f"Usuario {user_id} no encontrado")
    
    # Verificar que el workspace existe
    workspace = session.query(Workspace).filter_by(id=workspace_id).first()
    if not workspace:
        raise ValueError(f"Workspace {workspace_id} no encontrado")
    
    # Buscar el rol por nombre
    role = session.query(Role).filter_by(name=role_name).first()
    if not role:
        raise ValueError(f"Rol '{role_name}' no encontrado")
    
    # Verificar que no exista ya el membership
    existing = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    
    if existing:
        # Actualizar el role_id si ya existe
        existing.role_id = role.id
        existing.role = role_name  # Mantener para compatibilidad
        return existing
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
        return membership


def list_workspace_invitations(
    session: Session,
    workspace_id: str,
    status: str | None = None,
) -> list[WorkspaceInvitation]:
    """Lista invitaciones de un workspace."""
    query = session.query(WorkspaceInvitation).filter_by(workspace_id=workspace_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(WorkspaceInvitation.created_at.desc()).all()

