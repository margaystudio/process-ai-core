"""
Modelos de datos genéricos (v2) para soportar múltiples dominios.

Estos modelos reemplazan a Client/Process con Workspace/Document genéricos
que funcionan para cualquier dominio (procesos, recetas, etc.).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text
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


class Document(Base):
    """
    Documento genérico que puede ser:
    - Process (para dominio de procesos)
    - Recipe (para dominio de recetas)
    - Cualquier otro tipo de documento en el futuro
    """
    __tablename__ = "documents"

    # Identidad
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), index=True)

    # Tipo de documento (determina qué dominio usar)
    domain: Mapped[str] = mapped_column(String(20))  # "process" | "recipe"

    # Nombre del documento
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|active|archived

    # Metadata específica del dominio (JSON)
    # Para procesos: process_type, audience, formality, detail_level, etc.
    # Para recetas: cuisine, difficulty, servings, prep_time, cook_time, etc.
    domain_metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    workspace: Mapped["Workspace"] = relationship(back_populates="documents")
    runs: Mapped[list["RunV2"]] = relationship(back_populates="document")


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


class RunV2(Base):
    """
    Ejecución genérica del motor (funciona para cualquier dominio).
    
    Reemplaza a Run, pero ahora referencia Document en lugar de Process.
    """
    __tablename__ = "runs_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)

    # Dominio de esta ejecución
    domain: Mapped[str] = mapped_column(String(20))  # "process" | "recipe"

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
    artifacts: Mapped[list["ArtifactV2"]] = relationship(back_populates="run")


class ArtifactV2(Base):
    """
    Salida generada por una RunV2.
    
    Similar a Artifact, pero referencia RunV2.
    """
    __tablename__ = "artifacts_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs_v2.id"), index=True)

    type: Mapped[str] = mapped_column(String(10))  # json|md|pdf
    path: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    run: Mapped["RunV2"] = relationship(back_populates="artifacts")

