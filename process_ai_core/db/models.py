from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Client(Base):
    """
    Cliente / organización (tenant).

    Guarda defaults que luego se usan para armar el prompt:
    - estilo de idioma
    - audiencia por defecto (pistero / operativo / gestión)
    - nivel de detalle por defecto
    - formalidad por defecto
    - contexto libre del negocio

    Importante:
    - En este MVP guardamos "value" del catálogo (modelo A).
      Ej: default_audience="operativo" y el texto de prompt sale de catalog_option.
    """
    __tablename__ = "clients"

    # Identidad
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # "gpu", "acme", etc.
    name: Mapped[str] = mapped_column(String(200))

    # Defaults / contexto (alineado al MER)
    country: Mapped[str] = mapped_column(String(2), default="UY")  # ISO2, ej UY/AR/CL
    business_type: Mapped[str] = mapped_column(String(50), default="")  # catalog: business_type
    language_style: Mapped[str] = mapped_column(String(50), default="es_uy_formal")  # catalog: language_style

    default_audience: Mapped[str] = mapped_column(String(50), default="operativo")   # catalog: audience
    default_formality: Mapped[str] = mapped_column(String(50), default="media")      # catalog: formality
    default_detail_level: Mapped[str] = mapped_column(String(50), default="estandar")# catalog: detail_level

    # Contexto libre: "qué hace la empresa", sistemas típicos, jerga interna, etc.
    context_text: Mapped[str] = mapped_column(Text, default="")

    # Flex: para preferencias futuras sin migrar todo (lo mantenemos)
    prefs_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    processes: Mapped[list["Process"]] = relationship(back_populates="client")


class Process(Base):
    """
    Proceso dentro de un cliente.

    Puede heredar defaults del cliente o sobrescribirlos.
    Ej:
    - un proceso "operativo" (colgar el pico) => audience=operativo, detail_level=bajo
    - un proceso RRHH => audience=gestion, detail_level=alto, formality=alta
    """
    __tablename__ = "processes"

    # Identidad
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(String(36), ForeignKey("clients.id"), index=True)

    # Metadatos básicos
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")  # breve descripción
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|active|archived (ejemplo)

    # Atributos del proceso (MER) — guardamos VALUE del catálogo
    process_type: Mapped[str] = mapped_column(String(50), default="")   # catalog: process_type (operativo/rrhh/it/etc)

    # Overrides por proceso (si vacío => usa defaults del cliente)
    audience: Mapped[str] = mapped_column(String(50), default="")       # catalog: audience
    formality: Mapped[str] = mapped_column(String(50), default="")      # catalog: formality
    detail_level: Mapped[str] = mapped_column(String(50), default="")   # catalog: detail_level

    # Preferencias libres por proceso (si querés guardar flags sin tocar schema)
    preferences_json: Mapped[str] = mapped_column(Text, default="{}")

    # Contexto específico del proceso (ej: “se hace en Cloud Run, job GPU ETL Job”)
    context_text: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    client: Mapped["Client"] = relationship(back_populates="processes")
    runs: Mapped[list["Run"]] = relationship(back_populates="process")


class Run(Base):
    """
    Una ejecución/corrida del motor para generar un documento.

    Guarda:
    - manifest de inputs (qué archivos entraron, ids, metadata)
    - modelos usados (text/transcribe)
    - hash del prompt (para trazabilidad / caching)
    - perfil de salida (mode) si querés distinguir "operativo vs gestión"
    """
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    process_id: Mapped[str] = mapped_column(String(36), ForeignKey("processes.id"), index=True)

    # Perfil de salida (podés mapearlo luego a catálogo si querés)
    mode: Mapped[str] = mapped_column(String(20), default="operativo")  # operativo|gestion (por ahora)

    # Inputs de la corrida
    input_manifest_json: Mapped[str] = mapped_column(Text, default="{}")

    # Trazabilidad del prompt/modelos
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    model_text: Mapped[str] = mapped_column(String(100), default="")
    model_transcribe: Mapped[str] = mapped_column(String(100), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    process: Mapped["Process"] = relationship(back_populates="runs")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="run")


class Artifact(Base):
    """
    Salida generada por una Run.

    type: json | md | pdf
    path: ruta en disco (por ahora). A futuro podría ser un storage (S3/GCS).
    """
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), index=True)

    type: Mapped[str] = mapped_column(String(10))  # json|md|pdf
    path: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    run: Mapped["Run"] = relationship(back_populates="artifacts")