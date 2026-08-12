"""niveles_de_acceso

Fase 3 del rediseño de permisos: el rol de sistema (owner/admin/approver/
creator/viewer) desaparece como concepto y sus dos preguntas se reparten:

  - "¿es admin del workspace?" → `workspace_memberships.base_access`
    ('admin' | 'member' | 'external'), derivado del rol macro del tenant en
    margay-workspace y escrito por el sync en cada request.
  - "¿qué puede hacer y dónde?" → `operational_roles.access_level`
    ('lectura' | 'edicion' | 'aprobacion') × sus carpetas (folder_permissions).

POR QUÉ
-------
El rol de sistema era un vocabulario intermedio que nadie administraba: se
derivaba con un mapeo fijo del rol de tenant, la mitad de sus valores era
inalcanzable (owner/approver no se podían asignar por ningún flujo), y su
matriz vivía duplicada en el seed y en el frontend. Ver el ADR de plataforma
"Roles por módulo" (margay-dev-agent/knowledge/09-roles-por-modulo.md): el
módulo mapea el rol macro a roles finos DE DOMINIO — que acá son los roles
operativos que el cliente ya nombra ("Pistero", "Gerencia").

BACKFILL
--------
- base_access desde el rol de sistema actual (por role_id, con fallback al
  string legacy): owner/admin/superadmin → 'admin'; approver/creator →
  'member'; viewer → 'external'. La aproximación viewer→external es segura:
  el sync reescribe base_access desde el rol de tenant REAL en el siguiente
  request del usuario.
- access_level: todos los roles operativos existentes quedan en 'edicion'
  (espejo de lo que hoy puede un tenant_member/creator). El cap de solo
  lectura de los externos NO depende del rol operativo: lo impone
  base_access='external' en la evaluación.

Las tablas roles/role_permissions y las columnas role_id/role de memberships
NO se borran: dejan de leerse en runtime (salvo el fallback legacy del
superadmin por membership) y se eliminan en una limpieza posterior, cuando
corra tools/cleanup_workspace_sistema.py. role_id pierde el NOT NULL porque
el sync deja de escribirlo.

Revision ID: 0024_niveles_de_acceso
Revises: 0023_relacion_decided_by
Create Date: 2026-08-12
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0024_niveles_de_acceso"
down_revision = "0023_relacion_decided_by"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


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

    if not _columna_existe(conn, "workspace_memberships", "base_access"):
        conn.execute(
            text(
                f'ALTER TABLE "{SCHEMA}".workspace_memberships '
                "ADD COLUMN base_access VARCHAR(20) NOT NULL DEFAULT 'member'"
            )
        )
        # Backfill desde el rol de sistema vigente (role_id, fallback string).
        conn.execute(
            text(
                f"""
                UPDATE "{SCHEMA}".workspace_memberships m
                   SET base_access = CASE
                         WHEN COALESCE(r.name, m.role) IN ('owner', 'admin', 'superadmin')
                           THEN 'admin'
                         WHEN COALESCE(r.name, m.role) = 'viewer'
                           THEN 'external'
                         ELSE 'member'
                       END
                  FROM "{SCHEMA}".workspace_memberships m2
                  LEFT JOIN "{SCHEMA}".roles r ON r.id = m2.role_id
                 WHERE m2.id = m.id
                """
            )
        )

    if not _columna_existe(conn, "operational_roles", "access_level"):
        conn.execute(
            text(
                f'ALTER TABLE "{SCHEMA}".operational_roles '
                "ADD COLUMN access_level VARCHAR(20) NOT NULL DEFAULT 'edicion'"
            )
        )

    # role_id deja de escribirse: sin esto, el primer sync de un usuario nuevo
    # fallaría por el NOT NULL de una columna deprecada.
    conn.execute(
        text(
            f'ALTER TABLE "{SCHEMA}".workspace_memberships '
            "ALTER COLUMN role_id DROP NOT NULL"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if _columna_existe(conn, "workspace_memberships", "base_access"):
        conn.execute(
            text(f'ALTER TABLE "{SCHEMA}".workspace_memberships DROP COLUMN base_access')
        )
    if _columna_existe(conn, "operational_roles", "access_level"):
        conn.execute(
            text(f'ALTER TABLE "{SCHEMA}".operational_roles DROP COLUMN access_level')
        )
    # El NOT NULL de role_id no se restaura: habría filas nuevas con NULL.
