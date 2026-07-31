"""
Codificación documental: asignación del `code` de un documento (ADR-019).

Formato: `{PREFIJO}-{SECUENCIAL}`, ej. `PR-0042`, `PO-0007`, `IT-0113`.

Reglas que este módulo implementa
---------------------------------
- **No significativo respecto de la ubicación.** El código no se deriva de la
  carpeta ni de ningún dato del organigrama. Los "significant numbers" son
  frágiles: cuando la organización se reordena, o se renumera todo (y se pierde
  la trazabilidad) o el código pasa a mentir.
- **Prefijo por TIPO DOCUMENTAL.** Es la única semántica admitida, porque el tipo
  cambia mucho menos que el organigrama.
- **Secuencial por workspace y prefijo**, con padding a 4 dígitos.
- **Nunca se reutiliza ni se reasigna.** El contador es monótono y vive en su
  propia tabla: borrar un documento no libera su número. Reciclar un código
  haría que dos documentos distintos hayan sido "PR-0042" en momentos distintos,
  que es exactamente lo que un archivo documental no puede permitirse.
- **Único por workspace**, con índice único como respaldo del contador.

Concurrencia
------------
Dos documentos creados a la vez en el mismo workspace no pueden recibir el mismo
número. El contador se incrementa con un único `INSERT ... ON CONFLICT DO UPDATE
... RETURNING`, que es atómico en Postgres: el segundo request espera el lock de
fila del primero y recibe el valor siguiente. No hace falta `SELECT max(...) FOR
UPDATE` ni un lock explícito, que además serializarían más de lo necesario.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Dígitos del secuencial. 4 llega a 9999 documentos por tipo y workspace; al
#: pasarse, el número crece a 5 dígitos y el orden lexicográfico se rompe pero el
#: código sigue siendo único y válido. Es preferible a fallar.
CODE_PADDING = 4

#: Prefijo cuando el tipo documental no declara uno y no se puede derivar.
FALLBACK_PREFIX = "DO"

_NON_ALPHA = re.compile(r"[^A-Z]")


def _strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def derive_prefix(key_or_label: str) -> str:
    """
    Prefijo de dos letras a partir del key o label de un tipo documental.

    Solo se usa para tipos personalizados que no declararon `code_prefix`. Los
    tipos sembrados traen el suyo explícito (ver defaults.py), porque un prefijo
    derivado puede colisionar entre tipos distintos — y eso está bien: el par
    (prefijo, secuencial) sigue siendo único porque el contador es por prefijo.
    """
    limpio = _NON_ALPHA.sub("", _strip_accents(key_or_label or "").upper())
    if len(limpio) >= 2:
        return limpio[:2]
    return FALLBACK_PREFIX


def code_prefix_for(session: Session, workspace_id: str, document_type_key: str | None) -> str:
    """Prefijo configurado para ese tipo en ese workspace, o uno derivado."""
    from process_ai_core.db.models import DocumentType

    key = (document_type_key or "").strip()
    if not key:
        return FALLBACK_PREFIX

    fila = (
        session.query(DocumentType.code_prefix, DocumentType.label)
        .filter_by(workspace_id=workspace_id, key=key)
        .first()
    )
    if fila and fila[0]:
        return fila[0].strip().upper()
    return derive_prefix(key if not fila else (fila[1] or key))


def next_sequence(session: Session, workspace_id: str, prefix: str) -> int:
    """
    Reserva y devuelve el siguiente secuencial para (workspace, prefijo).

    Una sola sentencia atómica: el `ON CONFLICT DO UPDATE ... RETURNING` toma el
    lock de la fila del contador, incrementa y devuelve el valor nuevo. Dos
    creaciones concurrentes se serializan en ese lock y obtienen números
    distintos.
    """
    from process_ai_core.db.database import DATABASE_SCHEMA

    tabla = f"{DATABASE_SCHEMA}.document_code_counters" if DATABASE_SCHEMA else "document_code_counters"
    fila = session.execute(
        text(
            f"""
            INSERT INTO {tabla} (workspace_id, prefix, next_value)
            VALUES (:ws, :prefix, 1)
            ON CONFLICT (workspace_id, prefix)
            DO UPDATE SET next_value = {tabla.split('.')[-1]}.next_value + 1
            RETURNING next_value
            """
        ),
        {"ws": workspace_id, "prefix": prefix},
    ).first()
    return int(fila[0])


def format_code(prefix: str, sequence: int) -> str:
    return f"{prefix}-{sequence:0{CODE_PADDING}d}"


def _code_taken(session: Session, workspace_id: str, code: str) -> bool:
    from process_ai_core.db.models import Document

    return (
        session.query(Document.id).filter_by(workspace_id=workspace_id, code=code).first()
        is not None
    )


def generate_document_code(
    session: Session,
    workspace_id: str,
    document_type_key: str | None,
    *,
    max_intentos: int = 5,
) -> str:
    """
    Genera el siguiente código libre para un documento nuevo.

    El contador ya garantiza unicidad, pero un código puesto a mano puede haber
    ocupado un número de la serie. En ese caso se avanza el contador hasta
    encontrar uno libre, en vez de fallar la creación del documento.
    """
    prefijo = code_prefix_for(session, workspace_id, document_type_key)
    for _ in range(max_intentos):
        codigo = format_code(prefijo, next_sequence(session, workspace_id, prefijo))
        if not _code_taken(session, workspace_id, codigo):
            return codigo
        logger.warning(
            "El código %s del workspace %s ya estaba ocupado (override manual); "
            "se avanza el contador.", codigo, workspace_id,
        )
    raise ValueError(
        f"No se pudo generar un código libre para el prefijo {prefijo} en el "
        f"workspace {workspace_id} después de {max_intentos} intentos."
    )


def assign_document_code(
    session: Session,
    document,
    *,
    override: str | None = None,
) -> str:
    """
    Asigna el código a un documento recién creado.

    Idempotente: si el documento ya tiene código, lo devuelve sin tocarlo. Es el
    guardarraíl del invariante — el código no se reasigna nunca.

    Args:
        override: código elegido a mano. Se normaliza y se valida que esté libre
                  en el workspace.
    """
    if getattr(document, "code", None):
        return document.code

    if override and override.strip():
        codigo = override.strip().upper()
        if _code_taken(session, document.workspace_id, codigo):
            raise ValueError(f"El código {codigo} ya está en uso en este workspace.")
        document.code = codigo
        # flush explícito: sin esto el código queda solo en memoria y la próxima
        # comprobación de unicidad no lo ve, así que dos documentos creados en la
        # misma sesión podrían quedarse con el mismo.
        session.flush()
        return codigo

    document.code = generate_document_code(
        session, document.workspace_id, getattr(document, "document_type", None)
    )
    session.flush()
    return document.code
