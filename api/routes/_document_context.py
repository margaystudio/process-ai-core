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
    OperationalRole,
    User,
    UserOperationalRole,
    Validation,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.config import resolve_verification_base_url
from process_ai_core.export.document_context import DocumentContext, VersionHistoryEntry

logger = logging.getLogger(__name__)


def _resolve_signatories(
    session: Session, workspace_id: str | None, user_ids: list[str | None]
) -> dict[str, tuple[str, str | None]]:
    """Delegado al core: lo comparte con el snapshot del acta al aprobar."""
    from process_ai_core.db.signatories import resolve_signatories

    return resolve_signatories(session, workspace_id, user_ids)


def _collect_version_chain(session: Session, version: DocumentVersion) -> list[DocumentVersion]:
    """
    Versiones aprobadas de la cadena `supersedes_version_id`, de la más nueva a
    la más vieja.

    Se traen TODAS las versiones del documento en una query y la cadena se
    recorre en memoria. Ir saltando de una a otra con una query por eslabón sería
    un N+1 dentro de la transacción de aprobación, que es justo donde no conviene.

    Se sigue la cadena y no se listan todas las versiones: el historial dice qué
    aprobaciones llevaron hasta esta, no cuántos borradores hubo en el camino. Un
    borrador descartado o una versión rechazada no son hitos del documento.
    """
    todas = (
        session.query(DocumentVersion)
        .filter_by(document_id=version.document_id)
        .all()
    )
    por_id = {v.id: v for v in todas}

    cadena: list[DocumentVersion] = []
    actual: DocumentVersion | None = version
    vistos: set[str] = set()
    while actual is not None and actual.id not in vistos:
        vistos.add(actual.id)
        if actual.approved_at is not None:
            cadena.append(actual)
        siguiente = actual.supersedes_version_id
        actual = por_id.get(siguiente) if siguiente else None
    return cadena


def _build_version_history(
    session: Session,
    cadena: list[DocumentVersion],
    nombres: dict[str, tuple[str, str | None]],
) -> tuple[VersionHistoryEntry, ...]:
    """
    Filas del historial a partir de la cadena ya resuelta.

    `change_summary` sale del comentario que el autor escribió al enviar a
    revisión (`Validation.submit_comment`): es quien sabe qué cambió, y el
    aprobador lo tuvo a la vista antes de aprobar. Los nombres vienen resueltos
    de afuera para no repetir la consulta de usuarios.
    """
    if not cadena:
        return ()

    # Un solo lote para todos los comentarios de la cadena.
    validation_ids = [v.validation_id for v in cadena if v.validation_id]
    resumenes: dict[str, str] = {}
    if validation_ids:
        for vid, comentario in (
            session.query(Validation.id, Validation.submit_comment)
            .filter(Validation.id.in_(validation_ids))
            .all()
        ):
            texto = (comentario or "").strip()
            if texto:
                resumenes[vid] = texto

    return tuple(
        VersionHistoryEntry(
            version_number=v.version_number,
            approved_at=v.approved_at,
            approved_by=nombres.get(v.approved_by or "", ("", None))[0] or None,
            change_summary=resumenes.get(v.validation_id or ""),
        )
        for v in cadena
    )


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

        # La cadena primero, para resolver de UNA los nombres de los firmantes
        # del acta y de todos los aprobadores del historial.
        cadena = _collect_version_chain(session, version)
        firmantes = _resolve_signatories(
            session,
            document.workspace_id,
            [version.created_by, reviewer_id, version.approved_by]
            + [v.approved_by for v in cadena],
        )

        # ── Acta: se PREFIERE lo congelado al aprobar ────────────────────
        # Si la versión trae el snapshot (migración 0017), esos son los valores
        # del momento de la aprobación y son los que valen. El lookup queda solo
        # para versiones anteriores al cambio: para esas no hay dato congelado y
        # es lo mejor disponible, aunque pueda haber envejecido.
        congelado = bool(version.acta_approved_by_name or version.acta_elaborated_by_name)

        def _acta(campo_snapshot, uid, indice):
            valor = getattr(version, campo_snapshot, None)
            if congelado:
                return valor
            return firmantes.get(uid or "", (None, None))[indice]

        return DocumentContext(
            code=document.code,
            title=document.name,
            document_type_label=_document_type_label(session, document),
            client_name=(
                version.acta_client_name
                if congelado and version.acta_client_name
                else _workspace_name(session, document.workspace_id)
            ),
            version_number=version.version_number,
            version_id=version.id,
            is_approved=version.version_status == "APPROVED",
            elaborated_by=_acta("acta_elaborated_by_name", version.created_by, 0),
            reviewed_by=_acta("acta_reviewed_by_name", reviewer_id, 0),
            approved_by=_acta("acta_approved_by_name", version.approved_by, 0),
            elaborated_by_role=_acta("acta_elaborated_by_role", version.created_by, 1),
            reviewed_by_role=_acta("acta_reviewed_by_role", reviewer_id, 1),
            approved_by_role=_acta("acta_approved_by_role", version.approved_by, 1),
            version_history=_build_version_history(session, cadena, firmantes),
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
