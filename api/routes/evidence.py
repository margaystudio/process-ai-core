"""
Endpoint de procesamiento de evidencias individuales (wizard Bloque C).

POST /api/v1/evidence/process — recibe un archivo, lo procesa según tipo
y devuelve texto extraído + metadata (idioma, duración, páginas, used_ocr).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.dependencies import get_current_user_id
from process_ai_core.evidence_processing import process_evidence_file
from process_ai_core.upload_validation import ALLOWED_UPLOAD_EXTENSIONS

router = APIRouter(
    prefix="/api/v1/evidence",
    tags=["evidence"],
)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
VALID_KINDS = frozenset({"audio", "video", "image", "text"})


@router.post("/process")
async def process_evidence(
    file: UploadFile = File(...),
    kind: str = Form(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Procesa un archivo de evidencia según su tipo.

    Args:
        file: Archivo subido (multipart).
        kind: Tipo de evidencia: audio | video | image | text.

    Returns:
        { status, extracted_text, metadata, error }
    """
    del user_id  # auth requerida; no se usa para lógica adicional

    kind_lower = kind.strip().lower()
    if kind_lower not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"kind inválido: '{kind}'. Valores permitidos: audio, video, image, text",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="El archivo debe tener nombre")

    ext = Path(file.filename).suffix.lower()
    allowed = ALLOWED_UPLOAD_EXTENSIONS.get(kind_lower, frozenset())
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extensión no permitida para {kind_lower}: '{ext or '(sin extensión)'}'. "
                f"Permitidas: {', '.join(sorted(allowed))}"
            ),
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo supera el límite de {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        temp_path = tmp_dir / f"upload{ext}"
        temp_path.write_bytes(content)

        result = process_evidence_file(temp_path, kind_lower, file.filename)

    return {
        "status": result.status,
        "extracted_text": result.extracted_text,
        "metadata": result.metadata,
        "error": result.error,
    }
