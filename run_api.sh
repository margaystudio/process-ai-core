#!/bin/bash
# Script para ejecutar la API FastAPI
# Ejecuta desde la raíz del proyecto para que Python encuentre el módulo 'api'

cd "$(dirname "$0")"
uvicorn api.main:app --reload --port 8000


