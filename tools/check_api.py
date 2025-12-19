#!/usr/bin/env python3
"""
Script de verificación para diagnosticar problemas con la API.

Ejecutar: python tools/check_api.py
"""

import sys
from pathlib import Path

# Agregar raíz del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("🔍 Verificando dependencias y estructura de la API...\n")

# 1) Verificar dependencias
print("1. Verificando dependencias:")
try:
    import fastapi
    print(f"   ✅ FastAPI {fastapi.__version__}")
except ImportError as e:
    print(f"   ❌ FastAPI no instalado: {e}")
    sys.exit(1)

try:
    import pydantic
    print(f"   ✅ Pydantic {pydantic.__version__}")
except ImportError as e:
    print(f"   ❌ Pydantic no instalado: {e}")
    sys.exit(1)

try:
    import uvicorn
    print(f"   ✅ Uvicorn {uvicorn.__version__}")
except ImportError as e:
    print(f"   ❌ Uvicorn no instalado: {e}")
    sys.exit(1)

# 2) Verificar imports del core
print("\n2. Verificando imports del core:")
try:
    from process_ai_core.config import get_settings
    print("   ✅ process_ai_core.config")
except ImportError as e:
    print(f"   ❌ Error importando core: {e}")
    sys.exit(1)

try:
    from process_ai_core.engine import run_process_pipeline
    print("   ✅ process_ai_core.engine")
except ImportError as e:
    print(f"   ❌ Error importando engine: {e}")
    sys.exit(1)

# 3) Verificar imports de la API
print("\n3. Verificando imports de la API:")
try:
    from api.models.requests import ProcessMode, ProcessRunResponse
    print("   ✅ api.models.requests")
except ImportError as e:
    print(f"   ❌ Error importando models: {e}")
    sys.exit(1)

try:
    from api.routes import process_runs, artifacts
    print("   ✅ api.routes")
except ImportError as e:
    print(f"   ❌ Error importando routes: {e}")
    sys.exit(1)

# 4) Verificar que se puede crear la app
print("\n4. Verificando creación de la app FastAPI:")
try:
    from api.main import app
    print("   ✅ App FastAPI creada correctamente")
    print(f"   ✅ Título: {app.title}")
    print(f"   ✅ Versión: {app.version}")
except Exception as e:
    print(f"   ❌ Error creando app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Todas las verificaciones pasaron. La API debería funcionar correctamente.")
print("\nPara levantar el servidor:")
print("   uvicorn api.main:app --reload --port 8000")

