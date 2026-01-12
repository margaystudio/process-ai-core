"""
Modelos de datos genéricos para soportar múltiples dominios.

Estos modelos funcionan para cualquier dominio (procesos, recetas, etc.)
usando Workspace/Document genéricos en lugar de Client/Process específicos.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Workspace(Base):
    """
    Workspace genérico (tenant) que puede ser:
    - Una organización/cliente (para procesos)
    - Un usuario individual (para recetas personales)
    - Una comunidad/grupo (para recetas compartidas)
    """
    __tablename__ = "workspaces"

    # Identidad
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))

    # Tipo de workspace
    workspace_type: Mapped[str] = mapped_column(String(20))  # "organization" | "user" | "community"

    # Metadata genérica (JSON flexible)
    # Para organizaciones: business_type, country, language_style, defaults, etc.
    # Para usuarios: preferences, cuisine, diet, etc.
    # Para comunidades: visibility, members_count, etc.
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    documents: Mapped[list["Document"]] = relationship(back_populates="workspace")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")
    folders: Mapped[list["Folder"]] = relationship(back_populates="workspace")
    subscription: Mapped["WorkspaceSubscription | None"] = relationship("WorkspaceSubscription", back_populates="workspace", uselist=False)
    invitations: Mapped[list["WorkspaceInvitation"]] = relationship("WorkspaceInvitation", foreign_keys="WorkspaceInvitation.workspace_id")


class Document(Base):
    """
    Clase base abstracta para documentos.
    
    Usa herencia de tabla unida (Joined Table Inheritance) para permitir que
    Process, Recipe y futuros tipos de documentos hereden campos comunes.
    """
    __tablename__ = "documents"

    # Identidad
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)

    # Tipo de documento (discriminador para polimorfismo)
    document_type: Mapped[str] = mapped_column(String(20))  # "process" | "recipe" | "will" | ...

    # Nombre del documento
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | pending_validation | approved | rejected | archived
    
    # Versión aprobada actual (FK a document_versions)
    # Nota: Esta columna se agregará con la migración migrate_add_validation_tables.py
    # Por ahora, la hacemos opcional para no romper el código existente
    approved_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("document_versions.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Carpeta donde está ubicado el documento (obligatorio)
    folder_id: Mapped[str] = mapped_column(String(36), ForeignKey("folders.id"), nullable=False, index=True)

    # Relaciones
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")
    folder: Mapped["Folder"] = relationship(back_populates="documents")
    runs: Mapped[list["Run"]] = relationship(back_populates="document")
    validations: Mapped[list["Validation"]] = relationship("Validation", foreign_keys="[Validation.document_id]")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", foreign_keys="[AuditLog.document_id]")
    versions: Mapped[list["DocumentVersion"]] = relationship("DocumentVersion", foreign_keys="[DocumentVersion.document_id]")
    approved_version: Mapped["DocumentVersion | None"] = relationship("DocumentVersion", foreign_keys=[approved_version_id], post_update=True)

    # Configuración de herencia polimórfica
    __mapper_args__ = {
        "polymorphic_identity": "document",
        "polymorphic_on": "document_type",
    }


class Process(Document):
    """
    Documento de proceso (hereda de Document).
    
    Representa un proceso operativo o de gestión dentro de una organización.
    """
    __tablename__ = "processes"

    # Hereda id de Document (foreign key)
    id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), primary_key=True)

    # Campos específicos de procesos
    audience: Mapped[str] = mapped_column(String(50), default="")  # "operativo" | "gestion"
    detail_level: Mapped[str] = mapped_column(String(50), default="")  # "breve" | "estandar" | "detallado"
    context_text: Mapped[str] = mapped_column(Text, default="")  # Contexto libre del proceso

    # Configuración de herencia
    __mapper_args__ = {
        "polymorphic_identity": "process",
    }


class Recipe(Document):
    """
    Receta de cocina (hereda de Document).
    
    Representa una receta dentro de un workspace de usuario o comunidad.
    """
    __tablename__ = "recipes"

    # Hereda id de Document (foreign key)
    id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), primary_key=True)

    # Campos específicos de recetas
    cuisine: Mapped[str] = mapped_column(String(50), default="")  # "italian" | "mexican" | ...
    difficulty: Mapped[str] = mapped_column(String(20), default="")  # "easy" | "medium" | "hard"
    servings: Mapped[int] = mapped_column(Integer, default=0)
    prep_time: Mapped[str] = mapped_column(String(50), default="")  # "15 min"
    cook_time: Mapped[str] = mapped_column(String(50), default="")  # "30 min"

    # Configuración de herencia
    __mapper_args__ = {
        "polymorphic_identity": "recipe",
    }


class Folder(Base):
    """
    Carpeta dentro de un workspace para organizar documentos.
    
    Permite crear una estructura jerárquica de carpetas donde se ubican los procesos.
    La información de la carpeta (nombre, path) se puede usar en el prompt para
    inferir el tipo de proceso o sector de la empresa.
    """
    __tablename__ = "folders"

    # Identidad
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    
    # Nombre de la carpeta
    name: Mapped[str] = mapped_column(String(200))
    
    # Path completo de la carpeta (ej: "RRHH/Recursos Humanos" o "Operativo/Depósito")
    # Permite estructura jerárquica
    path: Mapped[str] = mapped_column(String(500), default="")
    
    # Carpeta padre (para estructura jerárquica, opcional)
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("folders.id"), nullable=True, index=True)
    
    # Orden de visualización
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata adicional (JSON flexible)
    # Puede contener: 
    #   - description: Descripción de la carpeta
    #   - prompt_text: Texto para usar en prompts
    #   - permissions: Estructura de permisos (futuro)
    #     {
    #       "allowed_roles": ["admin", "member"],
    #       "allowed_users": ["user_id_1", "user_id_2"],
    #       "denied_users": ["user_id_3"]
    #     }
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    workspace: Mapped["Workspace"] = relationship(back_populates="folders")
    parent: Mapped["Folder | None"] = relationship("Folder", remote_side="Folder.id", back_populates="children")
    children: Mapped[list["Folder"]] = relationship("Folder", back_populates="parent")
    documents: Mapped[list["Document"]] = relationship(back_populates="folder", cascade="all, delete-orphan")


class User(Base):
    """
    Usuario del sistema (autenticación/autorización).
    
    Soporta autenticación local y externa (OAuth/SSO).
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255), default="")  # Para autenticación local
    
    # Autenticación externa (OAuth/SSO)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # ID en el proveedor externo
    auth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True, default="local")  # "local" | "google" | "microsoft" | "okta" | "auth0"
    auth_metadata_json: Mapped[str] = mapped_column(Text, default="{}")  # Tokens, refresh tokens, etc.

    # Metadata del usuario (preferencias, etc.)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    workspace_memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="user")


class Role(Base):
    """
    Rol del sistema (ej: "approver", "creator", "viewer").
    
    Los roles tienen permisos asociados y pueden ser específicos de un tipo de workspace.
    """
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # "owner", "admin", "approver", "creator", "viewer"
    description: Mapped[str] = mapped_column(String(500), default="")
    
    # Tipo de workspace donde aplica (null = global)
    workspace_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "organization" | "user" | "community" | null
    
    # Si es un rol del sistema (no se puede eliminar)
    is_system: Mapped[bool] = mapped_column(default=False)
    
    # Metadata adicional
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
    )
    workspace_memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="role_obj")


class Permission(Base):
    """
    Permiso del sistema (ej: "documents.approve", "documents.create").
    
    Los permisos se agrupan por categoría y se asignan a roles.
    """
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # "documents.approve", "documents.create", etc.
    description: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(50), index=True)  # "documents", "workspaces", "users"
    
    # Metadata adicional
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
    )


class RolePermission(Base):
    """
    Tabla de relación muchos-a-muchos entre Role y Permission.
    """
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(String(36), ForeignKey("permissions.id"), primary_key=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceMembership(Base):
    """
    Relación muchos-a-muchos entre User y Workspace.
    
    Permite que un usuario pertenezca a múltiples workspaces con diferentes roles.
    Ahora usa role_id (FK a Role) en lugar de role (string).
    """
    __tablename__ = "workspace_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    
    # Rol del usuario en el workspace (ahora es FK a Role)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), index=True)
    
    # Mantener role como string para compatibilidad durante migración (se eliminará después)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)  # DEPRECATED: usar role_id

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    user: Mapped["User"] = relationship(back_populates="workspace_memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")
    role_obj: Mapped["Role"] = relationship("Role", foreign_keys=[role_id], back_populates="workspace_memberships")


class Run(Base):
    """
    Ejecución del motor de documentación.
    
    Puede ejecutarse para cualquier tipo de Document (Process, Recipe, etc.)
    gracias al polimorfismo de Document.
    """
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)

    # Tipo de documento (se infiere del documento asociado, pero lo guardamos para queries rápidas)
    document_type: Mapped[str] = mapped_column(String(20))  # "process" | "recipe" | ...

    # Perfil usado (específico del dominio)
    profile: Mapped[str] = mapped_column(String(50), default="")

    # Inputs de la corrida
    input_manifest_json: Mapped[str] = mapped_column(Text, default="{}")

    # Trazabilidad
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    model_text: Mapped[str] = mapped_column(String(100), default="")
    model_transcribe: Mapped[str] = mapped_column(String(100), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Validación asociada (opcional)
    validation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("validations.id"), nullable=True, index=True)
    
    # Indicador de aprobación
    is_approved: Mapped[bool] = mapped_column(default=False, index=True)

    # Relaciones
    document: Mapped["Document"] = relationship(back_populates="runs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="run")
    validation: Mapped["Validation | None"] = relationship("Validation", foreign_keys=[validation_id])


class Artifact(Base):
    """
    Salida generada por una Run.
    """
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), index=True)

    type: Mapped[str] = mapped_column(String(10))  # json|md|pdf
    path: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    run: Mapped["Run"] = relationship(back_populates="artifacts")


class Validation(Base):
    """
    Validación realizada sobre un documento o run.
    
    Permite rastrear el proceso de validación con observaciones,
    checklist ISO-friendly, y estado de aprobación/rechazo.
    """
    __tablename__ = "validations"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("runs.id"), nullable=True, index=True)
    
    # Validador (opcional, para cuando haya autenticación)
    validator_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    
    # Estado de la validación
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    
    # Observaciones del validador
    observations: Mapped[str] = mapped_column(Text, default="")
    
    # Checklist ISO-friendly (JSON estructurado)
    checklist_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relaciones
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id], overlaps="validations")
    run: Mapped["Run | None"] = relationship("Run", foreign_keys=[run_id])
    validator: Mapped["User | None"] = relationship("User", foreign_keys=[validator_user_id])


class AuditLog(Base):
    """
    Registro de auditoría de todas las acciones realizadas sobre documentos.
    
    Proporciona trazabilidad completa: quién hizo qué, cuándo, y qué cambió.
    """
    __tablename__ = "audit_logs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("runs.id"), nullable=True, index=True)
    
    # Usuario que realizó la acción (opcional, para cuando haya autenticación)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    
    # Tipo de acción
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # created | updated | validated | rejected | edited | regenerated | approved
    
    # Entidad relacionada
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # document | run | validation | version
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    
    # Cambios realizados (JSON con diff o descripción)
    changes_json: Mapped[str] = mapped_column(Text, default="{}")
    
    # Metadata adicional (JSON flexible)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id], overlaps="audit_logs")
    run: Mapped["Run | None"] = relationship("Run", foreign_keys=[run_id])
    user: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])


class DocumentVersion(Base):
    """
    Versión aprobada de un documento.
    
    Solo la última versión aprobada (is_current=TRUE) es la "verdad" visible
    para operarios y para RAG. Permite rastrear el historial de versiones.
    """
    __tablename__ = "document_versions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("runs.id"), nullable=True, index=True)
    
    # Número de versión (incremental)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Tipo de contenido
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)  # generated | manual_edit | ai_patch
    
    # Contenido del documento
    content_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON del ProcessDocument
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown renderizado
    
    # Aprobación
    approved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    validation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("validations.id"), nullable=True, index=True)
    
    # Indicador de versión actual
    is_current: Mapped[bool] = mapped_column(default=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id], overlaps="versions")
    run: Mapped["Run | None"] = relationship("Run", foreign_keys=[run_id])
    approver: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by])
    validation: Mapped["Validation | None"] = relationship("Validation", foreign_keys=[validation_id])


class SubscriptionPlan(Base):
    """
    Plan de suscripción disponible en el sistema.
    
    Define los límites y características de cada plan (free, starter, professional, enterprise).
    """
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # "free", "starter", "professional", "enterprise"
    display_name: Mapped[str] = mapped_column(String(100))  # "Free Plan", "Starter Plan", etc.
    description: Mapped[str] = mapped_column(Text, default="")
    
    # Tipo de plan (B2B o B2C)
    plan_type: Mapped[str] = mapped_column(String(20))  # "b2b" | "b2c"
    
    # Precios
    price_monthly: Mapped[float] = mapped_column(Float, default=0.0)
    price_yearly: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Límites del plan (None = ilimitado)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Solo para B2B
    max_documents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_documents_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_storage_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Features habilitadas (JSON)
    features_json: Mapped[str] = mapped_column(Text, default="{}")
    
    # Estado
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Orden de visualización
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    subscriptions: Mapped[list["WorkspaceSubscription"]] = relationship(back_populates="plan")


class WorkspaceSubscription(Base):
    """
    Suscripción activa de un workspace.
    
    Relaciona un workspace con un plan de suscripción y mantiene contadores actuales.
    """
    __tablename__ = "workspace_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), unique=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("subscription_plans.id"), index=True)
    
    # Estado de la suscripción
    status: Mapped[str] = mapped_column(String(20))  # "active" | "trial" | "expired" | "cancelled" | "past_due"
    
    # Período actual
    current_period_start: Mapped[datetime] = mapped_column(DateTime)
    current_period_end: Mapped[datetime] = mapped_column(DateTime)
    
    # Contadores actuales (para validar límites)
    current_users_count: Mapped[int] = mapped_column(Integer, default=0)
    current_documents_count: Mapped[int] = mapped_column(Integer, default=0)
    current_documents_this_month: Mapped[int] = mapped_column(Integer, default=0)
    current_storage_gb: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Metadata de pago
    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "stripe", "paypal", etc.
    payment_provider_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    workspace: Mapped["Workspace"] = relationship("Workspace", foreign_keys=[workspace_id], back_populates="subscription")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")


class WorkspaceInvitation(Base):
    """
    Invitación para unirse a un workspace (B2B).
    
    Permite que admins/superadmins inviten usuarios a unirse a un workspace.
    """
    __tablename__ = "workspace_invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)
    invited_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    
    # Datos de la invitación
    email: Mapped[str] = mapped_column(String(200), index=True)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # Token único para aceptar
    
    # Estado
    status: Mapped[str] = mapped_column(String(20))  # "pending" | "accepted" | "expired" | "cancelled"
    
    # Expiración
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    # Aceptación
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Mensaje opcional
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    workspace: Mapped["Workspace"] = relationship("Workspace", foreign_keys=[workspace_id], overlaps="invitations")
    invited_by: Mapped["User"] = relationship("User", foreign_keys=[invited_by_user_id])
    role: Mapped["Role"] = relationship("Role", foreign_keys=[role_id])
    accepted_by: Mapped["User | None"] = relationship("User", foreign_keys=[accepted_by_user_id])
