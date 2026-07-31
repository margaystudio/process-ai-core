"""relacion_decided_by

`document_relations.confirmed_by` → `decided_by` y `confirmed_at` → `decided_at`.

POR QUÉ: EL NOMBRE MENTÍA
-------------------------
Las dos columnas se escriben en `confirm()` **y** en `reject()`
(`process_ai_core/semantic/relations.py`). O sea que en una relación rechazada,
`confirmed_by` guardaba a quien la **rechazó** y `confirmed_at` el momento del
**rechazo**. El campo no dice quién confirmó: dice **quién decidió**.

No es cosmética. Estos campos son de gobierno: distinguen una relación que validó
una persona de una que aceptó el pipeline solo (`decided_by IS NULL` es el rastro
de "confirmada por el sistema, sin intervención humana" — ver
`process_ai_core/config.py`). El día que eso se muestre en pantalla, un
`confirmed_by` al lado de un `status='rejected'` se lee como una contradicción, y
quien lo lea va a desconfiar del dato o —peor— va a filtrar por él creyendo que
solo trae confirmaciones.

Se renombra ANTES de exponerlo en la UI a propósito. Hoy el campo viaja en la API
(`api/routes/semantic.py`) y ninguna pantalla lo pinta: es el momento más barato
para arreglarlo. Después de que una pantalla lo muestre, el nombre queda.

RENAME, NO ADD+COPY+DROP
------------------------
`ALTER TABLE ... RENAME COLUMN` conserva los datos, el tipo, la FK y los índices,
y es instantáneo: no reescribe la tabla. Como el módulo despliega el código y la
migración juntos (no hay ventana de convivencia), no hace falta el baile de
agregar la nueva, copiar, y borrar la vieja.

Revision ID: 0023_relacion_decided_by
Revises: 0022_id_canonico
Create Date: 2026-07-31
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0023_relacion_decided_by"
down_revision = "0022_id_canonico"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def _renombrar(conn, viejo: str, nuevo: str) -> None:
    """Renombra si existe la vieja y no existe la nueva. Idempotente."""
    existe_vieja = conn.execute(
        text(
            """
            SELECT count(*) FROM information_schema.columns
             WHERE table_schema = :s AND table_name = 'document_relations'
               AND column_name = :c
            """
        ),
        {"s": SCHEMA, "c": viejo},
    ).scalar()
    existe_nueva = conn.execute(
        text(
            """
            SELECT count(*) FROM information_schema.columns
             WHERE table_schema = :s AND table_name = 'document_relations'
               AND column_name = :c
            """
        ),
        {"s": SCHEMA, "c": nuevo},
    ).scalar()
    if existe_vieja and not existe_nueva:
        conn.execute(
            text(
                f'ALTER TABLE "{SCHEMA}".document_relations '
                f"RENAME COLUMN {viejo} TO {nuevo}"
            )
        )


def upgrade() -> None:
    conn = op.get_bind()
    _renombrar(conn, "confirmed_by", "decided_by")
    _renombrar(conn, "confirmed_at", "decided_at")

    conn.execute(
        text(
            f"""
            COMMENT ON COLUMN "{SCHEMA}".document_relations.decided_by IS
            'Quién DECIDIÓ sobre la relación: se escribe tanto al confirmar como '
            'al rechazar. NULL = la confirmó el sistema, sin intervención humana '
            '(ver process_ai_core/config.py). Antes se llamaba confirmed_by, que '
            'mentía en las relaciones rechazadas.'
            """
        )
    )
    conn.execute(
        text(
            f"""
            COMMENT ON COLUMN "{SCHEMA}".document_relations.decided_at IS
            'Momento de la decisión (confirmación O rechazo). Antes confirmed_at.'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    _renombrar(conn, "decided_by", "confirmed_by")
    _renombrar(conn, "decided_at", "confirmed_at")
