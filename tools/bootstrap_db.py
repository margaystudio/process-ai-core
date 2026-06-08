#!/usr/bin/env python3
"""
Bootstrap del schema process_ai en un proyecto Supabase (sandbox o prod).

Carga variables desde .env.production / .env.test / .env.local|.env ANTES de importar
la capa de DB (database.py también lee .env al importar; este script fuerza el archivo
correcto con override=True).

Uso:
  cp .env.production.example .env.production   # completar DATABASE_URL
  python tools/bootstrap_db.py --env prod

Opcional: pegar migrations/001_create_schema.sql en Supabase SQL Editor y luego:
  python tools/bootstrap_db.py --env prod --skip-schema-sql
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION_SQL = ROOT / "migrations" / "001_create_schema.sql"


def _load_env(target: str) -> None:
    from dotenv import load_dotenv

    if target == "prod":
        path = ROOT / ".env.production"
        if not path.exists():
            print(
                "❌ Falta .env.production\n"
                "   cp .env.production.example .env.production\n"
                "   Completá DATABASE_URL (pooler :6543, ref mqldatizgvmjqisuqabv).",
                file=sys.stderr,
            )
            sys.exit(1)
        load_dotenv(path, override=True)
        os.environ["ENVIRONMENT"] = "production"
        os.environ["PROCESS_AI_BOOTSTRAP"] = "1"
    elif target == "test":
        path = ROOT / ".env.test"
        if not path.exists():
            print("❌ Falta .env.test (copiá desde .env.example)", file=sys.stderr)
            sys.exit(1)
        load_dotenv(path, override=True)
        os.environ["ENVIRONMENT"] = "test"
        os.environ["PROCESS_AI_BOOTSTRAP"] = "1"
    else:
        for name in (".env.local", ".env"):
            p = ROOT / name
            if p.exists():
                load_dotenv(p, override=True)
        os.environ.setdefault("ENVIRONMENT", "local")
        os.environ["PROCESS_AI_BOOTSTRAP"] = "1"

    if not os.getenv("DATABASE_URL", "").strip():
        print("❌ DATABASE_URL vacío después de cargar el .env", file=sys.stderr)
        sys.exit(1)


def _run_schema_sql(engine) -> None:
    from sqlalchemy import text

    if not MIGRATION_SQL.exists():
        print(f"⚠️  No encontré {MIGRATION_SQL}, saltando SQL de grants")
        return

    raw = MIGRATION_SQL.read_text(encoding="utf-8")
    statements = [
        s.strip()
        for s in raw.split(";")
        if s.strip() and not all(line.strip().startswith("--") or not line.strip() for line in s.splitlines())
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    print(f"✅ SQL de schema aplicado ({MIGRATION_SQL.name})")


def _run_seeds() -> None:
    from tools.seed_catalogs import main as seed_catalogs_main
    from tools.seed_permissions import seed_permissions
    from tools.seed_subscription_plans import seed_plans

    seed_permissions()
    seed_plans()
    seed_catalogs_main()
    print("✅ Seeds (permisos, planes, catálogos) aplicados")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap schema process_ai + tablas + seeds")
    parser.add_argument(
        "--env",
        choices=["local", "test", "prod"],
        required=True,
        help="prod → .env.production | test → .env.test | local → .env.local / .env",
    )
    parser.add_argument(
        "--skip-schema-sql",
        action="store_true",
        help="No ejecutar migrations/001_create_schema.sql (si ya lo pegaste en SQL Editor)",
    )
    parser.add_argument(
        "--skip-seeds",
        action="store_true",
        help="Solo schema + tablas, sin seeds",
    )
    args = parser.parse_args()

    _load_env(args.env)

    # Importar después de cargar .env
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import text

    from process_ai_core.db.database import DATABASE_SCHEMA, get_db_engine
    from process_ai_core.db.models import (  # noqa: F401
        Artifact,
        Document,
        Folder,
        Process,
        Recipe,
        Run,
        User,
        Workspace,
        WorkspaceMembership,
    )
    from process_ai_core.db.models_catalog import CatalogOption  # noqa: F401
    from process_ai_core.db.database import Base

    ref = os.getenv("DATABASE_URL", "")
    if "mqldatizgvmjqisuqabv" in ref:
        label = "PROD (mqldatizgvmjqisuqabv)"
    elif "nbigcpjmckewuhrqjzrt" in ref:
        label = "SANDBOX (nbigcpjmckewuhrqjzrt)"
    else:
        label = "otro proyecto"

    print(f"🔧 Bootstrap — ambiente={args.env} — {label}")
    print(f"   schema={DATABASE_SCHEMA or '(default)'}")

    engine = get_db_engine(echo=False)

    if not args.skip_schema_sql:
        _run_schema_sql(engine)

    with engine.begin() as conn:
        if DATABASE_SCHEMA:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DATABASE_SCHEMA}"'))
    Base.metadata.create_all(bind=engine)
    print(f"✅ Tablas creadas/verificadas en schema '{DATABASE_SCHEMA or 'public'}'")

    if not args.skip_seeds:
        _run_seeds()

    print("🎉 Listo.")


if __name__ == "__main__":
    main()
