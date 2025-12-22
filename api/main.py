"""
API HTTP principal para process-ai-core.

Esta aplicación FastAPI expone endpoints REST que usan el core interno
(process_ai_core.engine) para generar documentación de procesos.

Uso:
    uvicorn api.main:app --reload --port 8000
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import artifacts, catalog, documents, folders, process_runs, recipe_runs, users, validations, workspaces

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Process AI Core API",
    description="API para generar documentación de procesos asistida por IA",
    version="0.1.0",
)

# CORS: permitir requests desde la UI (Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas
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

