"""drop_auth_muerta

Elimina los restos del sistema de identidad propio que Process AI arrastraba en
paralelo al de la plataforma.

QUÉ SE VA Y POR QUÉ
-------------------
  - users.password_hash        : **nunca autenticó nada**. No existía ruta de
                                 login ni verificación de contraseña en ningún
                                 lado; la columna se escribía siempre en "".
                                 Su comentario decía "Para autenticación local"
                                 y era falso. Se elimina para que nadie la lea
                                 como que hay auth local disponible.
  - workspace_invitations      : tabla, modelo y helpers completos
                                 (create/get_by_token/accept/list/pending), sin
                                 UNA SOLA ruta de API que los expusiera. El
                                 router ya se había eliminado antes (ver el
                                 comentario en `api/main.py`): esto es el resto
                                 que quedó. Las invitaciones son del Hub
                                 (`workspace.tenant_invitations`).

QUÉ NO SE TOCA
--------------
Process AI **no** es un sistema de identidad paralelo, contra lo que sugiere el
código borrado. El login va al Hub (`ui/lib/hub-login.ts`), los JWT los emite
Supabase y se validan por JWKS, y `sync_workspace_access`
(`api/workspace_client.py`) mantiene la proyección local con escritura al leer
desde `session/context` — que es el patrón correcto del estándar de la
plataforma. Todo eso se queda:

  - `users`, `workspace_memberships`  : la proyección local. Se llena sola.
  - `roles`, `user_operational_roles` : permisos finos del módulo. Workspace
                                        decide el acceso macro; el módulo, los
                                        permisos finos.
  - `users.auth_provider`             : se escribe en el sync vivo (siempre
                                        "supabase"). Nada ramifica sobre él, así
                                        que informativamente es inútil, pero
                                        sacarlo obliga a tocar la firma de
                                        `get_or_create_user` en el camino
                                        caliente. Queda para otra migración.

TRES TIEMPOS, Y ESTE ES EL ÚLTIMO
---------------------------------
  1. `0019_auth_muerta_compat` — `password_hash` gana un default del lado del
     servidor, así el código viejo y el nuevo conviven contra la misma base.
  2. Deploy del código que ya no usa `password_hash` ni `workspace_invitations`.
  3. **Esta migración** — recién ahora se borran, cuando ya no queda código
     apuntando a ellas.

Aplicar esta migración ANTES del paso 2 deja la base sin la columna mientras el
código deployado todavía la manda: `UndefinedColumn` en cada INSERT de usuario.
Por eso el orden importa y no es una formalidad.

Referencia: `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`,
sección "Process AI: qué está muerto y qué no".

Revision ID: 0020_drop_auth_muerta
Revises: 0019_auth_muerta_compat
Create Date: 2026-07-29
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0020_drop_auth_muerta"
down_revision = "0019_auth_muerta_compat"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def upgrade() -> None:
    op.execute(text(f'DROP TABLE IF EXISTS "{SCHEMA}".workspace_invitations'))
    op.execute(text(f'ALTER TABLE "{SCHEMA}".users DROP COLUMN IF EXISTS password_hash'))


def downgrade() -> None:
    """Recrea la estructura, no los datos.

    `password_hash` vuelve como columna vacía porque nunca tuvo contenido real.
    `workspace_invitations` vuelve vacía: si alguien necesita revertir, el dato
    de invitaciones vive en el Hub, que es su dueño.
    """
    op.execute(
        text(
            f'ALTER TABLE "{SCHEMA}".users '
            "ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) DEFAULT ''"
        )
    )
    op.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS "{SCHEMA}".workspace_invitations (
                id                  VARCHAR(36)  PRIMARY KEY,
                workspace_id        VARCHAR(36)  NOT NULL REFERENCES "{SCHEMA}".workspaces(id),
                invited_by_user_id  VARCHAR(36)  NOT NULL REFERENCES "{SCHEMA}".users(id),
                email               VARCHAR(200) NOT NULL,
                role_id             VARCHAR(36)  NOT NULL REFERENCES "{SCHEMA}".roles(id),
                token               VARCHAR(64)  NOT NULL UNIQUE,
                status              VARCHAR(20)  NOT NULL,
                expires_at          TIMESTAMP    NOT NULL,
                accepted_at         TIMESTAMP,
                accepted_by_user_id VARCHAR(36)  REFERENCES "{SCHEMA}".users(id),
                message             TEXT,
                created_at          TIMESTAMP    NOT NULL DEFAULT now()
            )
            """
        )
    )
    for col in ("workspace_id", "email", "token", "status"):
        op.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS idx_workspace_invitations_{col} "
                f'ON "{SCHEMA}".workspace_invitations({col})'
            )
        )
