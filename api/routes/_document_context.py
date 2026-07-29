"""
Construcción del `DocumentContext` que se le pasa al exportador de PDF.

Vive acá y no en `process_ai_core/export/` a propósito: el paquete de export no
conoce la base de datos — recibe datos ya resueltos. Este módulo es el traductor,
igual que `_branding.py` lo es para el logo.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from process_ai_core.db.models import (
    Document,
    DocumentType,
    DocumentVersion,
    User,
    Validation,
    Workspace,
)
from process_ai_core.config import resolve_verification_base_url
from process_ai_core.export.document_context import DocumentContext

logger = logging.getLogger(__name__)


def _resolve_user_names(session: Session, user_ids: list[str | None]) -> dict[str, str]:
    """
    Resuelve varios user_id a nombre en UNA query.

    El PDF necesita hasta tres personas distintas (elaboró / revisó / aprobó);
    una query por rol serían tres round-trips por render, y el freeze corre
    dentro de la transacción de aprobación.
    """
    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}
    rows = session.query(User.id, User.name, User.email).filter(User.id.in_(ids)).all()
    # Fallback al email: un usuario recién sincronizado puede no tener nombre, y
    # una firma vacía en el PDF es peor que una firma con el mail.
    return {uid: (name or email or "") for uid, name, email in rows}


def _document_type_label(session: Session, document: Document) -> str | None:
    """
    Label del tipo documental configurado por el tenant.

    `Document.document_type` guarda el slug; el label es lo que el cliente ve y
    lo que tiene que salir impreso. La resolución es soft por (workspace, key):
    si el tipo fue borrado, se cae al slug antes que dejarlo vacío.
    """
    key = (document.document_type or "").strip()
    if not key:
        return None
    row = (
        session.query(DocumentType.label)
        .filter_by(workspace_id=document.workspace_id, key=key)
        .first()
    )
    return (row[0] if row else None) or key


def _verification_url(version_id: str | None) -> str | None:
    """
    URL pública donde se comprueba si esta versión sigue vigente.

    Apunta a la UI y no a la API: la abre una persona con el teléfono después de
    escanear el QR de la portada. Si no hay base configurada se deriva de
    `api_base_url`, que en local es lo mismo.
    """
    if not version_id:
        return None
    try:
        base = resolve_verification_base_url()
    except RuntimeError:
        # En producción esto no debería pasar: el arranque ya lo valida. Si pasa,
        # el PDF sale SIN QR antes que con una URL que va a morir.
        logger.error(
            "No hay base de verificación configurada: el PDF se genera sin QR. "
            "Seteá DOCUMENT_VERIFICATION_BASE_URL."
        )
        return None
    if not base:
        return None
    return f"{base}/verificar/{version_id}"


def _workspace_name(session: Session, workspace_id: str | None) -> str | None:
    if not workspace_id:
        return None
    row = session.query(Workspace.name).filter_by(id=workspace_id).first()
    return row[0] if row else None


def build_document_context(
    session: Session,
    document: Document,
    version: DocumentVersion | None = None,
) -> DocumentContext:
    """
    Arma el contexto inmutable de `version` dentro de `document`.

    Solo entra lo que queda congelado al aprobar: nada de carpeta, estado actual
    ni referencia al run (ver process_ai_core/export/document_context.py).

    `version=None` es un caso real, no un descuido: el PDF del run (patch por IA)
    se genera ANTES de que exista la versión que lo va a contener. Ahí se llena
    lo que ya es cierto del documento —título, tipo documental, cliente— y los
    campos de versión quedan en None hasta que el freeze arme el contexto
    completo.

    Nunca lanza: un PDF sin una firma es aceptable, un freeze que explota porque
    faltó un dato accesorio no lo es.
    """
    try:
        if version is None:
            return DocumentContext(
                title=document.name,
                document_type_label=_document_type_label(session, document),
                client_name=_workspace_name(session, document.workspace_id),
            )

        supersedes_number = None
        supersedes_approved_at = None
        if version.supersedes_version_id:
            previa = (
                session.query(
                    DocumentVersion.version_number, DocumentVersion.approved_at
                )
                .filter_by(id=version.supersedes_version_id)
                .first()
            )
            if previa:
                supersedes_number, supersedes_approved_at = previa

        # Quien revisó: el validador de la validación asociada a esta versión.
        reviewer_id = None
        if version.validation_id:
            row = (
                session.query(Validation.validator_user_id)
                .filter_by(id=version.validation_id)
                .first()
            )
            reviewer_id = row[0] if row else None

        nombres = _resolve_user_names(
            session, [version.created_by, reviewer_id, version.approved_by]
        )

        return DocumentContext(
            code=document.code,
            title=document.name,
            document_type_label=_document_type_label(session, document),
            client_name=_workspace_name(session, document.workspace_id),
            version_number=version.version_number,
            version_id=version.id,
            is_approved=version.version_status == "APPROVED",
            elaborated_by=nombres.get(version.created_by or ""),
            reviewed_by=nombres.get(reviewer_id or ""),
            approved_by=nombres.get(version.approved_by or ""),
            approved_at=version.approved_at,
            supersedes_version_number=supersedes_number,
            supersedes_approved_at=supersedes_approved_at,
            validity_until=version.validity_until,
            verification_url=_verification_url(version.id),
        )
    except Exception as exc:
        logger.warning(
            "No se pudo armar el DocumentContext de la versión %s: %s. "
            "El PDF se genera sin metadata de gobernanza.",
            getattr(version, "id", "?"), exc,
        )
        return DocumentContext(
            title=getattr(document, "name", None),
            version_number=getattr(version, "version_number", None),
            version_id=getattr(version, "id", None),
            is_approved=getattr(version, "version_status", None) == "APPROVED",
            verification_url=_verification_url(getattr(version, "id", None)),
        )
