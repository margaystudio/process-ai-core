"""perf_indexes

Índices de performance para los patrones de consulta calientes de la UI/API:
- workspace_memberships (user_id, workspace_id) UNIQUE — lookup de membresía;
  verificado sin duplicados en prod/test (2026-07-27). La migración re-verifica
  en runtime: si aparecieron duplicados, degrada a índice normal (ix_) y avisa.
- documents (workspace_id, domain, status, created_at DESC) — listados por workspace
- documents (folder_id, status) — contenido de carpeta
- document_versions (document_id, version_status) — versiones por documento
- document_versions (version_status, is_current) — versión vigente / colas de estado
- audit_logs (document_id, created_at DESC) — timeline de auditoría
- validations (document_id, created_at DESC) — historial de validaciones
- folders (workspace_id, sort_order, name) — árbol de carpetas ordenado

Además materializa el "ENFORCE DB" documentado en DocumentVersion (models.py)
que nunca tuvo migración:
- uq_document_one_draft     UNIQUE (document_id) WHERE version_status = 'DRAFT'
- uq_document_one_in_review UNIQUE (document_id) WHERE version_status = 'IN_REVIEW'
Verificado sin violaciones en prod/test (2026-07-27); si en runtime las hay,
se omite el índice y se reporta (no se rompe la migración).

Y elimina ix_knowledge_objects_name_trgm (0005, GIN sobre el varchar crudo):
el planner nunca lo elige porque el operador `%` castea a text; quedó superado
por ix_knowledge_objects_name_trgm_txt (0011, GIN sobre la expresión
normalized_name::text). El docstring de 0011 ya lo marcaba como redundante.

Sin CREATE INDEX CONCURRENTLY: env.py corre las migraciones dentro de una
transacción (context.begin_transaction) y el repo no usa autocommit_block,
así que se crean índices normales (tablas chicas hoy; lock breve).

Revision ID: 0013_perf_indexes
Revises: 0012_tyto_query_log
Create Date: 2026-07-27
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "0013_perf_indexes"
down_revision = "0012_tyto_query_log"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


# (nombre, tabla, expresión de columnas) — índices compuestos no únicos
_INDEXES = [
    (
        "ix_documents_workspace_domain_status_created",
        "documents",
        "(workspace_id, domain, status, created_at DESC)",
    ),
    ("ix_documents_folder_status", "documents", "(folder_id, status)"),
    (
        "ix_document_versions_document_status",
        "document_versions",
        "(document_id, version_status)",
    ),
    (
        "ix_document_versions_status_current",
        "document_versions",
        "(version_status, is_current)",
    ),
    ("ix_audit_logs_document_created", "audit_logs", "(document_id, created_at DESC)"),
    ("ix_validations_document_created", "validations", "(document_id, created_at DESC)"),
    ("ix_folders_workspace_sort_name", "folders", "(workspace_id, sort_order, name)"),
]


def _has_duplicates(conn, table: str, group_by: str, where: str = "") -> bool:
    where_clause = f"WHERE {where} " if where else ""
    row = conn.execute(
        text(
            f'SELECT 1 FROM "{SCHEMA}".{table} {where_clause}'
            f"GROUP BY {group_by} HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    return row is not None


def upgrade() -> None:
    conn = op.get_bind()

    for name, table, cols in _INDEXES:
        conn.execute(
            text(f'CREATE INDEX IF NOT EXISTS {name} ON "{SCHEMA}".{table} {cols}')
        )

    # Membresía user↔workspace: UNIQUE salvo que existan duplicados (degrada).
    if _has_duplicates(conn, "workspace_memberships", "user_id, workspace_id"):
        print(
            "AVISO 0013: duplicados en workspace_memberships(user_id, workspace_id); "
            "se crea índice NO único ix_workspace_memberships_user_workspace."
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_workspace_memberships_user_workspace "
                f'ON "{SCHEMA}".workspace_memberships (user_id, workspace_id)'
            )
        )
    else:
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_workspace_memberships_user_workspace "
                f'ON "{SCHEMA}".workspace_memberships (user_id, workspace_id)'
            )
        )

    # ENFORCE DB de DocumentVersion: 1 solo DRAFT / IN_REVIEW por documento.
    for name, status in (
        ("uq_document_one_draft", "DRAFT"),
        ("uq_document_one_in_review", "IN_REVIEW"),
    ):
        if _has_duplicates(
            conn, "document_versions", "document_id", f"version_status = '{status}'"
        ):
            print(
                f"AVISO 0013: hay documentos con más de una versión {status}; "
                f"se omite el índice único parcial {name}. Sanear datos y re-crear."
            )
            continue
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {name} "
                f'ON "{SCHEMA}".document_versions (document_id) '
                f"WHERE version_status = '{status}'"
            )
        )

    # GIN muerto de 0005 (varchar crudo): superado por ..._trgm_txt de 0011.
    conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA}".ix_knowledge_objects_name_trgm'))


def downgrade() -> None:
    conn = op.get_bind()

    for name in (
        "uq_document_one_in_review",
        "uq_document_one_draft",
        "uq_workspace_memberships_user_workspace",
        "ix_workspace_memberships_user_workspace",
    ):
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA}".{name}'))

    for name, _table, _cols in _INDEXES:
        conn.execute(text(f'DROP INDEX IF EXISTS "{SCHEMA}".{name}'))

    # Restaura el GIN de 0005 sobre el varchar crudo (si pg_trgm está disponible).
    row = conn.execute(
        text(
            "SELECT n.nspname FROM pg_extension e "
            "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'pg_trgm'"
        )
    ).first()
    if row:
        opclass = f'"{row[0]}".gin_trgm_ops' if row[0] else "gin_trgm_ops"
        try:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_objects_name_trgm "
                    f'ON "{SCHEMA}".knowledge_objects USING gin (normalized_name {opclass})'
                )
            )
        except Exception:
            pass
