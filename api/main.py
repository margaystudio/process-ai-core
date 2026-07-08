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

from .routes import artifacts, catalog, documents, evidence, folders, process_runs, semantic, users, validations, workspaces, subscriptions, operational_roles
from process_ai_core.db.database import warmup_db_pool
# recipe_runs: dominio "recetas" (experimento B2C, sin auth/workspace) deshabilitado para el MVP. Ver línea de include_router más abajo.

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
app.include_router(catalog.router)
app.include_router(workspaces.router)
app.include_router(folders.router)
app.include_router(documents.router)
app.include_router(process_runs.router)
app.include_router(evidence.router)
# Deshabilitado para el MVP: el dominio "recetas" no tiene autenticación (no JWT, no
# sync_workspace_access, no contexto de tenant) y no es parte del producto de procesos.
# Es un experimento para otro nicho (app mobile B2C, sin workspace). Reactivar SOLO tras
# darle el hardening de la Etapa 1. Para reactivar: descomentar esta línea y re-agregar
# `recipe_runs` al import de arriba.
# app.include_router(recipe_runs.router)
app.include_router(artifacts.router)
app.include_router(validations.router)
app.include_router(users.router)
app.include_router(subscriptions.router)
# auth.router eliminado: sync-user y check-email son responsabilidad de margay-workspace.
# invitations.router eliminado: el flujo de invitaciones es responsabilidad del hub.
# superadmin.router eliminado: el alta de tenants/workspaces es responsabilidad
# de margay-workspace. Ver api/routes/superadmin.py (archivo eliminado).
app.include_router(operational_roles.router)
# Capa semántica: relaciones documentales, knowledge objects e impacto.
app.include_router(semantic.router)


@app.on_event("startup")
def _startup_warmup() -> None:
    try:
        warmup_db_pool()
        logger.info("DB pool warmed up")
    except Exception as exc:
        logger.warning("DB pool warmup failed: %s", exc)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "process-ai-core-api"}


@app.get("/health")
async def health():
    """Health check detallado."""
    from process_ai_core.db.database import DATABASE_URL

    db_backend = "sqlite" if DATABASE_URL.startswith("sqlite") else "postgresql"
    if db_backend == "sqlite" and ":memory:" not in DATABASE_URL:
        return {
            "status": "error",
            "service": "process-ai-core-api",
            "version": "0.1.0",
            "database": db_backend,
            "detail": "SQLite en archivo no soportado; usar Supabase Postgres (schema process_ai)",
        }
    if ENVIRONMENT in {"prod", "production", "test"} and db_backend == "sqlite":
        return {
            "status": "error",
            "service": "process-ai-core-api",
            "version": "0.1.0",
            "database": db_backend,
            "detail": "SQLite no permitido en test/prod; configurar DATABASE_URL con PostgreSQL",
        }

    return {
        "status": "ok",
        "service": "process-ai-core-api",
        "version": "0.1.0",
        "environment": ENVIRONMENT,
        "database": db_backend,
        "database_schema": os.getenv("DATABASE_SCHEMA", "process_ai") if db_backend == "postgresql" else None,
    }

