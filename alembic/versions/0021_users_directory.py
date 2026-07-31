"""users_directory

`process_ai.users_directory` — el directorio de usuarios del módulo, poblado por
**escritura al leer** desde `GET /api/tenants/{tid}/applications/{key}/directory`
de margay-workspace.

Implementa el §2 y el §3 de `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`.
Calcado de `margay-crm/migrations/032_users_directory.sql` (el piloto) y de
`margay-dashboards` (`analytics.users_directory`).

QUÉ AGREGA, EXACTAMENTE
-----------------------
Process AI ya hacía escritura al leer antes de que el estándar existiera:
`sync_workspace_access` (`api/workspace_client.py`) trae el `session/context` por
request y hace upsert del `User` y la `WorkspaceMembership` locales. Eso NO se
toca — es el §3 resuelto a mano.

Pero `session/context` solo trae al **usuario actual**, así que `process_ai.users`
es la proyección de "quien se logueó alguna vez". Sobre esa base, lo que suma esta
tabla es concreto y conviene no exagerarlo:

  1. FRESCURA. `get_or_create_local_user_from_workspace` escribe `users.name` al
     CREAR la fila y después nunca más (encuentra por `external_id` y retorna).
     Si la persona se cambia el nombre en el Hub, Process AI le sigue diciendo
     como se llamaba el día que entró por primera vez. El directorio se refresca
     por TTL cuando CUALQUIER miembro del módulo lee un nombre.
  2. FORMATO CANÓNICO. `display_name` lo calcula Workspace
     (`app/services/display_name.py`) y viaja en el DTO. El módulo no concatena
     nombre y apellido (anti-patrón #6) — así nacieron las nueve columnas
     `*_by_name` de OMS.
  3. COBERTURA. Alcanza a los miembros del módulo que todavía no entraron nunca,
     que hoy no existen en `process_ai.users` en absoluto. Es lo que habilita un
     selector de aprobadores real (`validations.assigned_approver_ids` hoy se
     llena con ids que el que envía tiene que conocer de antemano).

CÓMO SE LLENA
-------------
Escritura al leer, nunca un job/cron/webhook/trigger: el código que lee es el que
escribe (§3). Eso es lo que evita repetir el fracaso de `oms.tenant_users_cache`,
que se creó, el sync nunca se escribió, quedó en 0 filas y nadie se enteró. Si
esta tabla está vacía es porque nadie está resolviendo nombres, no porque el sync
se rompió.

TIPOS: VARCHAR, NO UUID — DESVÍO DELIBERADO DEL §2
--------------------------------------------------
El §2 define las columnas de id como `uuid`. Acá son `VARCHAR`, porque en
`process_ai` **todos** los ids son `VARCHAR(36)` (`users.id`, `documents.id`,
`document_versions.approved_by`, …) y `workspaces.tenant_id` es `VARCHAR(100)`.
Con `uuid` cada join contra la tabla del módulo pagaría un cast, y el repunte de
PK de la Parte 3 —que hace `users.id = users_directory.user_id`— tendría que
convertir tipos además de valores. La forma de la tabla es la del estándar; el
tipo sigue la convención del módulo.

SIN FK A workspace.* NI A process_ai.users
-------------------------------------------
El `user_id` cruza el límite como identificador opaco (regla dura de
`01-arquitectura.md`). Tampoco lleva FK a `process_ai.users`: el directorio tiene
gente que nunca se logueó y que por lo tanto no existe ahí, y nunca borra filas.
Son dos tablas con dueños distintos y un escritor único cada una — `users` la
escribe `sync_workspace_access` desde `session/context`; `users_directory` la
escribe el barrido de `/directory`. Fusionarlas es imposible además por la PK:
`(tenant_id, user_id)` contra un id global con email único.

Idempotente.

Revision ID: 0021_users_directory
Revises: 0020_drop_auth_muerta
Create Date: 2026-07-30
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0021_users_directory"
down_revision = "0020_drop_auth_muerta"
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
            f"""
            CREATE TABLE IF NOT EXISTS "{SCHEMA}".users_directory (
                tenant_id    VARCHAR(100) NOT NULL,
                user_id      VARCHAR(36)  NOT NULL,
                auth_user_id VARCHAR(36),
                email        VARCHAR(200),
                first_name   VARCHAR(200),
                last_name    VARCHAR(200),
                display_name VARCHAR(400),
                status       VARCHAR(20)  NOT NULL DEFAULT 'active',
                synced_at    TIMESTAMP    NOT NULL DEFAULT now(),
                PRIMARY KEY (tenant_id, user_id),
                CONSTRAINT users_directory_status_chk
                    CHECK (status IN ('active', 'revoked'))
            )
            """
        )
    )

    # Camino de resolución de HOY: las columnas del módulo guardan
    # `process_ai.users.id`, que se puentea al directorio por
    # `users.external_id = users_directory.auth_user_id`. Parcial porque
    # `auth_user_id` puede ser NULL (usuario provisionado sin cuenta de Auth) y
    # dos NULL no colisionan, pero un auth id repetido en el mismo tenant sí
    # sería un error de datos.
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS users_directory_tenant_auth_uid_key
                ON "{SCHEMA}".users_directory (tenant_id, auth_user_id)
             WHERE auth_user_id IS NOT NULL
            """
        )
    )

    # El chequeo de TTL es `max(synced_at)` por tenant, una vez por request que
    # resuelve nombres. Es el camino más caliente de la tabla.
    conn.execute(
        text(
            f"""
            CREATE INDEX IF NOT EXISTS ix_users_directory_tenant_synced
                ON "{SCHEMA}".users_directory (tenant_id, synced_at DESC)
            """
        )
    )

    conn.execute(
        text(
            f"""
            COMMENT ON TABLE "{SCHEMA}".users_directory IS
            'Directorio de usuarios del módulo, poblado por escritura al leer desde '
            'GET /api/tenants/{{tid}}/applications/{{key}}/directory de workspace. '
            'NUNCA se borra una fila: el que sale del módulo queda status=revoked '
            'para que el histórico siga resolviendo el nombre. Ver '
            'knowledge/11-directorio-de-usuarios.md §2 y §3.'
            """
        )
    )

    conn.execute(
        text(
            f"""
            COMMENT ON COLUMN "{SCHEMA}".users_directory.auth_user_id IS
            'TRANSITORIA. Supabase Auth UUID. Es el puente por el que el módulo '
            'resuelve HOY: process_ai.users.external_id = users_directory.auth_user_id. '
            'CRITERIO DE SALIDA: se borra en la migración del id canónico (Parte 3), '
            'que hace process_ai.users.id = workspace.users.id = users_directory.user_id '
            'y vuelve innecesario el puente. Junto con la columna se saca su escritura '
            'en process_ai_core/db/directory.py.'
            """
        )
    )

    conn.execute(
        text(
            f"""
            COMMENT ON COLUMN "{SCHEMA}".users_directory.display_name IS
            'Lo calcula WORKSPACE y viaja en el DTO. El módulo NO concatena nombre y '
            'apellido (anti-patrón #6): si cada módulo lo arma, cada uno muestra un '
            'formato distinto. Nunca viene vacío — workspace cae al email.'
            """
        )
    )


def downgrade() -> None:
    op.execute(text(f'DROP TABLE IF EXISTS "{SCHEMA}".users_directory'))
