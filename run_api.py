#!/usr/bin/env python3
"""
Script helper para ejecutar la API FastAPI.
Ejecuta desde la raíz del proyecto para asegurar que Python encuentre el módulo 'api'.
"""

import sys
import os
from pathlib import Path

# Asegurar que el directorio raíz esté en el PYTHONPATH
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Intentar activar el venv si existe
venv_path = project_root / ".venv"
if venv_path.exists():
    venv_site_packages = venv_path / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if venv_site_packages.exists() and str(venv_site_packages) not in sys.path:
        sys.path.insert(0, str(venv_site_packages))

if __name__ == "__main__":
    try:
        import uvicorn
        print("🚀 Iniciando API FastAPI en http://localhost:8000")
        print("📖 Documentación disponible en http://localhost:8000/docs")
        uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
    except ImportError as e:
        print(f"❌ Error: No se pudo importar uvicorn. ¿Activaste el venv?")
        print(f"   Ejecuta: source .venv/bin/activate")
        print(f"   Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al iniciar el servidor: {e}")
        sys.exit(1)

