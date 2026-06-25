"""
Construcción de claves canónicas de almacenamiento.

Esquema — TODO bajo `workspaces/{workspace_id}/...` (organizado por tenant):

    workspaces/{ws}/runs/{run_id}/process.json|md|pdf
    workspaces/{ws}/runs/{run_id}/assets/...
    workspaces/{ws}/documents/{document_id}/versions/{version_id}/document.pdf
    workspaces/{ws}/documents/{document_id}/versions/{version_id}/assets/{asset_id}.{ext}

Las claves incluyen `workspace_id` para aislamiento multi-tenant verificable y para
contabilidad/borrado por tenant triviales (sumar/borrar por prefijo).
"""

from __future__ import annotations


def workspace_prefix(workspace_id: str) -> str:
    return f"workspaces/{workspace_id}"


def run_prefix(workspace_id: str, run_id: str) -> str:
    return f"workspaces/{workspace_id}/runs/{run_id}"


def run_artifact_key(workspace_id: str, run_id: str, rel: str) -> str:
    """Clave de un artefacto de run (rel = ruta relativa dentro del run, estilo POSIX)."""
    rel = rel.lstrip("/")
    return f"{run_prefix(workspace_id, run_id)}/{rel}"


def version_prefix(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}"


def version_pdf_key(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"{version_prefix(workspace_id, document_id, version_id)}/document.pdf"


def version_asset_key(
    workspace_id: str, document_id: str, version_id: str, asset_id: str, ext: str
) -> str:
    ext = ext.lstrip(".")
    return f"{version_prefix(workspace_id, document_id, version_id)}/assets/{asset_id}.{ext}"
