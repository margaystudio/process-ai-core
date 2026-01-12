#!/usr/bin/env python3
"""
Script cross-platform para ejecutar la API en diferentes ambientes.

Uso:
    python run_api.py [local|test|prod]

Este script reemplaza los scripts .sh pero los mantiene para compatibilidad.
Funciona en Mac, Linux y Windows.
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def load_env_file(env_file: str) -> bool:
    """Carga un archivo .env si existe."""
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path, override=True)
        return True
    return False

def main():
    # Determinar ambiente desde argumentos o variable de entorno
    if len(sys.argv) > 1:
        env = sys.argv[1].lower()
    else:
        env = os.getenv('ENVIRONMENT', 'local').lower()
    
    # Validar ambiente
    if env not in ['local', 'test', 'prod', 'production']:
        print(f"❌ Ambiente inválido: {env}")
        print("   Uso: python run_api.py [local|test|prod]")
        sys.exit(1)
    
    # Normalizar 'production' a 'prod'
    if env == 'production':
        env = 'prod'
    
    # Cambiar al directorio del script
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Cargar variables de entorno según el ambiente
    env_loaded = False
    if env == 'local':
        if load_env_file('.env.local'):
            print("✅ Cargando configuración desde .env.local")
            env_loaded = True
        elif load_env_file('.env'):
            print("✅ Cargando configuración desde .env")
            env_loaded = True
        else:
            print("⚠️  No se encontró .env.local ni .env, usando valores por defecto")
    elif env == 'test':
        if load_env_file('.env.test'):
            print("✅ Cargando configuración desde .env.test")
            env_loaded = True
        else:
            print("❌ Error: No se encontró .env.test")
            print("   Crea .env.test basándote en .env.example")
            sys.exit(1)
    elif env == 'prod':
        if load_env_file('.env.production'):
            print("✅ Cargando configuración desde .env.production")
            env_loaded = True
        else:
            print("❌ Error: No se encontró .env.production")
            print("   Crea .env.production basándote en .env.example")
            sys.exit(1)
    
    # Forzar ambiente
    os.environ['ENVIRONMENT'] = env
    os.environ.setdefault('LOG_LEVEL', 'INFO')
    
    # Obtener configuración de puerto y host
    api_port = os.getenv('API_PORT', '8000' if env == 'local' else '8001' if env == 'test' else '8000')
    api_host = os.getenv('API_HOST', '0.0.0.0')
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:3001')
    
    # Mostrar información
    print(f"🔧 Ambiente: {env.upper()}")
    print(f"📡 Puerto: {api_port}")
    print(f"🌐 CORS Origins: {cors_origins}")
    print()
    
    # Ejecutar uvicorn
    try:
        cmd = [
            sys.executable, '-m', 'uvicorn',
            'api.main:app',
            '--reload',
            '--host', api_host,
            '--port', api_port
        ]
        
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Deteniendo servidor...")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando uvicorn: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: uvicorn no encontrado")
        print("   Asegúrate de tener el entorno virtual activado y las dependencias instaladas")
        sys.exit(1)

if __name__ == '__main__':
    main()
