"""drop_roles_legacy

Cierre de la fase 3 del rediseño de permisos: se eliminan los restos del RBAC
de roles de sistema, que desde la migración 0024 ya no se leía en runtime.

Qué borra (en este orden, por las FKs):

  1. El workspace legacy 'sistema' y sus memberships — era el ancla de la
     membership de superadmin en la arquitectura anterior al claim
     platform_roles. Absorbe lo que hacía tools/cleanup_workspace_sistema.py,
     que se elimina junto con esta migración.
  2. Las columnas workspace_memberships.role_id y .role (deprecadas).
  3. Las tablas role_permissions, roles y permissions.

Con esto, el fallback legacy del superadmin por membership desaparece también
del código (_is_superadmin queda solo por claim). Ningún superadmin pierde
acceso: el sync escribe base_access='admin' en cada workspace que visita, y
ese es el bypass que evalúan los endpoints que no propagan el claim.

Es IDEMPOTENTE: cada paso verifica existencia antes de actuar.

Revision ID: 0025_drop_roles_legacy
Revises: 0024_niveles_de_acceso
Create Date: 2026-08-12
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0025_drop_roles_legacy"
down_revision = "0024_niveles_de_acceso"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def _tabla_existe(conn, tabla: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT count(*) FROM information_schema.tables
                 WHERE table_schema = :s AND table_name = :t
                """
            ),
            {"s": SCHEMA, "t": tabla},
        ).scalar()
    )


def _columna_existe(conn, tabla: str, columna: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT count(*) FROM information_schema.columns
                 WHERE table_schema = :s AND table_name = :t AND column_name = :c
                """
            ),
            {"s": SCHEMA, "t": tabla, "c": columna},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Workspace legacy 'sistema' + sus memberships (y asignaciones colgadas).
    sistema_id = conn.execute(
        text(
            f"""
            SELECT id FROM "{SCHEMA}".workspaces
             WHERE slug = 'sistema' AND workspace_type = 'system'
            """
        )
    ).scalar()
    if sistema_id:
        conn.execute(
            text(
                f"""
                DELETE FROM "{SCHEMA}".user_operational_roles
                 WHERE workspace_membership_id IN (
                     SELECT id FROM "{SCHEMA}".workspace_memberships
                      WHERE workspace_id = :ws
                 )
                """
            ),
            {"ws": sistema_id},
        )
        conn.execute(
            text(
                f'DELETE FROM "{SCHEMA}".workspace_memberships WHERE workspace_id = :ws'
            ),
            {"ws": sistema_id},
        )
        conn.execute(
            text(f'DELETE FROM "{SCHEMA}".workspaces WHERE id = :ws'),
            {"ws": sistema_id},
        )

    # 2) Columnas deprecadas de memberships.
    for columna in ("role_id", "role"):
        if _columna_existe(conn, "workspace_memberships", columna):
            conn.execute(
                text(
                    f'ALTER TABLE "{SCHEMA}".workspace_memberships '
                    f"DROP COLUMN {columna}"
                )
            )

    # 3) Tablas del RBAC legacy (role_permissions primero por las FKs).
    for tabla in ("role_permissions", "roles", "permissions"):
        if _tabla_existe(conn, tabla):
            conn.execute(text(f'DROP TABLE "{SCHEMA}".{tabla}'))


def downgrade() -> None:
    """Recrea el ESQUEMA legacy (idéntico al baseline), sin datos.

    Los datos eran el seed de roles/permisos y las memberships del workspace
    'sistema': ninguno se puede reconstruir ni hace falta (el código que los
    leía se eliminó junto con esta migración). El downgrade existe para que
    `alembic downgrade base` recorra la cadena completa.
    """
    conn = op.get_bind()

    if not _tabla_existe(conn, "roles"):
        conn.execute(
            text(
                f"""
                CREATE TABLE "{SCHEMA}".roles (
                    id VARCHAR(36) NOT NULL,
                    name VARCHAR(50) NOT NULL,
                    description VARCHAR(500) NOT NULL,
                    workspace_type VARCHAR(20),
                    is_system BOOLEAN NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(
            text(f'CREATE UNIQUE INDEX ix_{SCHEMA}_roles_name ON "{SCHEMA}".roles (name)')
        )

    if not _tabla_existe(conn, "permissions"):
        conn.execute(
            text(
                f"""
                CREATE TABLE "{SCHEMA}".permissions (
                    id VARCHAR(36) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(500) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(
            text(
                f'CREATE UNIQUE INDEX ix_{SCHEMA}_permissions_name '
                f'ON "{SCHEMA}".permissions (name)'
            )
        )
        conn.execute(
            text(
                f'CREATE INDEX ix_{SCHEMA}_permissions_category '
                f'ON "{SCHEMA}".permissions (category)'
            )
        )

    if not _tabla_existe(conn, "role_permissions"):
        conn.execute(
            text(
                f"""
                CREATE TABLE "{SCHEMA}".role_permissions (
                    role_id VARCHAR(36) NOT NULL,
                    permission_id VARCHAR(36) NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (role_id, permission_id),
                    FOREIGN KEY(role_id) REFERENCES "{SCHEMA}".roles (id),
                    FOREIGN KEY(permission_id) REFERENCES "{SCHEMA}".permissions (id)
                )
                """
            )
        )

    if not _columna_existe(conn, "workspace_memberships", "role_id"):
        conn.execute(
            text(
                f'ALTER TABLE "{SCHEMA}".workspace_memberships '
                f'ADD COLUMN role_id VARCHAR(36) REFERENCES "{SCHEMA}".roles (id)'
            )
        )
    if not _columna_existe(conn, "workspace_memberships", "role"):
        conn.execute(
            text(
                f'ALTER TABLE "{SCHEMA}".workspace_memberships ADD COLUMN role VARCHAR(20)'
            )
        )
