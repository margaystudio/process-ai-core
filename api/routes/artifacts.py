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


@router.get("/{run_id}/{filename}")
async def get_artifact(run_id: str, filename: str):
    """
    Sirve un artefacto generado (JSON, Markdown o PDF).

    Args:
        run_id: ID de la corrida
        filename: Nombre del archivo (process.json, process.md, process.pdf)

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
    }
    content_type = content_type_map.get(artifact_path.suffix, "application/octet-stream")

    # Para PDFs, servir inline para que se puedan ver en iframes
    if artifact_path.suffix == ".pdf":
        with open(artifact_path, "rb") as f:
            content = f.read()
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": "inline; filename=\"" + filename + "\"",
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

