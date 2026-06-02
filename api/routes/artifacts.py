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

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from process_ai_core.config import get_settings
from ..artifact_signing import verify_artifact_token

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
    # Verificar token ANTES de tocar el filesystem
    if not verify_artifact_token(token, run_id, filename):
        raise HTTPException(status_code=404, detail="Artefacto no encontrado")

    settings = get_settings()
    artifact_path = Path(settings.output_dir) / run_id / filename

    # Validar que el archivo existe y está dentro de output_dir (seguridad)
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Artefacto {filename} no encontrado")

    # Validar que no hay path traversal
    try:
        artifact_path.resolve().relative_to(Path(settings.output_dir).resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Acceso denegado")

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
    content_type = content_type_map.get(artifact_path.suffix, "application/octet-stream")

    # Para PDFs, servir inline por defecto (para iframes) o forzar descarga
    if artifact_path.suffix == ".pdf":
        with open(artifact_path, "rb") as f:
            content = f.read()
        
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
    
    # Para otros archivos, permitir descarga
    return FileResponse(
        path=str(artifact_path),
        media_type=content_type,
        filename=filename,
    )

