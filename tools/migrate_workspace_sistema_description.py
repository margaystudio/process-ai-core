#!/usr/bin/env python3
"""
Migración: Actualizar workspace "sistema" para usar columna description.

Mueve description de metadata_json a la columna description.

Ejecutar:
    python tools/migrate_workspace_sistema_description.py
"""

import sys
import json
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace


def migrate_sistema_description():
    """Actualiza workspace sistema para usar columna description."""
    with get_db_session() as session:
        print("=" * 70)
        print("  MIGRACIÓN: description en workspace 'sistema'")
        print("=" * 70)
        print()
        
        workspace = session.query(Workspace).filter_by(slug="sistema").first()
        
        if not workspace:
            print("⚠️  Workspace 'sistema' no encontrado.")
            print("   Se creará automáticamente cuando ejecutes create_super_admin.py")
            return
        
        # Si tiene description en metadata_json, moverla a columna
        if workspace.metadata_json and workspace.metadata_json != "{}":
            try:
                meta = json.loads(workspace.metadata_json)
                if "description" in meta and not workspace.description:
                    workspace.description = meta["description"]
                    # Limpiar metadata_json
                    remaining_meta = {k: v for k, v in meta.items() if k != "description"}
                    workspace.metadata_json = json.dumps(remaining_meta) if remaining_meta else "{}"
                    session.commit()
                    print(f"✅ Description migrada: {workspace.description}")
                else:
                    print("ℹ️  Workspace 'sistema' ya tiene description en columna o no hay description en metadata_json")
            except (json.JSONDecodeError, TypeError):
                print("⚠️  metadata_json inválido, saltando...")
        else:
            print("ℹ️  Workspace 'sistema' no tiene metadata_json para migrar")
        
        # Asegurar que description esté establecida
        if not workspace.description:
            workspace.description = "Workspace del sistema para superadmins"
            workspace.metadata_json = "{}"
            session.commit()
            print(f"✅ Description establecida: {workspace.description}")
        
        print()
        print("=" * 70)
        print("  ✅ MIGRACIÓN COMPLETADA")
        print("=" * 70)


if __name__ == "__main__":
    migrate_sistema_description()
