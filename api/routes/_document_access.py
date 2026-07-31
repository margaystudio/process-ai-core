"""
Verificación de acceso a un documento para servir sus archivos.

Por qué existe
--------------
Las imágenes embebidas en el contenido de un documento se servían con un token
firmado en la URL. Un token en la dirección es un PORTADOR: el servidor valida la
firma y el workspace, pero no puede saber QUIÉN lo presenta. Con eso, el permiso
por carpeta —una capacidad que el producto vende explícitamente— simplemente no
se aplicaba sobre las imágenes: cualquier miembro del workspace con el enlace
veía material de una carpeta que tenía denegada.

El proxy del front es la plomería que hace que el servidor sepa quién pide. Esto
de acá es el arreglo: la verificación que ese request ahora sí puede hacer.

Sobre el costo
--------------
Una vista con diez imágenes son diez requests, y por lo tanto diez chequeos. Se
usa `PermissionContext` —el contexto precargado que ya existe— y no las funciones
por-ítem: el contexto resuelve todo en ~7 queries constantes contra las ~12 por
ítem del camino ingenuo. Diez chequeos ingenuos serían diez veces el N+1 que ya
se eliminó una vez.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from process_ai_core.db.models import Document, Run


def assert_document_viewable(
    session: Session,
    document: Document | None,
    *,
    workspace_id: str,
    user_id: str,
    contexto: str = "El archivo",
) -> Document:
    """
    Verifica que `user_id` pueda VER el documento, y devuelve el documento.

    Dos controles, en este orden:

    1. **Aislamiento de tenant**: el documento tiene que pertenecer al workspace
       activo. Falla con 404, no 403: para quien está en otro tenant, ese
       documento no existe.
    2. **Permiso sobre la CARPETA**, no solo membresía al workspace. Es lo que el
       token firmado no podía evaluar. Falla con 403.

    Raises:
        HTTPException 404: el documento no existe o es de otro workspace.
        HTTPException 403: el usuario no puede ver esa carpeta.
    """
    from process_ai_core.db.permissions import build_permission_context

    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail=f"{contexto} no se encontró")

    # Contexto precargado: evaluación en memoria, sin N+1 (ver PermissionContext).
    perm_ctx = build_permission_context(session, user_id, workspace_id)
    if not perm_ctx.can_view_folder(document.folder_id):
        raise HTTPException(
            status_code=403,
            detail="No tiene acceso a los documentos de esta carpeta",
        )
    return document


def assert_run_viewable(
    session: Session,
    run_id: str,
    *,
    workspace_id: str,
    user_id: str,
    contexto: str = "El artefacto",
) -> Document:
    """
    Igual que `assert_document_viewable`, para un artefacto de run.

    El run no tiene permisos propios: los hereda del documento que produjo. Un
    artefacto de un run es contenido del documento, y se ve si el documento se ve.
    """
    run = session.query(Run).filter_by(id=run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"{contexto} no se encontró")
    document = session.query(Document).filter_by(id=run.document_id).first()
    return assert_document_viewable(
        session, document, workspace_id=workspace_id, user_id=user_id, contexto=contexto
    )
