#!/bin/bash
# Script para ejecutar la API en ambiente LOCAL

set -e

cd "$(dirname "$0")"

# Cargar variables de entorno local
if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
    echo "✅ Cargando configuración desde .env.local"
elif [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Cargando configuración desde .env"
else
    echo "⚠️  No se encontró .env.local ni .env, usando valores por defecto"
fi

# Forzar ambiente local
export ENVIRONMENT=local
export LOG_LEVEL=${LOG_LEVEL:-INFO}

echo "🔧 Ambiente: LOCAL"
echo "📡 Puerto: ${API_PORT:-8000}"
echo "🌐 CORS Origins: ${CORS_ORIGINS:-http://localhost:3000,http://localhost:3001}"

uvicorn api.main:app --reload --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}


