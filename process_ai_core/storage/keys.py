"""
Construcción de claves canónicas de almacenamiento.

Esquema (reemplaza el viejo `output/{run_id}/...` para artefactos auditables):

    workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/document.pdf
    workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/assets/{asset_id}.{ext}

Las claves incluyen `workspace_id` para aislamiento multi-tenant verificable.
Los runs efímeros NO usan estas claves (se renderizan en temp y no se persisten).
"""

from __future__ import annotations


def version_prefix(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}"


def version_pdf_key(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"{version_prefix(workspace_id, document_id, version_id)}/document.pdf"


def version_asset_key(
    workspace_id: str, document_id: str, version_id: str, asset_id: str, ext: str
) -> str:
    ext = ext.lstrip(".")
    return f"{version_prefix(workspace_id, document_id, version_id)}/assets/{asset_id}.{ext}"
