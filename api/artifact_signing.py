"""
Firma HMAC-SHA256 para URLs de artefactos.

Permite servir artefactos (PDFs, JSON, MD) desde el endpoint
GET /api/v1/artifacts/{run_id}/{filename} sin exponer autenticación
por header (necesario para iframes y window.open).

Formato del token: {exp}.{workspace_id}.{sig_hex}
  - exp         : timestamp Unix de expiración (int)
  - workspace_id: ID de workspace que firma la URL (UUID, sin puntos)
  - sig_hex     : HMAC-SHA256 de "{run_id}:{filename}:{workspace_id}:{exp}"

El token se pasa como ?token=... en la query string.
"""

import hashlib
import hmac
import logging
import os
import time
from urllib.parse import quote

logger = logging.getLogger(__name__)

_DEV_SECRET = "dev-only-insecure-artifact-secret-do-not-use-in-prod"


def _get_secret() -> bytes:
    from process_ai_core.config import get_settings  # import tardío para evitar ciclos

    secret = get_settings().artifact_signing_secret
    if not secret:
        env = os.getenv("ENVIRONMENT", "local")
        if env not in ("local", "test"):
            raise RuntimeError(
                "ARTIFACT_SIGNING_SECRET debe estar configurado en producción. "
                "Setea la variable de entorno ARTIFACT_SIGNING_SECRET."
            )
        logger.warning(
            "ARTIFACT_SIGNING_SECRET no configurado — usando secreto de desarrollo inseguro. "
            "NO usar en producción."
        )
        secret = _DEV_SECRET
    return secret.encode("utf-8")


def sign_artifact_url(
    run_id: str,
    filename: str,
    workspace_id: str,
    ttl: int | None = None,
) -> str:
    """
    Genera la URL firmada para un artefacto.

    Args:
        run_id      : ID de la corrida.
        filename    : Ruta relativa del archivo dentro del directorio del run
                      (puede incluir subdirectorios, ej. "assets/frame1.png").
        workspace_id: ID del workspace activo; vincula la firma al tenant.
        ttl         : Tiempo de vida en segundos. Si None, usa ARTIFACT_URL_TTL_SECONDS.

    Returns:
        URL relativa con token firmado: "/api/v1/artifacts/{run_id}/{filename}?token=..."
    """
    from process_ai_core.config import get_settings

    if ttl is None:
        ttl = get_settings().artifact_url_ttl_seconds

    exp = int(time.time()) + ttl
    msg = f"{run_id}:{filename}:{workspace_id}:{exp}"
    sig = hmac.new(_get_secret(), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{exp}.{workspace_id}.{sig}"

    # quote(filename, safe="/") preserva barras para subdirectorios (assets/frame.png)
    encoded_filename = quote(filename, safe="/")
    return f"/api/v1/artifacts/{run_id}/{encoded_filename}?token={token}"


def verify_artifact_token(token: str, run_id: str, filename: str) -> bool:
    """
    Verifica que el token sea válido para el run_id y filename dados.

    - Valida estructura del token.
    - Verifica expiración.
    - Verifica firma con hmac.compare_digest (resistente a timing attacks).
    - Devuelve False (no lanza) ante cualquier error; el caller debe devolver 404.

    Args:
        token   : Token de la query string.
        run_id  : run_id del path de la URL.
        filename: filename del path de la URL.

    Returns:
        True si el token es válido y no ha expirado; False en caso contrario.
    """
    return verify_and_extract_workspace(token, run_id, filename) is not None


def verify_and_extract_workspace(token: str, run_id: str, filename: str) -> str | None:
    """
    Verifica el token y, si es válido, devuelve el `workspace_id` embebido en él.
    Devuelve None si el token es inválido o expiró.

    El `workspace_id` se usa para construir la clave de storage tenant-scoped
    (`workspaces/{ws}/runs/{run_id}/{filename}`) sin cambiar la URL pública.
    """
    try:
        parts = token.split(".", 2)
        if len(parts) != 3:
            return None

        exp_str, workspace_id, sig = parts
        exp = int(exp_str)

        if time.time() > exp:
            return None

        msg = f"{run_id}:{filename}:{workspace_id}:{exp}"
        expected = hmac.new(_get_secret(), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, sig):
            return workspace_id
        return None

    except Exception:
        return None
