"""tyto_session

Agrupador de conversación para Tyto, y las dos columnas que le faltaban al log
para poder reconstruir un hilo al recargar la página.

  - tyto_session                 : la conversación (id, workspace, usuario,
                                   título, anclado, timestamps)
  - tyto_query_log.session_id    : a qué conversación pertenece cada pregunta
  - tyto_query_log.answer        : el texto de la respuesta

SIN FOREIGN KEY EN session_id, A PROPÓSITO
------------------------------------------
`tyto_query_log` es una tabla de auditoría deliberadamente desacoplada: ya no
tiene FK a documentos ni a usuarios, para que el rastro sobreviva a los borrados.
`session_id` sigue esa misma regla y por el mismo motivo.

Con una FK, borrar una conversación del historial personal arrastraría (CASCADE)
o bloquearía (RESTRICT) filas de auditoría. Las dos están mal: el log alimenta la
detección de brechas documentales (ADR-011), que tiene que seguir funcionando
aunque la persona limpie su historial. Borrar una conversación es una acción
sobre la vista del usuario, no sobre el rastro del sistema. Un `session_id`
huérfano es el estado correcto, no una inconsistencia.

Índices
-------
  ix_tyto_session_ws_user_updated  (workspace_id, user_id, updated_at DESC)
      El listado de "recientes". Lleva user_id porque NO existe un listado sin
      él: el historial es solo para uno mismo, sin excepción de rol.
  ix_tyto_query_log_session        (session_id, created_at)
      Reconstruir un hilo en orden.

Revision ID: 0018_tyto_session
Revises: 0017_acta_snapshot
Create Date: 2026-07-29
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0018_tyto_session"
down_revision = "0017_acta_snapshot"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text(
            f'''
            CREATE TABLE IF NOT EXISTS "{SCHEMA}".tyto_session (
                id            varchar(36) PRIMARY KEY,
                workspace_id  varchar(36) NOT NULL,
                user_id       varchar(36) NOT NULL,
                title         varchar(200) NOT NULL DEFAULT '',
                pinned        boolean NOT NULL DEFAULT false,
                created_at    timestamp NOT NULL DEFAULT now(),
                updated_at    timestamp NOT NULL DEFAULT now()
            )
            '''
        )
    )
    conn.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS ix_tyto_session_workspace_id '
            f'ON "{SCHEMA}".tyto_session (workspace_id)'
        )
    )
    conn.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS ix_tyto_session_user_id '
            f'ON "{SCHEMA}".tyto_session (user_id)'
        )
    )
    conn.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS ix_tyto_session_ws_user_updated '
            f'ON "{SCHEMA}".tyto_session (workspace_id, user_id, updated_at DESC)'
        )
    )

    # ── tyto_query_log: la conversación y el texto de la respuesta ───────────
    conn.execute(
        text(
            f'ALTER TABLE "{SCHEMA}".tyto_query_log '
            f"ADD COLUMN IF NOT EXISTS session_id varchar(36)"
        )
    )
    # NOTA: sin FOREIGN KEY, a propósito. Ver el docstring de esta migración y el
    # del campo en process_ai_core/db/models_semantic.py.
    conn.execute(
        text(
            f'ALTER TABLE "{SCHEMA}".tyto_query_log '
            f"ADD COLUMN IF NOT EXISTS answer text NOT NULL DEFAULT ''"
        )
    )
    conn.execute(
        text(
            f'CREATE INDEX IF NOT EXISTS ix_tyto_query_log_session '
            f'ON "{SCHEMA}".tyto_query_log (session_id, created_at)'
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA}".ix_tyto_query_log_session'))
    conn.execute(
        text(f'ALTER TABLE "{SCHEMA}".tyto_query_log DROP COLUMN IF EXISTS answer')
    )
    conn.execute(
        text(f'ALTER TABLE "{SCHEMA}".tyto_query_log DROP COLUMN IF EXISTS session_id')
    )
    # Las conversaciones se pierden; el rastro de auditoría queda intacto, que es
    # justamente lo que la ausencia de FK garantiza.
    conn.execute(text(f'DROP TABLE IF EXISTS "{SCHEMA}".tyto_session'))
