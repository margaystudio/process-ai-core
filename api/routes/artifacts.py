"""
Endpoint para servir artefactos generados (JSON, Markdown, PDF).

Este endpoint permite descargar los archivos generados por el pipeline.
Para PDFs, se sirven inline para poder visualizarlos en iframes.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from process_ai_core.config import get_settings

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


@router.get("/{run_id}/{filename:path}")
async def get_artifact(run_id: str, filename: str, download: bool = False):
    """
    Sirve un artefacto generado (JSON, Markdown, PDF o imágenes/assets).

    Args:
        run_id: ID de la corrida
        filename: Ruta relativa del archivo dentro del directorio del run
                  (puede incluir subdirectorios, p.ej. assets/frames_vid1/step01_1.png)
        download: Si es True, fuerza la descarga del archivo (default: False, se abre inline)

    Returns:
        Archivo solicitado o 404 si no existe
    """
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

