# process_ai_core/database.py
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

"""
process_ai_core.database
========================

Capa de infraestructura para acceso a base de datos usando SQLAlchemy.

Este módulo centraliza:
- La carga de la URL de base de datos desde variables de entorno.
- La creación lazy (perezosa) del engine y del sessionmaker.
- Un context manager seguro para manejar sesiones (commit / rollback).

Está pensado para usar **PostgreSQL** (schema `process_ai` en el proyecto Supabase de Margay).
SQLite en archivo ya no se usa; solo `:memory:` en tests unitarios.

Variables de entorno
--------------------
- DATABASE_URL:
    URL de conexión SQLAlchemy (PostgreSQL / Supabase pooler).
    Ejemplo:
      postgresql+psycopg://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?prepare_threshold=0
- DATABASE_SCHEMA:
    Schema Postgres del módulo (default: `process_ai`).
"""

# Carga .env desde la raíz del repo (uvicorn --reload no pasa por run_api.py).
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")
load_dotenv(_project_root / ".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def _resolve_database_schema(url: str) -> str | None:
    """Schema Postgres del módulo. None solo para SQLite :memory: en tests."""
    if url.startswith("sqlite"):
        return None
    schema = os.getenv("DATABASE_SCHEMA", "process_ai").strip()
    if not schema:
        raise RuntimeError("DATABASE_SCHEMA no puede estar vacío con PostgreSQL.")
    return schema


def _validate_database_url(url: str) -> None:
    if not url:
        raise RuntimeError(
            "DATABASE_URL es obligatorio. "
            "Usá PostgreSQL del proyecto Supabase de Margay (schema process_ai). "
            "Ver docs/DB_SETUP_FROM_SCRATCH.md"
        )

    if url.startswith("sqlite:///") and ":memory:" not in url:
        raise RuntimeError(
            "SQLite en archivo ya no se usa. "
            "Configurá DATABASE_URL con PostgreSQL (Supabase). "
            "Ver docs/DB_SETUP_FROM_SCRATCH.md"
        )

    env = os.getenv("ENVIRONMENT", "local").lower()
    if env in {"prod", "production", "test"} and url.startswith("sqlite"):
        raise RuntimeError(
            f"DATABASE_URL no puede ser SQLite en ambiente '{env}'. "
            "Configurá PostgreSQL (Supabase, schema process_ai)."
        )


_validate_database_url(DATABASE_URL)
DATABASE_SCHEMA = _resolve_database_schema(DATABASE_URL)

# Engine y SessionLocal se inicializan de forma lazy
_engine = None
SessionLocal = None


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos ORM.

    Todos los modelos SQLAlchemy del proyecto deben heredar de esta clase.
    En PostgreSQL las tablas viven en el schema `process_ai` (o DATABASE_SCHEMA).
    """
    metadata = MetaData(schema=DATABASE_SCHEMA) if DATABASE_SCHEMA else MetaData()


@event.listens_for(Engine, "connect")
def configure_connection(dbapi_conn, connection_record):
    """SQLite: FK en tests."""
    if dbapi_conn.__class__.__module__ == "sqlite3":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def warmup_db_pool() -> None:
    """Precalienta el pool al arrancar (evita cold connect de varios segundos)."""
    if not DATABASE_URL.startswith("postgresql"):
        return
    from sqlalchemy import text

    engine = get_db_engine(echo=False)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def get_db_engine(echo: bool = False):
    """
    Devuelve (y crea si no existe) el SQLAlchemy Engine global.

    El engine se inicializa solo una vez (singleton simple a nivel de módulo)
    para evitar múltiples conexiones innecesarias.

    Parameters
    ----------
    echo:
        Si True, SQLAlchemy loguea todas las queries SQL ejecutadas.
        Útil para debugging; normalmente False en producción.

    Returns
    -------
    sqlalchemy.Engine
        Engine configurado con la DATABASE_URL.
    """
    global _engine, SessionLocal

    if _engine is None:
        env = os.getenv("ENVIRONMENT", "local").lower()
        pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "false" if env == "local" else "true").lower() == "true"
        pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))

        engine_kwargs: dict = {
            "echo": echo,
            "future": True,
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_recycle": 300,
        }
        if DATABASE_URL.startswith("postgresql"):
            engine_kwargs["pool_pre_ping"] = pool_pre_ping
            engine_kwargs["connect_args"] = {"prepare_threshold": None}
        _engine = create_engine(DATABASE_URL, **engine_kwargs)
        SessionLocal = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

    return _engine


@contextmanager
def get_db_session():
    """
    Context manager para manejar una sesión de base de datos.

    Garantiza:
    - Apertura correcta de la sesión.
    - Commit automático si no hay errores.
    - Rollback automático ante cualquier excepción.
    - Cierre de la sesión al final del bloque.

    Uso recomendado
    ---------------
    >>> from process_ai_core.database import get_db_session
    >>> with get_db_session() as session:
    ...     session.add(obj)
    ...     session.query(Model).all()

    Y NO:
    - crear sesiones manualmente
    - olvidar cerrar sesiones
    - manejar commits/rollbacks a mano en cada función

    Yields
    ------
    sqlalchemy.orm.Session
        Sesión activa lista para usar.
    """
    # Asegura que el engine y SessionLocal estén inicializados
    get_db_engine(echo=False)

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()