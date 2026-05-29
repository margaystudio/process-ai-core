#!/usr/bin/env python3
"""
Migración: Agregar columna tenant_id a la tabla workspaces.

Esta columna vincula cada Workspace local con el tenant del control plane
(margay-workspace) a través de su ID externo.

Características:
- Nullable: los workspaces previos no tienen tenant_id.
- Unique + índice: permite lookup O(1) en resolve_tenant_workspace_id.

Ejecutar:
    python tools/migrate_add_tenant_id_to_workspaces.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from process_ai_core.db.database import get_db_engine, get_db_session


def migrate():
    engine = get_db_engine()

    with get_db_session() as session:
        print("=" * 70)
        print("  MIGRACIÓN: Agregar tenant_id a workspaces")
        print("=" * 70)
        print()

        inspector = inspect(engine)
        existing_cols = {col["name"] for col in inspector.get_columns("workspaces")}

        if "tenant_id" in existing_cols:
            print("⏭️  Columna 'tenant_id' ya existe. Nada que hacer.")
            return

        print("➕ Agregando columna tenant_id VARCHAR(100) NULL ...")
        session.execute(
            text("ALTER TABLE workspaces ADD COLUMN tenant_id VARCHAR(100) DEFAULT NULL")
        )
        print("✅ Columna agregada.")

        print("➕ Creando índice único ix_workspaces_tenant_id ...")
        session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_workspaces_tenant_id"
                " ON workspaces(tenant_id)"
                " WHERE tenant_id IS NOT NULL"
            )
        )
        print("✅ Índice creado.")
        session.commit()

        print()
        print("=" * 70)
        print("  ✅ MIGRACIÓN COMPLETADA")
        print("=" * 70)


if __name__ == "__main__":
    migrate()
