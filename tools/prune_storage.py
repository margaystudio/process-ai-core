#!/usr/bin/env python3
"""
Prune de artefactos huérfanos en el storage (Fase E3).

Borra del bucket:
  - objetos "flat" del esquema viejo (no bajo workspaces/),
  - runs cuyo registro ya no existe en la BD,
  - documentos cuyo registro ya no existe.

Por seguridad corre en DRY-RUN por default (solo reporta). Para ejecutar de verdad:
    python tools/prune_storage.py --apply
"""

import argparse

from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import prune_orphan_artifacts


def main() -> None:
    ap = argparse.ArgumentParser(description="Prune de artefactos huérfanos del storage.")
    ap.add_argument("--apply", action="store_true", help="Ejecuta el borrado (sin esto: dry-run).")
    args = ap.parse_args()

    with get_db_session() as session:
        summary = prune_orphan_artifacts(session, dry_run=not args.apply)

    print("DRY-RUN (no se borró nada)" if summary["dry_run"] else "APLICADO")
    print(f"  objetos flat (esquema viejo): {summary['flat']}")
    print(f"  runs huérfanos:               {summary['orphan_runs']}")
    print(f"  documentos huérfanos:         {summary['orphan_documents']}")
    if not summary["dry_run"]:
        print(f"  objetos borrados:             {summary['objects_deleted']}")
    if summary["flat_keys_sample"]:
        print("  muestra de flat keys:")
        for k in summary["flat_keys_sample"]:
            print(f"    - {k}")


if __name__ == "__main__":
    main()
