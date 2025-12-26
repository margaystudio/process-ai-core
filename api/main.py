"""
API HTTP principal para process-ai-core.

Esta aplicación FastAPI expone endpoints REST que usan el core interno
(process_ai_core.engine) para generar documentación de procesos.

Uso:
    uvicorn api.main:app --reload --port 8000
"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .routes import artifacts, auth, catalog, documents, folders, process_runs, recipe_runs, users, validations, workspaces

# Cargar variables de entorno
load_dotenv()

# Determinar ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configurar logging según ambiente
log_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"🚀 Iniciando API en ambiente: {ENVIRONMENT}")

app = FastAPI(
    title="Process AI Core API",
    description="API para generar documentación de procesos asistida por IA",
    version="0.1.0",
)

# CORS: configurar según ambiente
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

logger.info(f"🌐 CORS origins configurados: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(workspaces.router)
app.include_router(folders.router)
app.include_router(documents.router)
app.include_router(process_runs.router)
app.include_router(recipe_runs.router)
app.include_router(artifacts.router)
app.include_router(validations.router)
app.include_router(users.router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "process-ai-core-api"}


@app.get("/health")
async def health():
    """Health check detallado."""
    return {
        "status": "ok",
        "service": "process-ai-core-api",
        "version": "0.1.0",
    }

