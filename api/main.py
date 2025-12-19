"""
API HTTP principal para process-ai-core.

Esta aplicación FastAPI expone endpoints REST que usan el core interno
(process_ai_core.engine) para generar documentación de procesos.

Uso:
    uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import artifacts, process_runs

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
app.include_router(process_runs.router)
app.include_router(artifacts.router)


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

