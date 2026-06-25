"""
Rutas de documentos (procesos, recetas, etc.).

Originalmente un único módulo `documents.py` de ~2600 líneas que concentraba
routing, permisos, generación, edición, versionado y exportación. Se partió en
sub-routers por responsabilidad, sin cambiar URLs ni comportamiento:

- crud:     listar / obtener / actualizar / eliminar / detalles de Process
- runs:     listado de runs y generación (pipeline) de nuevas versiones
- content:  edición manual, imágenes del editor y patch asistido por IA
- versions: versiones, preview PDF y flujo de aprobación (submit/cancel/clone)

El router expuesto acá conserva el prefijo y las dependencias originales, que
FastAPI propaga a todos los sub-routers incluidos.
"""

from fastapi import APIRouter, Depends

from api.workspace_client import require_process_ai_access, sync_workspace_access

from . import content, crud, runs, versions

_PREFIX = "/api/v1/documents"

# El prefijo va en cada include_router (no en el router padre) porque crud expone
# una ruta con path "" (GET /api/v1/documents) y FastAPI rechaza prefijo+path
# ambos vacíos al incluir un sub-router. Las dependencias del router padre se
# propagan igual a todas las rutas incluidas.
router = APIRouter(
    tags=["documents"],
    # sync_workspace_access corre primero: garantiza que User local y WorkspaceMembership
    # existan antes de que get_current_user_id y has_permission los necesiten.
    dependencies=[Depends(sync_workspace_access), Depends(require_process_ai_access)],
)

# Orden de inclusión: crud primero para que sus rutas estáticas de un segmento
# (/pending-approval, /to-review) se registren antes del catch-all /{document_id}.
router.include_router(crud.router, prefix=_PREFIX)
router.include_router(runs.router, prefix=_PREFIX)
router.include_router(content.router, prefix=_PREFIX)
router.include_router(versions.router, prefix=_PREFIX)
