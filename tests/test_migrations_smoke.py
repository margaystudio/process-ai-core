"""Smoke test de migraciones Alembic (0.1.2).

Verifica que `alembic upgrade head` levanta el schema del módulo desde cero en un
Postgres real. Se ejecuta SOLO si se define la variable de entorno
`ALEMBIC_SMOKE_DATABASE_URL` con una URL de Postgres de prueba; de lo contrario se
saltea (no rompe la suite que corre con SQLite en memoria).

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
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SMOKE_URL = os.getenv("ALEMBIC_SMOKE_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not SMOKE_URL,
    reason="Definí ALEMBIC_SMOKE_DATABASE_URL (Postgres) para correr el smoke de migraciones.",
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
    env = dict(os.environ)
    env["DATABASE_URL"] = SMOKE_URL
    env["DATABASE_SCHEMA"] = schema
    env.setdefault("ENVIRONMENT", "test")
    env.setdefault("PROCESS_AI_BOOTSTRAP", "1")  # evita cargar .env y pisar DATABASE_URL
    return subprocess.run(
        [str(REPO / ".venv" / "bin" / "alembic"), *args],
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
