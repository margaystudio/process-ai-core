#!/usr/bin/env python
"""
Barrido de versiones APROBADAS sin PDF congelado.

POR QUÉ EXISTE
--------------
El PDF congelado es EL artefacto de auditoría: es lo que se sirve, lo que se
hashea y lo que verifica la página pública. Una versión aprobada sin PDF es una
aprobación que el sistema no puede mostrar.

El GET del PDF ya congela bajo demanda, pero eso ata la existencia del artefacto
a que alguien lo mire. Un documento aprobado que nadie abre en seis meses no
tendría artefacto durante seis meses — y su razón de ser es justamente estar
disponible el día que alguien pregunte. Este barrido cierra ese agujero.

Quedan pendientes por dos caminos legítimos:
  - aprobación en lote con `defer_freeze=True` (no congela dentro del request);
  - un freeze que falló al aprobar (evidencia faltante, storage caído).

POR QUÉ COMANDO Y NO TAREA EN PROCESO
-------------------------------------
Se eligió un comando en tools/ y no un scheduler dentro de la app:

  - La API corre en Cloud Run, que apaga las instancias sin tráfico. Un hilo
    programado en proceso no correría justo cuando más falta hace: de noche,
    sin nadie usando el sistema, que es cuando el backlog se acumula.
  - Con N instancias, un scheduler en proceso son N barridos simultáneos. Acá
    eso no rompe nada (`SKIP LOCKED` los reparte), pero es trabajo duplicado
    por diseño en vez de por accidente.
  - Un comando se dispara desde Cloud Scheduler contra un Cloud Run Job, se
    corre a mano cuando algo se ve raro, y se testea sin levantar la API.

USO
---
    python tools/freeze_pending_pdfs.py                    # hasta 50
    python tools/freeze_pending_pdfs.py --limit 200
    python tools/freeze_pending_pdfs.py --dry-run          # solo listar
    python tools/freeze_pending_pdfs.py --workspace <id>   # acotado a un tenant
    python tools/freeze_pending_pdfs.py --loop             # hasta vaciar la cola

Es idempotente y seguro de correr varias veces, en paralelo consigo mismo y en
paralelo con el freeze bajo demanda. Sale con código 1 si alguna falló, para que
un scheduler pueda alertar.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.routes._freeze import count_versions_pending_freeze, freeze_pending_versions
from process_ai_core.db.database import get_db_session

logger = logging.getLogger("freeze_pending")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("USO")[0].strip())
    parser.add_argument("--limit", type=int, default=50, help="máximo por pasada (default 50)")
    parser.add_argument("--workspace", default=None, help="acotar a un workspace")
    parser.add_argument("--dry-run", action="store_true", help="listar sin congelar")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="repetir hasta que no queden pendientes (o hasta que una pasada no avance)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    totales = {"candidatas": 0, "congeladas": 0, "salteadas": 0, "fallidas": 0}
    with get_db_session() as session:
        pendientes = count_versions_pending_freeze(session, args.workspace)
        print(f"Versiones APPROVED sin PDF congelado: {pendientes}")
        if not pendientes:
            return 0

        while True:
            resultado = freeze_pending_versions(
                session,
                limit=args.limit,
                workspace_id=args.workspace,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                for version_id in resultado.get("ids", []):
                    print(f"  pendiente: {version_id}")
                print(f"\n(dry-run: {resultado['candidatas']} candidata(s), no se congeló nada)")
                return 0

            for clave in totales:
                totales[clave] += resultado[clave]
            print(
                f"  pasada: {resultado['congeladas']} congelada(s), "
                f"{resultado['salteadas']} salteada(s), {resultado['fallidas']} fallida(s)"
            )

            # Corta si no quedan, o si la pasada no avanzó: sin esto, un
            # documento que falla siempre —una evidencia que no existe— haría
            # girar el loop para siempre re-intentando lo mismo.
            if not args.loop or resultado["congeladas"] == 0:
                break

        restantes = count_versions_pending_freeze(session, args.workspace)

    print(
        f"\nTotal: {totales['congeladas']} congelada(s), {totales['salteadas']} salteada(s), "
        f"{totales['fallidas']} fallida(s). Quedan {restantes} pendiente(s)."
    )
    if totales["fallidas"]:
        print(
            "\nHay versiones que no se pudieron congelar. Si el número no baja entre\n"
            "corridas, no es backlog: revisá los warnings. Desde que la verificación\n"
            "de integridad aborta el freeze cuando falta una evidencia, la causa más\n"
            "probable es una imagen que ya no está en storage."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
