"""Configuración compartida de la suite de tests.

A qué base apuntan los tests
----------------------------
19 de los 53 archivos de test usan `get_db_session()` — la sesión real de la app —
y por lo tanto la `DATABASE_URL` del `.env`. Si esa URL es el Supabase sandbox
COMPARTIDO, la suite tarda ~21 min con solo 48 s de CPU real (el 96 % es espera de
red: 240 ms de RTT y ~3,7 s por conexión nueva contra eu-central-1) y su churn de
conexiones satura el pooler, rompiendo los tests de los otros módulos.

Lo recomendado es un Postgres efímero local:

    ./tools/dev_db.sh up     # levanta, migra y escribe .env.test
    .venv/bin/pytest         # conftest lee .env.test solo

`TEST_DATABASE_URL` en el entorno siempre gana sobre `.env.test`. Tu `.env` no se
toca nunca: si no definís ninguna de las dos, todo sigue funcionando como antes
(con una advertencia si detectamos que estás apuntando a una base compartida).

Ver `knowledge/12-testing.md` del repo margay-dev-agent.

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

import os
import pathlib
import sqlite3

from dotenv import load_dotenv

_RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _cargar_env_test() -> None:
    """Lee `.env.test` (lo escribe `tools/dev_db.sh up`) si no hay env var.

    Evita tener que hacer `export TEST_DATABASE_URL=...` en cada terminal nueva.
    La env var explícita siempre gana. El archivo está gitignoreado.
    """
    if os.getenv("TEST_DATABASE_URL"):
        return
    archivo = _RAIZ / ".env.test"
    if not archivo.exists():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _apuntar_a_la_base_de_tests() -> None:
    """Impone `TEST_DATABASE_URL` como `DATABASE_URL` **antes** de importar la app.

    `process_ai_core.db.database` lee `DATABASE_URL` y arma `Base.metadata` en el
    momento del import, así que esto tiene que pasar antes. Cargamos el `.env` acá
    nosotros para que el resto de las variables (OpenAI, Supabase, workspace…) sigan
    disponibles, y recién después pisamos la URL; `PROCESS_AI_BOOTSTRAP=1` evita que
    el módulo vuelva a cargar el `.env` y nos la pise de nuevo (`.env.local` se carga
    con `override=True`).
    """
    url_tests = os.getenv("TEST_DATABASE_URL")
    if not url_tests:
        return

    load_dotenv(_RAIZ / ".env")
    load_dotenv(_RAIZ / ".env.local", override=True)

    os.environ["DATABASE_URL"] = url_tests
    os.environ["PROCESS_AI_BOOTSTRAP"] = "1"
    # Postgres directo (sin PgBouncer): se pueden reusar prepared statements, que
    # vale ~2× por query. Contra el pooler de Supabase en modo transaction esto
    # DEBE quedar deshabilitado — de ahí que el default de la app sea `None`.
    os.environ.setdefault("DB_PREPARE_THRESHOLD", "5")


def _es_base_compartida(url: str) -> bool:
    if os.getenv("TEST_DATABASE_URL"):
        return False
    return "supabase" in url.lower() or "pooler" in url.lower()


_cargar_env_test()
_apuntar_a_la_base_de_tests()

from sqlalchemy import event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from process_ai_core.db.database import DATABASE_URL, Base  # noqa: E402


_BANNER_BASE_COMPARTIDA = (
    "",
    "  ┌──────────────────────────────────────────────────────────────────┐",
    "  │  Los tests apuntan al Supabase COMPARTIDO.                       │",
    "  │                                                                  │",
    "  │  La suite va a tardar ~21 min (el 96 % es espera de red) y su    │",
    "  │  churn de conexiones satura el pooler, rompiendo los tests de    │",
    "  │  los otros módulos.                                              │",
    "  │                                                                  │",
    "  │      ./tools/dev_db.sh up      →  la suite baja a ~55 s          │",
    "  └──────────────────────────────────────────────────────────────────┘",
    "",
)


def pytest_sessionstart(session) -> None:
    """Avisa arriba de todo si la suite quedó apuntando a una base compartida.

    Escribe por el terminal reporter y no con `print`/`warnings.warn` por dos
    motivos: el conftest se importa dentro de la captura de pytest (una salida
    directa se traga salvo con `-s`), y `pytest_report_header` no se muestra con
    `-q`, que es justo como se corre la suite casi siempre.
    """
    if not _es_base_compartida(DATABASE_URL):
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:  # -p no:terminal
        return
    for linea in _BANNER_BASE_COMPARTIDA:
        reporter.write_line(linea)

# Nombre del schema que usa la app (None si DATABASE_URL es SQLite → no hace falta).
_APP_SCHEMA = Base.metadata.schema


@event.listens_for(Engine, "connect")
def _attach_app_schema_on_sqlite(dbapi_connection, connection_record):
    """Adjunta el schema de la app como un database en memoria en cada conexión SQLite."""
    if _APP_SCHEMA and isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.execute(f'ATTACH DATABASE \':memory:\' AS "{_APP_SCHEMA}"')
