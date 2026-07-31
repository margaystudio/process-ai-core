"""auth_muerta_compat

Primer tiempo de la eliminación de la auth muerta: hace que `users.password_hash`
deje de ser obligatoria, para que el código nuevo (que ya no la escribe) y el
viejo (que la escribe en "") funcionen **los dos** contra la misma base.

POR QUÉ ESTE PASO EXISTE
------------------------
`password_hash` es `NOT NULL` y su default vivía en SQLAlchemy (`default=""`), no
en el servidor. Entonces, apenas el modelo deja de declarar la columna, el INSERT
no la manda y Postgres rechaza la fila:

    NotNullViolation: null value in column "password_hash" of relation "users"

Es decir: sacar la columna del modelo y borrarla después NO es un two-step seguro
— es un cambio rompedor con un paso de más. Entre el deploy del código y la
migración hay una ventana donde nada anda.

Con `SET DEFAULT ''` la ventana desaparece en las dos direcciones:

  - código viejo → sigue mandando "" explícitamente. Funciona.
  - código nuevo → no la manda, Postgres pone "". Funciona.
  - rollback del código → sigue funcionando, sin revertir la migración.

Recién cuando el código nuevo esté deployado en todos lados, la 0020 borra la
columna y la tabla de invitaciones.

ORDEN DE APLICACIÓN
-------------------
  1. Esta migración (0019). Se puede aplicar YA, con el código viejo corriendo:
     no rompe nada y no destruye nada.
  2. Deploy del código que ya no usa `password_hash` ni `workspace_invitations`.
  3. Migración 0020 (`DROP`), una vez que no queda código apuntando a ellas.

Referencia: `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`,
sección "Process AI: qué está muerto y qué no".

Revision ID: 0019_auth_muerta_compat
Revises: 0018_tyto_session
Create Date: 2026-07-29
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0019_auth_muerta_compat"
down_revision = "0018_tyto_session"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def upgrade() -> None:
    # Default del lado del servidor: el INSERT que no manda la columna ya no falla.
    op.execute(
        text(f"""ALTER TABLE "{SCHEMA}".users ALTER COLUMN password_hash SET DEFAULT ''""")
    )


def downgrade() -> None:
    op.execute(
        text(f'ALTER TABLE "{SCHEMA}".users ALTER COLUMN password_hash DROP DEFAULT')
    )
