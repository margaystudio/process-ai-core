"""
Verificación pública de vigencia de una versión documental.

    GET /api/v1/verify/{version_id}

Es el otro extremo del QR que se imprime en la portada del PDF, y la pieza sobre
la que se apoya la decisión de NO imprimir el estado en el documento: el papel
es inmutable, el estado no, así que el papel remite acá.

Nivel de acceso: PÚBLICO en lo mínimo, con sesión para el detalle
-----------------------------------------------------------------
Sin sesión responde lo que hace falta para actuar sobre una hoja de papel:

  - si la versión sigue vigente o fue superada, y por qué número de versión,
  - la fecha de aprobación y hasta cuándo se comprometió la vigencia,
  - el SHA-256 registrado del PDF.

Con sesión y membresía en el workspace dueño agrega la identificación completa:
código, título, tipo documental y quién aprobó.

El corte está donde está por dos razones. Un documento operativo circula
legítimamente fuera de la organización —un contratista, un inspector, un auditor
con una copia impresa— y esa persona necesita saber si lo que tiene en la mano
sigue valiendo; obligarla a tener cuenta convertiría el QR en un adorno. Pero el
título y el nombre de quien aprueba SON información del cliente: un endpoint
público que devuelva "quién firma los procedimientos de ACME" filtra estructura
interna sin que nadie lo haya pedido.

El `version_id` es un UUID impreso en el PDF: funciona como capability URL — no
se puede adivinar, y quien lo tiene ya tiene el documento. El SHA-256 se expone
sin sesión a propósito: solo sirve si ya tenés el archivo, y es justamente lo que
permite comprobar que el PDF en la mano es el que se aprobó.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Document,
    DocumentType,
    DocumentVersion,
    User,
    Workspace,
    WorkspaceMembership,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/verify", tags=["verification"])


#: Estados que se le muestran a alguien con una copia en la mano. Deliberadamente
#: pocos: la pregunta que trae es "¿esto vale?", no el detalle del ciclo de vida.
_ESTADO_PUBLICO = {
    "APPROVED": "vigente",
    "OBSOLETE": "superada",
    "REJECTED": "rechazada",
    "DRAFT": "sin_aprobar",
    "IN_REVIEW": "sin_aprobar",
}


def _viewer_user_id(authorization: str | None) -> str | None:
    """
    Resuelve el usuario si vino un Bearer válido; None si no.

    No usa `get_current_user_id` como dependencia porque esa lanza 401: acá la
    ausencia de sesión es un caso normal, no un error.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    try:
        from api.dependencies import get_current_user_id

        with get_db_session() as session:
            return get_current_user_id(authorization=authorization, session=session)
    except Exception:
        return None


def _tiene_membresia(session, user_id: str | None, workspace_id: str) -> bool:
    if not user_id:
        return False
    return (
        session.query(WorkspaceMembership.id)
        .filter_by(user_id=user_id, workspace_id=workspace_id)
        .first()
        is not None
    )


@router.get("/{version_id}")
def verify_document_version(
    version_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Estado de vigencia de una versión. Público; con sesión devuelve más detalle.
    """
    viewer_id = _viewer_user_id(authorization)

    with get_db_session() as session:
        version = session.query(DocumentVersion).filter_by(id=version_id).first()
        if not version:
            # 404 sin distinguir "no existe" de "no autorizado": no hay nada que
            # filtrar, el id es público por estar impreso.
            raise HTTPException(
                status_code=404,
                detail="No encontramos ninguna versión con ese identificador.",
            )

        document = session.query(Document).filter_by(id=version.document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="El documento ya no existe.")

        # ¿Qué versión rige hoy? Es lo que convierte al QR en útil: no alcanza con
        # decir "esta fue superada", hay que decir por cuál.
        vigente = (
            session.query(DocumentVersion)
            .filter_by(document_id=document.id, is_current=True, version_status="APPROVED")
            .first()
        )

        es_la_vigente = bool(vigente and vigente.id == version.id)
        respuesta = {
            "version_id": version.id,
            "estado": _ESTADO_PUBLICO.get(version.version_status, "desconocido"),
            "es_version_vigente": es_la_vigente,
            "version_number": version.version_number,
            "approved_at": version.approved_at.isoformat() if version.approved_at else None,
            "validity_until": (
                version.validity_until.isoformat() if version.validity_until else None
            ),
            # Para contrastar contra el PDF que la persona tiene en la mano.
            "pdf_sha256": version.pdf_sha256,
            "version_vigente_number": vigente.version_number if vigente else None,
            "version_vigente_approved_at": (
                vigente.approved_at.isoformat() if vigente and vigente.approved_at else None
            ),
            "detalle_completo": False,
        }

        if not _tiene_membresia(session, viewer_id, document.workspace_id):
            return respuesta

        # ── Detalle solo para miembros del workspace dueño ───────────────────
        aprobador = None
        if version.approved_by:
            fila = session.query(User.name, User.email).filter_by(id=version.approved_by).first()
            if fila:
                aprobador = fila[0] or fila[1]

        tipo = (
            session.query(DocumentType.label)
            .filter_by(workspace_id=document.workspace_id, key=document.document_type)
            .first()
        )
        workspace = session.query(Workspace.name).filter_by(id=document.workspace_id).first()

        respuesta.update(
            {
                "detalle_completo": True,
                "document_id": document.id,
                "code": document.code,
                "title": document.name,
                "document_type_label": (tipo[0] if tipo else None) or document.document_type,
                "approved_by": aprobador,
                "client_name": workspace[0] if workspace else None,
            }
        )
        return respuesta
