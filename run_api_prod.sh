#!/bin/bash
# Script para ejecutar la API en ambiente PRODUCTION

set -e

cd "$(dirname "$0")"

# Cargar variables de entorno production
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
    echo "✅ Cargando configuración desde .env.production"
else
    echo "❌ Error: No se encontró .env.production"
    echo "   Crea .env.production basándote en .env.example"
    exit 1
fi

# Forzar ambiente production
export ENVIRONMENT=production
export LOG_LEVEL=${LOG_LEVEL:-WARNING}

echo "🔧 Ambiente: PRODUCTION"
echo "📡 Puerto: ${API_PORT:-8000}"
echo "🌐 CORS Origins: ${CORS_ORIGINS}"

# En producción, no usar --reload
uvicorn api.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --workers 4

