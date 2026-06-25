"""
Endpoint para servir artefactos generados (JSON, Markdown, PDF).

Este endpoint permite descargar los archivos generados por el pipeline.
Para PDFs, se sirven inline para poder visualizarlos en iframes.

Autenticación: URLs firmadas con HMAC-SHA256. Como el endpoint es consumido por
<iframe> y window.open (que no pueden enviar el header Authorization), la
autenticación se realiza mediante un token firmado en la query string.
El token es generado por el backend al construir la URL del artefacto
(api/artifact_signing.py) y expira según ARTIFACT_URL_TTL_SECONDS (default: 15 min).
"""

from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from process_ai_core.storage import get_storage, normalize_key, run_artifact_key
from ..artifact_signing import verify_and_extract_workspace

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("/{run_id}/{filename:path}")
async def get_artifact(
    run_id: str,
    filename: str,
    token: str = Query(..., description="Token HMAC firmado por el backend"),
    download: bool = False,
):
    """
    Sirve un artefacto generado (JSON, Markdown, PDF o imágenes/assets).

    Requiere un token HMAC firmado generado por el backend (sign_artifact_url).
    Token inválido, expirado o para otro run/filename → 404 (no revela existencia).

    Args:
        run_id  : ID de la corrida
        filename: Ruta relativa del archivo dentro del directorio del run
                  (puede incluir subdirectorios, ej. assets/frames_vid1/step01_1.png)
        token   : Token HMAC firmado (?token=...)
        download: Si es True, fuerza la descarga del archivo (default: False, inline)

    Returns:
        Archivo solicitado o 404 si token inválido/expirado o el archivo no existe
    """
    # Verificar token ANTES de tocar el storage. El token embebe el workspace_id,
    # que usamos para construir la clave tenant-scoped sin cambiar la URL pública.
    workspace_id = verify_and_extract_workspace(token, run_id, filename)
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Artefacto no encontrado")

    # Clave de blob: workspaces/{ws}/runs/{run_id}/{filename}. normalize_key valida traversal.
    try:
        key = normalize_key(run_artifact_key(workspace_id, run_id, filename))
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    storage = get_storage()
    try:
        content = storage.get(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Artefacto {filename} no encontrado")

    # Determinar content-type
    content_type_map = {
        ".json": "application/json",
        ".md": "text/markdown",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    suffix = PurePosixPath(key).suffix
    content_type = content_type_map.get(suffix, "application/octet-stream")

    # Para PDFs, servir inline por defecto (para iframes) o forzar descarga
    if suffix == ".pdf":
        disposition = "attachment" if download else "inline"
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"{disposition}; filename=\"{filename}\"",
                "Content-Type": "application/pdf",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    
    # Para otros archivos, servir los bytes (inline o descarga).
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f"{disposition}; filename=\"{PurePosixPath(key).name}\"",
        },
    )

