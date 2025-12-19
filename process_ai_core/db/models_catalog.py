from __future__ import annotations

from sqlalchemy import String, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class CatalogOption(Base):
    """
    Catálogo de opciones parametrizables (modelo A: guardamos value en Workspace/Document).

    domain: el "campo" al que pertenece
      ej: "business_type", "audience", "detail_level", "formality", "process_type", "language_style"

    value: lo que se guarda en Workspace/Document metadata_json
      ej: "operativo", "gestion", "alto", "bajo", "rrhh"

    label: texto para UI (lo que ve el usuario)
    prompt_text: texto que se inyecta al prompt (lo que interpreta el modelo)
    """
    __tablename__ = "catalog_option"
    __table_args__ = (
        UniqueConstraint("domain", "value", name="uq_catalog_domain_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    domain: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(50), nullable=False)

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_text: Mapped[str] = mapped_column(String(2000), nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)