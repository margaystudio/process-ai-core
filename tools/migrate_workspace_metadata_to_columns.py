#!/usr/bin/env python3
"""
Migración: Mover campos comunes de metadata_json a columnas en Workspace.

Esta migración:
1. Lee metadata_json de cada workspace
2. Extrae campos comunes: country, business_type, language_style, default_audience, default_detail_level, context_text
3. Los mueve a columnas dedicadas
4. Limpia metadata_json dejando solo campos opcionales

Ejecutar:
    python tools/migrate_workspace_metadata_to_columns.py
"""

import sys
import json
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace


def migrate_workspace_metadata():
    """Migra campos comunes de metadata_json a columnas."""
    with get_db_session() as session:
        print("=" * 70)
        print("  MIGRACIÓN: metadata_json → Columnas en Workspace")
        print("=" * 70)
        print()
        
        # Campos a migrar
        fields_to_migrate = [
            "country",
            "business_type",
            "language_style",
            "default_audience",
            "default_detail_level",
            "context_text",
        ]
        
        workspaces = session.query(Workspace).all()
        migrated_count = 0
        skipped_count = 0
        
        print(f"📊 Encontrados {len(workspaces)} workspaces")
        print()
        
        for workspace in workspaces:
            if not workspace.metadata_json or workspace.metadata_json == "{}":
                skipped_count += 1
                continue
            
            try:
                meta = json.loads(workspace.metadata_json)
            except (json.JSONDecodeError, TypeError):
                print(f"⚠️  Workspace {workspace.slug}: metadata_json inválido, saltando...")
                skipped_count += 1
                continue
            
            # Verificar si hay campos para migrar
            has_fields_to_migrate = any(field in meta for field in fields_to_migrate)
            if not has_fields_to_migrate:
                skipped_count += 1
                continue
            
            # Migrar campos comunes a columnas
            updated = False
            for field in fields_to_migrate:
                if field in meta:
                    value = meta[field]
                    # Solo actualizar si la columna está vacía (no sobrescribir datos existentes)
                    current_value = getattr(workspace, field, None)
                    if not current_value and value:
                        setattr(workspace, field, value)
                        updated = True
            
            if updated:
                # Limpiar metadata_json: remover campos migrados
                remaining_meta = {
                    k: v for k, v in meta.items()
                    if k not in fields_to_migrate
                }
                workspace.metadata_json = json.dumps(remaining_meta) if remaining_meta else "{}"
                migrated_count += 1
                print(f"✅ {workspace.slug}: Migrados campos a columnas")
            else:
                skipped_count += 1
        
        session.commit()
        
        print()
        print("=" * 70)
        print("  ✅ MIGRACIÓN COMPLETADA")
        print("=" * 70)
        print()
        print(f"📊 Resumen:")
        print(f"  - Workspaces migrados: {migrated_count}")
        print(f"  - Workspaces sin cambios: {skipped_count}")
        print(f"  - Total: {len(workspaces)}")
        print()
        print("💡 Los campos ahora están en columnas dedicadas:")
        print("  - country, business_type, language_style")
        print("  - default_audience, default_detail_level, context_text")
        print()
        print("💡 metadata_json ahora solo contiene campos opcionales")


if __name__ == "__main__":
    migrate_workspace_metadata()
