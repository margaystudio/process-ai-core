"""base_access_fail_closed

El `server_default` de `workspace_memberships.base_access` era `'member'`
(nivel edición) y la lógica de resolución es fail-closed (`external` ante
cualquier duda): dos criterios opuestos para el mismo campo.

Hoy no es explotable porque el único escritor —`sync_membership_from_context`—
siempre lo setea explícito. Es una bomba de tiempo igual: un INSERT crudo, un
backfill o un segundo escritor que omita la columna otorgaría permiso de
edición en silencio, y el `server_default` aplica incluso a los INSERT que no
pasan por SQLAlchemy.

Solo cambia el DEFAULT. Las filas existentes NO se tocan: su `base_access` lo
escribió el sync con el rol real del tenant.

Revision ID: 0026_base_access_fail_closed
Revises: 0025_drop_roles_legacy
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0026_base_access_fail_closed"
down_revision = "0025_drop_roles_legacy"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def upgrade() -> None:
    op.get_bind().execute(
        text(
            f'ALTER TABLE "{SCHEMA}".workspace_memberships '
            "ALTER COLUMN base_access SET DEFAULT 'external'"
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        text(
            f'ALTER TABLE "{SCHEMA}".workspace_memberships '
            "ALTER COLUMN base_access SET DEFAULT 'member'"
        )
    )
