"""
Modelos de datos genéricos para soportar múltiples dominios.

Estos modelos funcionan para cualquier dominio (procesos, recetas, etc.)
usando Workspace/Document genéricos en lugar de Client/Process específicos.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
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
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|active|archived

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Carpeta donde está ubicado el documento (obligatorio)
    folder_id: Mapped[str] = mapped_column(String(36), ForeignKey("folders.id"), nullable=False, index=True)

    # Relaciones
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")
    folder: Mapped["Folder"] = relationship(back_populates="documents")
    runs: Mapped[list["Run"]] = relationship(back_populates="document")

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
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255), default="")  # Para autenticación futura

    # Metadata del usuario (preferencias, etc.)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    workspace_memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="user")


class WorkspaceMembership(Base):
    """
    Relación muchos-a-muchos entre User y Workspace.
    
    Permite que un usuario pertenezca a múltiples workspaces con diferentes roles.
    """
    __tablename__ = "workspace_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)

    # Rol del usuario en el workspace
    role: Mapped[str] = mapped_column(String(20))  # "owner" | "admin" | "member" | "viewer"

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    user: Mapped["User"] = relationship(back_populates="workspace_memberships")
    workspace: Mapped["Workspace"] = relationship(back_populates="memberships")


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

    # Relaciones
    document: Mapped["Document"] = relationship(back_populates="runs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="run")


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
