"""Modelo `DocumentType` — entidad de tipos documentales por-tenant.

Ver docs/PLAN_DOCUMENT_TYPES.md. Reemplaza el dominio `document_type` de
`catalog_option` (global) por filas propias de cada workspace. `Document.document_type`
sigue guardando el string `key`; la resolución es soft por `(workspace_id, key)`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class DocumentType(Base):
    __tablename__ = "document_type"
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_document_type_workspace_key"),
        Index("ix_document_type_workspace", "workspace_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=False, index=True
    )

    # Slug estable referenciado por Document.document_type. No cambia al editar el label.
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    # Texto inyectado al prompt de generación de este tipo.
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Toggles de comportamiento (allowlist en domains.document_types.BEHAVIOR_KEYS).
    behaviors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 'default' (sembrado) | 'custom' (creado por el tenant).
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="custom")

    # Identidad visual (seleccionable por el tenant).
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
