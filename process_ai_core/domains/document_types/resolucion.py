"""Qué tipo documental tiene un documento importado, y si eso exige aprobación.

Hasta ahora todo lo que se importaba nacía como `procedimiento` —el default de
la columna, no una decisión— y pedía aprobación siempre, porque la pantalla de
import mandaba `requires_approval` fijo en `true`. El resultado era que una ley
y un procedimiento de pista entraban por el mismo camino, y el acta del PDF
congelado terminaba afirmando que alguien de la organización había aprobado una
ley: un hecho que nunca ocurrió, impreso como evidencia de auditoría.

El criterio no es qué tan importante es el documento sino **de quién es**. Lo
propio se aprueba, porque aprobar es el momento en que una persona se hace
responsable. Lo externo —una ley, un manual de fabricante, un presupuesto que
recibimos de un proveedor— no se aprueba: se incorpora. Eso ya vive en los
`behaviors` de cada tipo (`aprobacion`, `es_referencia`), que estaban definidos
y no los leía nadie.

DE DÓNDE SALE LA DECISIÓN, EN ORDEN
-----------------------------------
1. El tipo que eligió quien importa.
2. Si no eligió, el `default_document_type` de la carpeta (heredado del padre si
   la carpeta no lo define). Por eso en una carpeta "Normativa" no hay que
   decidir nada archivo por archivo.
3. Si tampoco hay, `TIPO_POR_DEFECTO`.

La aprobación NO la manda el cliente: sale del behavior del tipo, resuelto acá
contra la tabla del tenant. Que el cliente pudiera pedir "esto no necesita
aprobación" sería un agujero — publicar sin revisión es exactamente lo que el
flujo de aprobación existe para impedir.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from .defaults import normalize_behaviors

logger = logging.getLogger(__name__)

#: Último recurso: ni quien importa eligió, ni la carpeta define uno. Se elige el
#: tipo más exigente a propósito — que un documento pida una revisión de más es
#: recuperable; que se publique sin revisión porque nadie configuró la carpeta,
#: no.
TIPO_POR_DEFECTO = "procedimiento"


class TipoDocumentalInvalido(ValueError):
    """El tipo pedido no existe (o está inactivo) en este workspace."""


def heredar_default_document_type(folder) -> str | None:
    """El `default_document_type` de la carpeta, o el del ancestro más cercano.

    Réplica deliberada de `resolve_inherited` de la ruta de carpetas: importarla
    desde acá sería que el dominio dependa de la capa de rutas. El recorrido es
    el mismo, incluida la guarda contra ciclos en `parent`.
    """
    actual = folder
    visitados: set[str] = set()
    while actual is not None and actual.id not in visitados:
        visitados.add(actual.id)
        valor = getattr(actual, "default_document_type", None)
        if valor:
            return valor
        actual = getattr(actual, "parent", None)
    return None


def _buscar_tipo(session: Session, workspace_id: str, key: str):
    from process_ai_core.db.models import DocumentType

    return (
        session.query(DocumentType)
        .filter_by(workspace_id=workspace_id, key=key, is_active=True)
        .first()
    )


def resolver_tipo_de_importacion(
    session: Session,
    *,
    workspace_id: str,
    folder,
    tipo_pedido: str | None = None,
) -> tuple[str, bool]:
    """Devuelve `(key_del_tipo, requiere_aprobacion)` para un documento importado.

    Lanza `TipoDocumentalInvalido` solo si el tipo lo pidió EXPLÍCITAMENTE quien
    importa y no existe: ahí hay que avisarle, porque eligió algo que no está.
    Un default de carpeta que quedó apuntando a un tipo borrado no puede hacer
    fallar la importación — se registra y se cae al tipo por defecto, que es el
    más exigente.
    """
    pedido = (tipo_pedido or "").strip()

    if pedido:
        tipo = _buscar_tipo(session, workspace_id, pedido)
        if tipo is None:
            raise TipoDocumentalInvalido(
                f"El tipo documental '{pedido}' no existe o está inactivo en este workspace."
            )
        return tipo.key, _requiere_aprobacion(tipo)

    heredado = heredar_default_document_type(folder)
    if heredado:
        tipo = _buscar_tipo(session, workspace_id, heredado)
        if tipo is not None:
            return tipo.key, _requiere_aprobacion(tipo)
        logger.warning(
            "La carpeta %s tiene default_document_type='%s', que no existe en el "
            "workspace %s; se importa como '%s'",
            getattr(folder, "id", "?"), heredado, workspace_id, TIPO_POR_DEFECTO,
        )

    tipo = _buscar_tipo(session, workspace_id, TIPO_POR_DEFECTO)
    if tipo is not None:
        return tipo.key, _requiere_aprobacion(tipo)

    # El tenant no tiene sembrada su tabla de tipos (o borró el procedimiento).
    # Sin behaviors que consultar, se exige aprobación: es el lado seguro.
    logger.warning(
        "El workspace %s no tiene el tipo '%s'; se importa exigiendo aprobación",
        workspace_id, TIPO_POR_DEFECTO,
    )
    return TIPO_POR_DEFECTO, True


def _requiere_aprobacion(tipo) -> bool:
    try:
        behaviors = normalize_behaviors(json.loads(tipo.behaviors_json or "{}"))
    except (json.JSONDecodeError, TypeError):
        # Behaviors ilegibles: se exige aprobación. Un JSON roto no puede ser el
        # motivo por el que un documento se publique sin que nadie lo mire.
        logger.warning("behaviors_json ilegible en el tipo %s; se exige aprobación", tipo.key)
        return True
    return bool(behaviors.get("aprobacion"))
