"""
Resolución de los firmantes del acta: nombre + rol operativo.

Vive en el core y no en `api/` porque lo usan dos lados que no deberían
depender entre sí: el flujo de aprobación, que congela estos valores en la
versión, y la construcción del `DocumentContext`, que los lee para imprimir.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def resolve_signatories(
    session: Session, workspace_id: str | None, user_ids: list[str | None]
) -> dict[str, tuple[str, str | None]]:
    """
    Resuelve varios user_id a (nombre, rol operativo) en UNA query.

    El rol es el **operativo** ("Encargado de turno", "Gerente de Estación"), no
    el de sistema (owner/admin/approver). Un acta que dijera "aprobado por Juan
    Pérez, approver" no aporta autoridad: describe un permiso, no una posición
    en la organización. Sin rol operativo el campo queda en None y el acta lo
    omite, en vez de caer a algo que no significa lo mismo.

    Si alguien tiene más de un rol se toma el primero por nombre, para que el
    resultado sea determinista y el PDF reproducible.
    """
    from process_ai_core.db.models import (
        OperationalRole,
        User,
        UserOperationalRole,
        WorkspaceMembership,
    )

    ids = {uid for uid in user_ids if uid}
    if not ids:
        return {}

    filas = (
        session.query(User.id, User.name, User.email, OperationalRole.name)
        .outerjoin(
            WorkspaceMembership,
            (WorkspaceMembership.user_id == User.id)
            & (WorkspaceMembership.workspace_id == workspace_id),
        )
        .outerjoin(
            UserOperationalRole,
            UserOperationalRole.workspace_membership_id == WorkspaceMembership.id,
        )
        .outerjoin(
            OperationalRole,
            (OperationalRole.id == UserOperationalRole.operational_role_id)
            & (OperationalRole.is_active.is_(True)),
        )
        .filter(User.id.in_(ids))
        .order_by(User.id, OperationalRole.name)
        .all()
    )

    resultado: dict[str, tuple[str, str | None]] = {}
    for uid, nombre, email, rol in filas:
        if uid in resultado and resultado[uid][1]:
            continue  # ya tiene rol: el order_by garantiza cuál
        # Fallback al email: un usuario recién sincronizado puede no tener
        # nombre, y una firma vacía en el PDF es peor que una firma con el mail.
        resultado[uid] = ((nombre or email or ""), rol or None)
    return resultado


def snapshot_acta_fields(session: Session, version) -> None:
    """
    Congela en la versión los datos del acta, en el momento de aprobar.

    Por qué no basta con resolverlos al imprimir
    --------------------------------------------
    Mientras el PDF esté congelado no hay diferencia: el que quedó impreso es
    correcto para siempre. Pero el RE-FREEZE existe —una versión APPROVED sin
    `pdf_storage_key` se congela al servirla— y toma los valores ACTUALES. Si
    Juan Pérez aprobó como "Encargado de turno" y después ascendió a "Gerente",
    el PDF regenerado le atribuiría a esa aprobación una autoridad que no tenía:
    exactamente la clase de afirmación falsa que este diseño existe para impedir.

    El riesgo no es teórico y además creció: desde que el freeze ABORTA cuando
    falta una evidencia, un documento aprobado hoy puede congelarse recién la
    semana que viene, con la organización ya cambiada.

    Se guarda TEXTO y no FK a propósito. Una FK sigue los renombres: si mañana
    el rol "Encargado de turno" pasa a llamarse "Supervisor de playa", el acta
    de una aprobación de 2026 diría "Supervisor de playa". El acta registra qué
    decía el cargo ESE día, no cómo se llama hoy.
    """
    from process_ai_core.db.models import Document, Validation

    documento = session.query(Document).filter_by(id=version.document_id).first()
    if not documento:
        return

    revisor_id = None
    if version.validation_id:
        fila = (
            session.query(Validation.validator_user_id)
            .filter_by(id=version.validation_id)
            .first()
        )
        revisor_id = fila[0] if fila else None

    firmantes = resolve_signatories(
        session,
        documento.workspace_id,
        [version.created_by, revisor_id, version.approved_by],
    )

    def datos(uid):
        return firmantes.get(uid or "", (None, None))

    version.acta_elaborated_by_name, version.acta_elaborated_by_role = datos(version.created_by)
    version.acta_reviewed_by_name, version.acta_reviewed_by_role = datos(revisor_id)
    version.acta_approved_by_name, version.acta_approved_by_role = datos(version.approved_by)

    # El nombre del cliente también: un workspace se puede renombrar, y el acta
    # dice a nombre de quién se aprobó ese día.
    if documento.workspace_id:
        from process_ai_core.db.models import Workspace

        fila = session.query(Workspace.name).filter_by(id=documento.workspace_id).first()
        version.acta_client_name = fila[0] if fila else None
