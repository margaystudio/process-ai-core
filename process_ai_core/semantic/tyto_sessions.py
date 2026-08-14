"""
Conversaciones de Tyto: resolución, título y lectura del historial.

QUIÉN CREA LA SESIÓN: EL SERVIDOR
---------------------------------
La alternativa era que el cliente generara un UUID y lo mandara. Se descartó por
dos motivos, en ese orden:

1. **Un id que elige el cliente es un id que elige cualquiera.** El historial es
   estrictamente personal, así que un id enviado por el usuario tiene que
   validarse contra su dueño de todas formas. Si igual hay que verificar la
   propiedad en el servidor, que el servidor lo emita no cuesta nada y elimina
   la clase entera de error "mandé el id de otro".

2. **El cliente no puede inventar el título.** El título sale de la primera
   pregunta y se guarda con la sesión; con creación en el cliente habría que
   mandarlo aparte o dejar la fila a medias.

Cómo vuelve el id al cliente, que era la parte a mirar antes de elegir: el POST
síncrono lo devuelve en el cuerpo, y el streaming emite un evento SSE `session`
ANTES del primer token. Ponerlo solo en el `result` final habría sido más simple
y estaba mal: si el stream muere a mitad —que es justo cuando falla el proveedor—
el cliente nunca se entera del id, la próxima pregunta abre otra conversación, y
el historial se llena de sesiones de un mensaje. Que es exactamente la basura que
esta tarea existe para evitar.

REGLA DE ACCESO
---------------
Todo lo que lee acá filtra por `user_id` ADEMÁS de `workspace_id`, sin excepción
de rol. No hay una variante "para admins": un registro de qué preguntó cada
persona revela lo que esa persona no sabe, y un supervisor que puede leerlo
convierte a Tyto en vigilancia. La gente deja de preguntar y el producto pierde
lo único que necesitaba que hicieran. Para brechas documentales está
`tyto_query_log` agregado y anónimo.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, UTC

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.models_semantic import TytoQueryLog, TytoSession

logger = logging.getLogger(__name__)

#: Largo del título derivado. Entra en una barra lateral angosta sin cortar una
#: palabra al medio; el usuario lo renombra si no le gusta.
TITULO_MAX = 80


def derive_title(question: str) -> str:
    """
    Título a partir de la primera pregunta. Sin LLM, a propósito.

    Pedirle a un modelo que resuma esto cuesta plata y agrega latencia a cada
    conversación nueva, para producir algo que el usuario corrige en un clic. La
    primera pregunta ya es, casi siempre, de qué se trata el hilo.
    """
    limpio = re.sub(r"\s+", " ", (question or "").strip())
    if not limpio:
        return "Consulta sin título"
    if len(limpio) <= TITULO_MAX:
        return limpio
    # Corte en el último espacio, para no partir una palabra al medio.
    recortado = limpio[:TITULO_MAX].rsplit(" ", 1)[0] or limpio[:TITULO_MAX]
    return f"{recortado}…"


def resolve_session(
    session: Session,
    *,
    workspace_id: str,
    user_id: str,
    session_id: str | None,
    question: str,
) -> TytoSession:
    """
    Devuelve la conversación a la que pertenece esta pregunta, creándola si hace falta.

    Si llega un `session_id` que no existe o que es de otro usuario u otro
    workspace, NO se falla con un error: se abre una conversación nueva. Un id
    inválido no puede costarle al usuario la pregunta que acaba de escribir, y
    devolver 403 ante un id ajeno confirmaría que ese id existe.
    """
    if session_id:
        existente = session.execute(
            select(TytoSession).where(
                TytoSession.id == session_id,
                TytoSession.workspace_id == workspace_id,
                TytoSession.user_id == user_id,
            )
        ).scalar_one_or_none()
        if existente is not None:
            # `updated_at` es el orden de "recientes": se toca con cada pregunta.
            existente.updated_at = datetime.now(UTC).replace(tzinfo=None)
            session.flush()
            return existente
        logger.info(
            "Tyto: session_id %s no pertenece a este usuario/workspace; se abre una nueva",
            session_id,
        )

    nueva = TytoSession(
        workspace_id=workspace_id,
        user_id=user_id,
        title=derive_title(question),
    )
    session.add(nueva)
    session.flush()
    return nueva


def list_sessions(
    session: Session,
    *,
    workspace_id: str,
    user_id: str,
    limit: int = 50,
    buscar: str | None = None,
) -> list[TytoSession]:
    """
    Las conversaciones del usuario, ancladas primero y después por recientes.

    Con `buscar`, filtra por el título **o por el texto de las preguntas** de la
    conversación. Las dos cosas, porque la pregunta que uno recuerda casi nunca
    es la primera —que es la que da el título—: se busca "cierre de caja" y eso
    puede haber aparecido en la tercera repregunta de un hilo que se llama otra
    cosa.
    """
    condiciones = [
        TytoSession.workspace_id == workspace_id,
        # Este filtro no es negociable: ver el docstring del módulo.
        TytoSession.user_id == user_id,
    ]

    if buscar and buscar.strip():
        patron = f"%{buscar.strip()}%"
        # Subconsulta sobre las preguntas del hilo. Se acota por workspace_id
        # además de session_id: el log no tiene dueño confiable (user_id puede
        # ser null), así que el alcance lo da la sesión, ya filtrada arriba.
        con_la_pregunta = (
            select(TytoQueryLog.session_id)
            .where(
                TytoQueryLog.workspace_id == workspace_id,
                TytoQueryLog.question.ilike(patron),
            )
            .scalar_subquery()
        )
        condiciones.append(
            or_(
                TytoSession.title.ilike(patron),
                TytoSession.id.in_(con_la_pregunta),
            )
        )

    return list(
        session.execute(
            select(TytoSession)
            .where(*condiciones)
            .order_by(TytoSession.pinned.desc(), TytoSession.updated_at.desc())
            .limit(limit)
        ).scalars()
    )


def get_own_session(
    session: Session, *, workspace_id: str, user_id: str, session_id: str
) -> TytoSession | None:
    """La sesión, solo si es del usuario. None en cualquier otro caso."""
    return session.execute(
        select(TytoSession).where(
            TytoSession.id == session_id,
            TytoSession.workspace_id == workspace_id,
            TytoSession.user_id == user_id,
        )
    ).scalar_one_or_none()


def update_session(
    session: Session,
    *,
    workspace_id: str,
    user_id: str,
    session_id: str,
    title: str | None = None,
    pinned: bool | None = None,
) -> TytoSession | None:
    """Renombra y/o ancla una conversación propia.

    El título lo edita el usuario y por eso NO se deriva de nada acá: si alguien
    lo cambió, una regeneración automática se lo pisaría en la siguiente
    pregunta. Se recorta al largo de la columna en vez de rechazar, que para un
    título es lo que espera cualquiera.
    """
    convo = get_own_session(
        session, workspace_id=workspace_id, user_id=user_id, session_id=session_id
    )
    if convo is None:
        return None
    if title is not None:
        limpio = title.strip()
        if limpio:
            convo.title = limpio[:200]
    if pinned is not None:
        convo.pinned = pinned
    session.flush()
    return convo


def delete_session(
    session: Session, *, workspace_id: str, user_id: str, session_id: str
) -> bool:
    """
    Borra una conversación propia. Devuelve False si no era del usuario.

    Borra SOLO la fila de `tyto_session` y desliga sus preguntas
    (`session_id = NULL`). El rastro en `tyto_query_log` se conserva a
    propósito: alimenta la detección de brechas documentales, que es agregada y
    anónima, y tiene que seguir funcionando aunque la persona limpie su
    historial. Borrar la conversación es una acción sobre SU vista, no sobre el
    rastro del sistema — es exactamente el motivo por el que ese log no tiene
    foreign key a esta tabla.
    """
    convo = get_own_session(
        session, workspace_id=workspace_id, user_id=user_id, session_id=session_id
    )
    if convo is None:
        return False
    session.query(TytoQueryLog).filter(
        TytoQueryLog.session_id == session_id
    ).update({TytoQueryLog.session_id: None}, synchronize_session=False)
    session.delete(convo)
    session.flush()
    return True


def turnos_previos(
    session: Session, *, session_id: str, limite: int = 3
) -> list[tuple[str, str]]:
    """Los últimos intercambios RESPONDIDOS de una conversación, en orden.

    Es lo que le da sentido a una repregunta: "¿y si se pasa del límite?" no
    significa nada sola. Se piden acá y no dentro del servicio de respuesta
    porque la sesión ya está resuelta y verificada en la ruta — el servicio no
    tiene por qué saber de dueños de conversaciones.

    Se excluyen los turnos NO respondidos a propósito: arrastrar un "no tengo
    documentación para eso" como contexto solo agrega ruido a la búsqueda y le
    sugiere al modelo que el tema no está documentado.
    """
    filas = list(
        session.execute(
            select(TytoQueryLog.question, TytoQueryLog.answer)
            .where(
                TytoQueryLog.session_id == session_id,
                TytoQueryLog.answered.is_(True),
            )
            .order_by(TytoQueryLog.created_at.desc(), TytoQueryLog.id.desc())
            .limit(limite)
        )
    )
    filas.reverse()  # del más viejo al más nuevo: así se lee una conversación
    return [(q, a or "") for q, a in filas]


def get_session_thread(
    session: Session, *, workspace_id: str, user_id: str, session_id: str
) -> tuple[TytoSession | None, list[TytoQueryLog]]:
    """
    Una conversación y sus preguntas en orden.

    Devuelve `(None, [])` si la sesión no es del usuario. La verificación va
    sobre `tyto_session` —que sí tiene dueño— y recién después se traen las
    filas del log por `session_id`: el log no tiene user_id confiable para esto
    (puede ser null) y filtrar por ahí sería apoyar el control de acceso en una
    columna que la tabla no garantiza.
    """
    convo = session.execute(
        select(TytoSession).where(
            TytoSession.id == session_id,
            TytoSession.workspace_id == workspace_id,
            TytoSession.user_id == user_id,
        )
    ).scalar_one_or_none()
    if convo is None:
        return None, []

    entradas = list(
        session.execute(
            select(TytoQueryLog)
            .where(TytoQueryLog.session_id == session_id)
            .order_by(TytoQueryLog.created_at.asc(), TytoQueryLog.id.asc())
        ).scalars()
    )
    return convo, entradas
