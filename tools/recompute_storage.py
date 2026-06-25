#!/usr/bin/env python3
"""
Reconciliación de contabilidad de storage (Fase E2).

Recalcula `current_storage_gb` de todos los workspaces con suscripción, sumando el
uso real en el bucket por prefijo `workspaces/{ws}/`. Útil como tarea de mantenimiento
o cron (la contabilidad también se actualiza best-effort en cada generación/aprobación).

Uso:
    python tools/recompute_storage.py
"""

from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import recompute_all_workspaces_storage


def main() -> None:
    with get_db_session() as session:
        result = recompute_all_workspaces_storage(session)
    if not result:
        print("No hay workspaces con suscripción para recalcular.")
        return
    print(f"Recalculados {len(result)} workspaces:")
    for ws_id, gb in sorted(result.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {ws_id}: {gb:.6f} GB")


if __name__ == "__main__":
    main()
