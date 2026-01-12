#!/bin/bash
# Script para ejecutar la API en ambiente TEST

set -e

cd "$(dirname "$0")"

# Cargar variables de entorno test
if [ -f .env.test ]; then
    export $(cat .env.test | grep -v '^#' | xargs)
    echo "✅ Cargando configuración desde .env.test"
else
    echo "❌ Error: No se encontró .env.test"
    echo "   Crea .env.test basándote en .env.example"
    exit 1
fi

# Forzar ambiente test
export ENVIRONMENT=test
export LOG_LEVEL=${LOG_LEVEL:-INFO}

echo "🔧 Ambiente: TEST"
echo "📡 Puerto: ${API_PORT:-8001}"
echo "🌐 CORS Origins: ${CORS_ORIGINS}"

uvicorn api.main:app --reload --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8001}


