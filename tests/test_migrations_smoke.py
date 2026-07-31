"""Smoke test de migraciones Alembic (0.1.2).

Verifica que `alembic upgrade head` levanta el schema del módulo **desde cero** en
un Postgres real.

POR QUÉ IMPORTA QUE ESTO CORRA SOLO
-----------------------------------
Este test existía y estaba skippeado salvo que definieras
`ALEMBIC_SMOKE_DATABASE_URL`, una variable que en la práctica no seteaba nadie.
Resultado: el único test que valida la cadena completa nunca corría en local, y
un bug que solo se ve desde una base vacía llegó al CI.

Fue este: la `0022` importaba el inventario VIVO de `db/id_remap.py`, la `0023`
renombró una columna, se actualizó el inventario, y la `0022` —que corre antes,
cuando la columna todavía tiene el nombre viejo— empezó a abortar. Contra una
base ya migrada no se nota **nunca**; desde cero falla siempre.

Ahora cae solo a `TEST_DATABASE_URL` (la base efímera de `tools/dev_db.sh`), así
que corre con el resto de la suite sin configurar nada. `ALEMBIC_SMOKE_DATABASE_URL`
sigue existiendo para apuntarlo a otro lado.

Para no tocar el schema real (`process_ai`) ni el de margay (`workspace`), crea un
schema descartable y único, corre la migración apuntada a él, valida las tablas y
lo elimina al final.

Correr localmente:
    ALEMBIC_SMOKE_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/db" \\
        .venv/bin/pytest tests/test_migrations_smoke.py -v
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Explícita si está; si no, la base efímera de los tests. Solo Postgres: el
#: schema descartable que crea este test no existe en SQLite.
_URL = os.getenv("ALEMBIC_SMOKE_DATABASE_URL") or os.getenv("TEST_DATABASE_URL") or ""
SMOKE_URL = _URL if _URL.startswith("postgresql") else None

pytestmark = pytest.mark.skipif(
    not SMOKE_URL,
    reason=(
        "Se necesita un Postgres. Levantá la base efímera con ./tools/dev_db.sh up "
        "(escribe TEST_DATABASE_URL en .env.test) o definí ALEMBIC_SMOKE_DATABASE_URL."
    ),
)

# Tablas centrales que deben existir tras el baseline.
EXPECTED_TABLES = {
    "workspaces",
    "documents",
    "document_versions",
    "runs",
    "validations",
    "audit_logs",
    "folders",
    "users",
    "alembic_version",
}


def _alembic(args, schema):
    """Corre alembic con el intérprete que está corriendo el test.

    `sys.executable -m alembic` y no `.venv/bin/alembic`: el binario del venv no
    existe en el CI, que instala con `pip install -e` sobre el Python del runner.
    Este test estuvo skippeado desde que se escribió, así que esa ruta hardcodeada
    nunca se ejecutó y el error apareció recién al encenderlo.

    La forma por módulo funciona en los dos lados sin preguntar dónde está nada.
    """
    env = dict(os.environ)
    env["DATABASE_URL"] = SMOKE_URL
    env["DATABASE_SCHEMA"] = schema
    env.setdefault("ENVIRONMENT", "test")
    env.setdefault("PROCESS_AI_BOOTSTRAP", "1")  # evita cargar .env y pisar DATABASE_URL
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )


def _drop_schema(schema):
    from sqlalchemy import create_engine, text

    eng = create_engine(SMOKE_URL)
    with eng.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    eng.dispose()


def test_upgrade_head_creates_module_schema():
    schema = f"process_ai_smoke_{uuid.uuid4().hex[:8]}"
    try:
        res = _alembic(["upgrade", "head"], schema)
        assert res.returncode == 0, f"alembic falló:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"

        from sqlalchemy import create_engine, text

        eng = create_engine(SMOKE_URL)
        with eng.connect() as conn:
            rows = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"),
                {"s": schema},
            ).fetchall()
        eng.dispose()

        names = {r[0] for r in rows}
        missing = EXPECTED_TABLES - names
        assert not missing, f"Faltan tablas tras upgrade head: {missing}"
    finally:
        _drop_schema(schema)


def test_downgrade_base_drops_tables():
    schema = f"process_ai_smoke_{uuid.uuid4().hex[:8]}"
    try:
        up = _alembic(["upgrade", "head"], schema)
        assert up.returncode == 0, up.stderr
        down = _alembic(["downgrade", "base"], schema)
        assert down.returncode == 0, f"downgrade falló:\n{down.stderr}"

        from sqlalchemy import create_engine, text

        eng = create_engine(SMOKE_URL)
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :s AND table_name <> 'alembic_version'"
                ),
                {"s": schema},
            ).fetchall()
        eng.dispose()
        assert not rows, f"Quedaron tablas tras downgrade base: {[r[0] for r in rows]}"
    finally:
        _drop_schema(schema)
