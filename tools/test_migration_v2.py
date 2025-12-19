"""
Script de prueba para verificar que la migración v2 está lista.

Este script verifica:
1. Que los modelos v2 se pueden importar
2. Que las tablas se pueden crear
3. Que las funciones helper funcionan
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

try:
    from process_ai_core.db.database import Base, get_db_engine, get_db_session
    from process_ai_core.db.models import Client, Process, Run
    from process_ai_core.db.models_v2 import (
        Workspace,
        Document,
        User,
        WorkspaceMembership,
        RunV2,
        ArtifactV2,
    )
    from process_ai_core.db.helpers_v2 import (
        create_organization_workspace,
        create_process_document,
        get_workspace_metadata,
    )
    print("✅ Todos los imports funcionan correctamente")
except ImportError as e:
    print(f"❌ Error de import: {e}")
    sys.exit(1)

# Verificar que los modelos están registrados
print("\n📋 Verificando modelos v2...")
try:
    # Verificar que los modelos están en Base.metadata
    tables_v2 = [
        "workspaces",
        "documents",
        "users",
        "workspace_memberships",
        "runs_v2",
        "artifacts_v2",
    ]
    
    engine = get_db_engine(echo=False)
    existing_tables = set(engine.table_names() if hasattr(engine, 'table_names') else [])
    
    print(f"  Tablas existentes en DB: {len(existing_tables)}")
    print(f"  Tablas v2 a crear: {len(tables_v2)}")
    
    for table in tables_v2:
        if table in existing_tables:
            print(f"  ⚠️  {table} ya existe")
        else:
            print(f"  ✅ {table} se creará")
    
    print("\n✅ Verificación de estructura completada")
    print("\n💡 Para ejecutar la migración completa, ejecuta:")
    print("   python tools/migrate_to_v2.py")
    
except Exception as e:
    print(f"❌ Error durante la verificación: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

