#!/usr/bin/env python3
"""
Migra los logos de marca de los workspaces desde disco local a object storage.

Contexto
--------
Hasta la Fase A el icono se guardaba en `{output_dir}/workspace-branding/{ws}/{archivo}`.
En Cloud Run eso no funciona: el filesystem es efímero y hay varias instancias,
así que el archivo que subió una no existe en la que congela el PDF — el
artefacto oficial se congelaba sin logo, en silencio.

Desde la Fase A la fuente de verdad es object storage, con un camino de
compatibilidad que todavía lee del disco viejo. Este script mueve lo que quedó,
para que ese camino de compatibilidad se pueda retirar.

Uso
---
    python tools/backfill_workspace_logos.py --dry-run     # ver qué haría
    python tools/backfill_workspace_logos.py               # migrar
    python tools/backfill_workspace_logos.py --delete-local # migrar y borrar el origen

`--delete-local` borra el archivo local SOLO después de verificar, releyendo
desde storage, que el blob subido coincide byte a byte con el origen.

Es idempotente: un logo que ya está en storage con el mismo contenido se saltea.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from process_ai_core.config import get_settings  # noqa: E402
from process_ai_core.db.database import get_db_session  # noqa: E402
from process_ai_core.db.models import Workspace  # noqa: E402
from process_ai_core.storage import get_storage, workspace_branding_key  # noqa: E402


def _configured_icon_filename(workspace: Workspace) -> str | None:
    """Nombre del icono según la metadata del workspace (la fuente de verdad)."""
    try:
        metadata = json.loads(workspace.metadata_json) if workspace.metadata_json else {}
    except json.JSONDecodeError:
        return None
    branding = metadata.get("branding")
    if not isinstance(branding, dict):
        return None
    filename = branding.get("client_icon_filename")
    return filename.strip() if isinstance(filename, str) and filename.strip() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="No sube nada; solo reporta.")
    parser.add_argument(
        "--delete-local",
        action="store_true",
        help="Borra el archivo local tras verificar que el blob subido coincide.",
    )
    args = parser.parse_args()

    base = Path(get_settings().output_dir) / "workspace-branding"
    storage = get_storage()

    subidos = salteados = faltantes = huerfanos = errores = 0

    with get_db_session() as session:
        workspaces = session.query(Workspace).all()
        # Se itera por workspace y no por archivos del disco: el archivo que
        # importa es el que la metadata declara. Un archivo suelto en el disco
        # que nadie referencia es basura de un reemplazo anterior.
        configurados = {ws.id: _configured_icon_filename(ws) for ws in workspaces}

    for workspace_id, filename in sorted(configurados.items()):
        if not filename:
            continue

        key = workspace_branding_key(workspace_id, filename)
        local = base / workspace_id / filename

        try:
            if not local.exists():
                # Puede estar ya en storage (subido después de la Fase A).
                if storage.exists(key):
                    salteados += 1
                    print(f"  ok     {workspace_id}/{filename} — ya está en storage")
                else:
                    faltantes += 1
                    print(
                        f"  FALTA  {workspace_id}/{filename} — no está ni en disco ni en "
                        "storage. Ese workspace va a generar PDFs sin logo; hay que "
                        "volver a subirlo desde la UI."
                    )
                continue

            data = local.read_bytes()
            sha_local = hashlib.sha256(data).hexdigest()

            if storage.exists(key):
                if hashlib.sha256(storage.get(key)).hexdigest() == sha_local:
                    salteados += 1
                    print(f"  ok     {workspace_id}/{filename} — ya migrado (mismo contenido)")
                    if args.delete_local and not args.dry_run:
                        local.unlink()
                        print("         local borrado")
                    continue
                print(f"  DIFF   {workspace_id}/{filename} — storage tiene otro contenido; se sobreescribe")

            if args.dry_run:
                print(f"  [dry]  subiría {workspace_id}/{filename} → {key} ({len(data)} bytes)")
                subidos += 1
                continue

            storage.put(key, data, content_type=_media_type(filename))

            # Releer para confirmar antes de tocar el origen.
            if hashlib.sha256(storage.get(key)).hexdigest() != sha_local:
                errores += 1
                print(f"  ERROR  {workspace_id}/{filename} — el blob subido no coincide; NO se borra el local")
                continue

            subidos += 1
            print(f"  subido {workspace_id}/{filename} → {key} ({len(data)} bytes)")
            if args.delete_local:
                local.unlink()
                print("         local borrado")

        except Exception as exc:
            errores += 1
            print(f"  ERROR  {workspace_id}/{filename}: {exc}")

    # Archivos en disco que ninguna metadata referencia.
    if base.exists():
        referenciados = {
            (ws_id, fn) for ws_id, fn in configurados.items() if fn
        }
        for path in base.glob("*/*"):
            if path.is_file() and (path.parent.name, path.name) not in referenciados:
                huerfanos += 1
                print(f"  huérfano (no referenciado por ninguna metadata): {path}")

    print(
        f"\nResumen: {subidos} subidos, {salteados} ya estaban, {faltantes} sin origen, "
        f"{huerfanos} huérfanos, {errores} errores."
    )
    if faltantes:
        print(
            "Los 'sin origen' hay que resubirlos desde la UI: el archivo se perdió "
            "con el filesystem efímero de la instancia que lo recibió."
        )
    return 1 if errores else 0


def _media_type(filename: str) -> str:
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".svg": "image/svg+xml",
    }.get(Path(filename).suffix.lower(), "application/octet-stream")


if __name__ == "__main__":
    raise SystemExit(main())
