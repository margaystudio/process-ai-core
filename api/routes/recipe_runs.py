"""
Endpoint para crear y consultar corridas del pipeline de recetas.

Este endpoint maneja:
- POST /api/v1/recipe-runs: Crear una nueva corrida
- GET /api/v1/recipe-runs/{run_id}: Consultar estado de una corrida
"""

import tempfile
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from process_ai_core.config import get_settings
from process_ai_core.domain_models import RawAsset
from process_ai_core.domains.recipes.profiles import get_profile
from process_ai_core.engine import run_recipe_pipeline

from ..models.requests import RecipeMode, RecipeRunResponse

router = APIRouter(prefix="/api/v1/recipe-runs", tags=["recipe-runs"])


@router.post("", response_model=RecipeRunResponse)
async def create_recipe_run(
    recipe_name: str = Form(...),
    mode: RecipeMode = Form(RecipeMode.SIMPLE),
    audio_files: List[UploadFile] = File(default=[]),
    video_files: List[UploadFile] = File(default=[]),
    image_files: List[UploadFile] = File(default=[]),
    text_files: List[UploadFile] = File(default=[]),
):
    """
    Crea una nueva corrida del pipeline de documentación de recetas.

    Recibe archivos multimedia (audio, video, imágenes, texto) y genera
    un documento de receta estructurado (JSON, Markdown, PDF).

    Args:
        recipe_name: Nombre de la receta a documentar
        mode: Modo del documento (simple o detallado)
        audio_files: Archivos de audio (.m4a, .mp3, .wav)
        video_files: Archivos de video (.mp4, .mov, .mkv)
        image_files: Archivos de imagen (.png, .jpg, .jpeg, .webp)
        text_files: Archivos de texto (.txt, .md)

    Returns:
        RecipeRunResponse con run_id, status y paths a artefactos generados
    """
    settings = get_settings()
    run_id = str(uuid.uuid4())

    # Validar que haya al menos un archivo
    total_files = (
        len(audio_files) + len(video_files) + len(image_files) + len(text_files)
    )
    if total_files == 0:
        raise HTTPException(
            status_code=400, detail="Se requiere al menos un archivo de entrada"
        )

    # Crear directorio temporal para los uploads
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        raw_assets: List[RawAsset] = []

        # Contadores para IDs deterministas
        counters = {"audio": 0, "video": 0, "image": 0, "text": 0}

        async def process_files(files: List[UploadFile], kind: str, prefix: str):
            """Procesa una lista de archivos y los agrega a raw_assets."""
            if not files:
                return

            for upload_file in files:
                counters[kind] += 1
                asset_id = f"{prefix}{counters[kind]}"

                # Guardar archivo en temp_dir
                ext = Path(upload_file.filename).suffix if upload_file.filename else ""
                temp_path = temp_dir / f"{asset_id}{ext}"

                # Leer contenido y guardar
                content = await upload_file.read()
                temp_path.write_bytes(content)

                # Construir RawAsset
                titulo = (
                    Path(upload_file.filename).stem
                    if upload_file.filename
                    else f"{kind} {counters[kind]}"
                )

                raw_assets.append(
                    RawAsset(
                        id=asset_id,
                        kind=kind,  # type: ignore
                        path_or_url=str(temp_path),
                        metadata={"titulo": titulo},
                    )
                )

        # Procesar cada tipo de archivo
        await process_files(audio_files, "audio", "aud")
        await process_files(video_files, "video", "vid")
        await process_files(image_files, "image", "img")
        await process_files(text_files, "text", "txt")

        # Obtener perfil según modo
        profile = get_profile(mode.value)

        # Ejecutar pipeline
        try:
            output_dir = Path(settings.output_dir) / run_id
            output_dir.mkdir(parents=True, exist_ok=True)

            result = run_recipe_pipeline(
                recipe_name=recipe_name,
                raw_assets=raw_assets,
                profile=profile,
                context_block=None,
                output_base=output_dir,  # Las imágenes se copiarán a output_dir/assets/
            )

            # Persistir artefactos
            json_path = output_dir / "recipe.json"
            md_path = output_dir / "recipe.md"
            pdf_path = output_dir / "recipe.pdf"

            json_path.write_text(result["json_str"], encoding="utf-8")
            md_path.write_text(result["markdown"], encoding="utf-8")

            # Generar PDF si se requiere
            pdf_generated = False
            try:
                from process_ai_core.export import export_pdf

                export_pdf(run_dir=output_dir, md_path=md_path, pdf_name="recipe.pdf")
                pdf_generated = True
            except Exception as pdf_error:
                # PDF opcional, no fallamos si no se puede generar
                pass

            # Construir paths relativos a los artefactos
            artifacts = {
                "json": f"/api/v1/artifacts/{run_id}/recipe.json",
                "markdown": f"/api/v1/artifacts/{run_id}/recipe.md",
            }
            if pdf_generated:
                artifacts["pdf"] = f"/api/v1/artifacts/{run_id}/recipe.pdf"

            return RecipeRunResponse(
                run_id=run_id,
                recipe_name=recipe_name,
                status="completed",
                artifacts=artifacts,
            )

        except Exception as e:
            # Error interno del servidor: devolver 500
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando el pipeline: {str(e)}",
            ) from e


@router.get("/{run_id}", response_model=RecipeRunResponse)
async def get_recipe_run(run_id: str):
    """
    Obtiene el estado y resultados de una corrida.

    Args:
        run_id: ID de la corrida

    Returns:
        RecipeRunResponse con el estado actual
    """
    # TODO: Implementar consulta desde DB o storage
    # Por ahora devolvemos un error 404
    raise HTTPException(status_code=404, detail=f"Run {run_id} no encontrada")


@router.post("/{run_id}/generate-pdf")
async def generate_pdf_from_run(run_id: str):
    """
    Genera un PDF desde un run existente (sin ejecutar el pipeline completo).

    Este endpoint es más rápido y económico que crear un nuevo run, ya que:
    - No requiere llamadas a OpenAI
    - Solo ejecuta Pandoc para convertir Markdown a PDF
    - Reutiliza el markdown y las imágenes ya generadas

    Args:
        run_id: ID de la corrida existente

    Returns:
        JSON con la URL del PDF generado

    Raises:
        404: Si el run_id no existe o no tiene markdown
        500: Si falla la generación del PDF
    """
    settings = get_settings()
    run_dir = Path(settings.output_dir) / run_id
    md_path = run_dir / "recipe.md"

    # Verificar que el run existe y tiene markdown
    if not run_dir.exists():
        raise HTTPException(
            status_code=404, detail=f"Run {run_id} no encontrado"
        )

    if not md_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Markdown no encontrado para run {run_id}. El run debe tener un recipe.md generado.",
        )

    # Generar PDF
    try:
        from process_ai_core.export import export_pdf

        pdf_path = export_pdf(
            run_dir=run_dir,
            md_path=md_path,
            pdf_name="recipe.pdf",
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "pdf_url": f"/api/v1/artifacts/{run_id}/recipe.pdf",
            "message": "PDF generado exitosamente",
        }

    except FileNotFoundError as e:
        # Pandoc no está instalado
        raise HTTPException(
            status_code=500,
            detail=f"Pandoc no está instalado o no está en PATH: {str(e)}",
        ) from e
    except RuntimeError as e:
        # Error al generar PDF (LaTeX, imágenes faltantes, etc.)
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar PDF: {str(e)}",
        ) from e
    except Exception as e:
        # Error inesperado
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado al generar PDF: {str(e)}",
        ) from e



