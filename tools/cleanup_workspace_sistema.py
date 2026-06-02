#!/usr/bin/env python3
"""
Script de limpieza del workspace "sistema".

En la arquitectura anterior, el workspace con slug='sistema' y workspace_type='system'
era necesario para colgarle la WorkspaceMembership de superadmin al usuario. En la
arquitectura actual, el superadmin se detecta por el claim platform_roles=['superadmin']
del contexto de margay-workspace — sin necesidad de workspace local.

Este script elimina:
  1. Las WorkspaceMembership con rol 'superadmin' colgadas del workspace 'sistema'.
  2. El Workspace con slug='sistema' y workspace_type='system'.

Es IDEMPOTENTE: puede correrse varias veces sin efecto si ya se ejecutó o si el
workspace no existe.

Uso:
    python tools/cleanup_workspace_sistema.py [--dry-run]

    --dry-run  Muestra lo que se eliminaría sin hacer cambios.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace, WorkspaceMembership, Role


def cleanup(dry_run: bool = False) -> None:
    prefix = "[DRY RUN] " if dry_run else ""

    with get_db_session() as session:
        sistema = (
            session.query(Workspace)
            .filter(
                Workspace.slug == "sistema",
                Workspace.workspace_type == "system",
            )
            .first()
        )

        if not sistema:
            print("✅ Workspace 'sistema' no encontrado — nada que limpiar.")
            return

        print(f"🔍 Encontrado workspace 'sistema': id={sistema.id}, name={sistema.name!r}")

        # 1. Obtener memberships del workspace 'sistema'
        memberships = (
            session.query(WorkspaceMembership)
            .filter_by(workspace_id=sistema.id)
            .all()
        )

        if memberships:
            # Resolver nombres de roles para el log
            role_ids = {m.role_id for m in memberships if m.role_id}
            roles_by_id = {}
            if role_ids:
                for role in session.query(Role).filter(Role.id.in_(role_ids)).all():
                    roles_by_id[role.id] = role.name

            for m in memberships:
                role_name = roles_by_id.get(m.role_id) or m.role or "(desconocido)"
                print(
                    f"  {prefix}Eliminando membership: user_id={m.user_id}, "
                    f"role={role_name}"
                )
                if not dry_run:
                    session.delete(m)
        else:
            print("  Sin memberships en workspace 'sistema'.")

        # 2. Eliminar el workspace
        print(f"  {prefix}Eliminando workspace 'sistema' (id={sistema.id})")
        if not dry_run:
            session.delete(sistema)
            session.commit()
            print("✅ Limpieza completada.")
        else:
            print("✅ [DRY RUN] Nada fue eliminado. Re-ejecutá sin --dry-run para aplicar.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra lo que se eliminaría sin hacer cambios reales.",
    )
    args = parser.parse_args()
    cleanup(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
