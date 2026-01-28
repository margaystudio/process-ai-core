# process_ai_core/database.py
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
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

Está pensado para ser **simple, explícito y estable**, evitando configuraciones
mágicas difíciles de depurar, y funcionando bien tanto en desarrollo local
(SQLite) como en entornos productivos (PostgreSQL, MySQL, etc.).

Variables de entorno
--------------------
- DATABASE_URL:
    URL de conexión SQLAlchemy.
    Ejemplos:
      - sqlite:///data/process_ai_core.sqlite
      - postgresql+psycopg://user:pass@host:5432/dbname

Si no se define, se usa por defecto:
    sqlite:///data/process_ai_core.sqlite
"""

# Carga variables de entorno desde .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/process_ai_core.sqlite")

# Si es SQLite en archivo, aseguramos que el directorio exista
if DATABASE_URL.startswith("sqlite:///"):
    db_file = DATABASE_URL.replace("sqlite:///", "", 1)
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

# Engine y SessionLocal se inicializan de forma lazy
_engine = None
SessionLocal = None


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos ORM.

    Todos los modelos SQLAlchemy del proyecto deben heredar de esta clase.
    Permite:
    - Declarar modelos con el estilo Declarative.
    - Centralizar metadata (Base.metadata) para crear/migrar esquemas.
    """
    pass


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Event listener que activa foreign keys en SQLite automáticamente.
    
    Se ejecuta en cada nueva conexión a SQLite, asegurando que
    ON DELETE CASCADE y ON DELETE SET NULL funcionen correctamente.
    """
    if dbapi_conn.__class__.__module__ == "sqlite3":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


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
        _engine = create_engine(
            DATABASE_URL,
            echo=echo,
            future=True,
        )
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