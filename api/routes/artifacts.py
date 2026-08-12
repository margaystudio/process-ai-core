"""
Endpoint para servir artefactos generados de un run (JSON, Markdown, PDF, assets).

Autenticación: `Authorization: Bearer`, como el resto de la API, MÁS verificación
del permiso de ver la carpeta del documento que produjo el run.

Antes se servían con un token HMAC en la query string, para poder consumirlos
desde un `<iframe>`, un `window.open` o un `<img>` —que no pueden mandar headers—.
El costo de eso era que el servidor no sabía QUIÉN presentaba el token: validaba
la firma y el workspace, pero no podía aplicar el permiso por carpeta. Cualquier
miembro del workspace con el enlace veía un artefacto de una carpeta que tenía
denegada.

Cómo se resuelve ahora, según quién pide (ver el principio completo en
api/routes/documents/_helpers.py):

- Un archivo suelto que el usuario abre a propósito (el PDF de un run): lo pide
  la PANTALLA con fetch + Authorization y lo muestra desde un blob URL.
- Una imagen embebida en el contenido de un documento (`assets/...`): la pide el
  navegador solo, así que va por el proxy del front, que reenvía con Bearer.

El freeze del PDF no pasa por acá: lee los blobs directo de object storage.
"""

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Request

from process_ai_core.db.database import get_db_session
from process_ai_core.storage import get_storage, normalize_key, run_artifact_key

from api.dependencies import get_current_user_id
from api.routes._document_access import assert_run_viewable
from api.routes.documents._helpers import authorized_file_response, media_type_for
from api.request_identity import capture_request_identity
from api.workspace_client import (
    WorkspaceSessionContext,
    get_workspace_context,
    require_process_ai_access,
    resolve_tenant_workspace_id,
    sync_workspace_access,
)

router = APIRouter(
    prefix="/api/v1/artifacts",
    tags=["artifacts"],
    dependencies=[
        Depends(sync_workspace_access),
        Depends(capture_request_identity),
        Depends(require_process_ai_access),
    ],
)


@router.get("/{run_id}/{filename:path}")
def get_artifact(
    run_id: str,
    filename: str,
    request: Request,
    download: bool = False,
    user_id: str = Depends(get_current_user_id),
    ctx: WorkspaceSessionContext = Depends(get_workspace_context),
):
    """
    Sirve un artefacto generado (JSON, Markdown, PDF o imágenes/assets).

    Sin sesión → 401. Sin permiso sobre la carpeta del documento → 403. El run
    no tiene permisos propios: los hereda del documento que produjo.

    Args:
        run_id  : ID de la corrida
        filename: Ruta relativa del archivo dentro del directorio del run
                  (puede incluir subdirectorios, ej. assets/frames_vid1/step01_1.png)
        download: Si es True, fuerza la descarga del archivo (default: inline)
    """
    workspace_id = resolve_tenant_workspace_id(ctx)
    with get_db_session() as session:
        assert_run_viewable(
            session, run_id, workspace_id=workspace_id, user_id=user_id,
            contexto="El artefacto",
        )

    # Clave de blob: workspaces/{ws}/runs/{run_id}/{filename}. normalize_key valida traversal.
    try:
        key = normalize_key(run_artifact_key(workspace_id, run_id, filename))
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    try:
        content = get_storage().get(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Artefacto {filename} no encontrado")

    nombre = PurePosixPath(key).name
    return authorized_file_response(
        content,
        nombre,
        request,
        media_type=media_type_for(nombre),
        download=download,
    )
