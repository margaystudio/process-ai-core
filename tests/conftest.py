"""Configuración compartida de la suite de tests.

Fix de infraestructura (Tarea 4 — hardening semántico)
------------------------------------------------------
La app modela sus tablas en el schema `process_ai` (`Base.metadata` se construye
con `schema=DATABASE_SCHEMA`, que resuelve a `process_ai` cuando `DATABASE_URL`
apunta a Postgres — el caso normal en dev/test/prod de Margay).

Muchos tests usan **SQLite en memoria** por velocidad y aislamiento. SQLite no
tiene el concepto de schema, así que `Base.metadata.create_all(engine)` fallaba con
`sqlite3.OperationalError: unknown database process_ai`, volteando en cascada tests
que no tienen nada que ver con la capa semántica (los 19 failed + 34 errors).

Solución (sin tocar lógica de negocio): en cada conexión **SQLite** adjuntamos un
database en memoria con ese nombre de schema (`ATTACH DATABASE ':memory:' AS
"process_ai"`), de modo que `process_ai.tabla` resuelva. El listener solo actúa
sobre conexiones `sqlite3` — las conexiones Postgres (smoke de migraciones, etc.)
quedan intactas.
"""

from __future__ import annotations

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine

from process_ai_core.db.database import Base

# Nombre del schema que usa la app (None si DATABASE_URL es SQLite → no hace falta).
_APP_SCHEMA = Base.metadata.schema


@event.listens_for(Engine, "connect")
def _attach_app_schema_on_sqlite(dbapi_connection, connection_record):
    """Adjunta el schema de la app como un database en memoria en cada conexión SQLite."""
    if _APP_SCHEMA and isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.execute(f'ATTACH DATABASE \':memory:\' AS "{_APP_SCHEMA}"')
