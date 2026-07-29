"""document_code — codificación documental (ADR-019)

Agrega el código estable de cada documento: `PR-0042`, `PO-0007`, `IT-0113`.

Qué crea
--------
- `documents.code` VARCHAR(32) NULL + UNIQUE (workspace_id, code) parcial.
  Nullable porque el backfill de abajo puede no cubrir filas con datos raros, y
  porque un documento sin código es preferible a una migración que falla.
- `document_type.code_prefix` VARCHAR(8) NULL — prefijo por tipo documental.
- `document_code_counters` — secuencial por (workspace, prefijo).

Por qué una tabla de contadores y no `MAX(code)`
------------------------------------------------
Un contador monótono nunca reutiliza un número aunque se borre el documento que
lo tenía. Con `MAX(...)`, borrar el último documento haría que el siguiente
reciclara su código, y dos documentos distintos habrían sido "PR-0042" en
momentos distintos. Además `MAX` obliga a un lock explícito para ser seguro ante
concurrencia; el contador se incrementa con un único INSERT ... ON CONFLICT
DO UPDATE ... RETURNING, que ya es atómico.

Backfill
--------
Los documentos existentes reciben código por orden de creación dentro de cada
(workspace, prefijo), y el contador queda en el último valor entregado. El
prefijo sale de `document_type.code_prefix` si el tipo ya está sembrado; si no,
de un mapa estático de los 14 tipos por defecto; si tampoco, 'DO'.

Reversible: el downgrade borra la tabla, el índice y las dos columnas.

Revision ID: 0014_document_code
Revises: 0013_perf_indexes
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "0014_document_code"
down_revision = "0013_perf_indexes"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


# Mapa estático de respaldo, por si un workspace todavía no tiene sembrados sus
# tipos documentales cuando corre el backfill. Debe coincidir con
# process_ai_core/domains/document_types/defaults.py.
_PREFIJOS_POR_DEFECTO = {
    "procedimiento": "PR", "instructivo": "IT", "manual_interno": "MI",
    "manual_externo": "ME", "manual": "MA", "politica": "PO", "normativa": "NO",
    "formulario": "FO", "contrato": "CO", "nda": "ND", "checklist": "CL",
    "tramite": "TR", "faq_validada": "FQ", "presupuesto": "PU",
}


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Columnas ──────────────────────────────────────────────────────────
    conn.execute(text(f"ALTER TABLE {SCHEMA}.documents ADD COLUMN IF NOT EXISTS code VARCHAR(32)"))
    conn.execute(
        text(f"ALTER TABLE {SCHEMA}.document_type ADD COLUMN IF NOT EXISTS code_prefix VARCHAR(8)")
    )

    # ── 2. Tabla de contadores ───────────────────────────────────────────────
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.document_code_counters (
                workspace_id VARCHAR(36) NOT NULL
                    REFERENCES {SCHEMA}.workspaces(id) ON DELETE CASCADE,
                prefix       VARCHAR(8)  NOT NULL,
                next_value   INTEGER     NOT NULL DEFAULT 0,
                PRIMARY KEY (workspace_id, prefix)
            )
            """
        )
    )

    # ── 3. Prefijos de los tipos ya sembrados ────────────────────────────────
    for key, prefijo in _PREFIJOS_POR_DEFECTO.items():
        conn.execute(
            text(
                f"UPDATE {SCHEMA}.document_type SET code_prefix = :p "
                f"WHERE key = :k AND (code_prefix IS NULL OR code_prefix = '')"
            ),
            {"p": prefijo, "k": key},
        )

    # ── 4. Backfill de códigos ───────────────────────────────────────────────
    # Se resuelve el prefijo de cada documento y se numera por orden de creación
    # dentro de (workspace, prefijo). `created_at, id` hace el orden determinista
    # aunque dos documentos compartan timestamp.
    filas = conn.execute(
        text(
            f"""
            SELECT d.id, d.workspace_id, COALESCE(dt.code_prefix, '') AS prefijo_tipo,
                   COALESCE(d.document_type, '') AS tipo
            FROM {SCHEMA}.documents d
            LEFT JOIN {SCHEMA}.document_type dt
                   ON dt.workspace_id = d.workspace_id AND dt.key = d.document_type
            WHERE d.code IS NULL
            ORDER BY d.workspace_id, d.created_at, d.id
            """
        )
    ).fetchall()

    contadores: dict[tuple[str, str], int] = {}
    for doc_id, workspace_id, prefijo_tipo, tipo in filas:
        prefijo = (prefijo_tipo or _PREFIJOS_POR_DEFECTO.get(tipo, "DO")).upper()
        clave = (workspace_id, prefijo)
        contadores[clave] = contadores.get(clave, 0) + 1
        conn.execute(
            text(f"UPDATE {SCHEMA}.documents SET code = :c WHERE id = :i"),
            {"c": f"{prefijo}-{contadores[clave]:04d}", "i": doc_id},
        )

    # El contador arranca donde terminó el backfill: el próximo documento sigue
    # la serie en vez de pisar un código existente.
    for (workspace_id, prefijo), ultimo in contadores.items():
        conn.execute(
            text(
                f"""
                INSERT INTO {SCHEMA}.document_code_counters (workspace_id, prefix, next_value)
                VALUES (:ws, :p, :v)
                ON CONFLICT (workspace_id, prefix)
                DO UPDATE SET next_value = GREATEST(document_code_counters.next_value, :v)
                """
            ),
            {"ws": workspace_id, "p": prefijo, "v": ultimo},
        )

    # ── 5. Unicidad ──────────────────────────────────────────────────────────
    # Parcial (WHERE code IS NOT NULL) para no bloquear filas sin código.
    # Si el backfill dejó duplicados —no debería—, se degrada a índice no único
    # y se avisa, en vez de romper la migración.
    duplicados = conn.execute(
        text(
            f"""
            SELECT COUNT(*) FROM (
                SELECT workspace_id, code FROM {SCHEMA}.documents
                WHERE code IS NOT NULL
                GROUP BY workspace_id, code HAVING COUNT(*) > 1
            ) t
            """
        )
    ).scalar()

    if duplicados:
        print(
            f"[0014] AVISO: {duplicados} par(es) (workspace_id, code) duplicados. "
            "Se crea índice NO único; revisar y re-aplicar la unicidad a mano."
        )
        conn.execute(
            text(
                f"CREATE INDEX IF NOT EXISTS ix_documents_workspace_code "
                f"ON {SCHEMA}.documents (workspace_id, code)"
            )
        )
    else:
        conn.execute(
            text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_workspace_code "
                f"ON {SCHEMA}.documents (workspace_id, code) WHERE code IS NOT NULL"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(f"DROP INDEX IF EXISTS {SCHEMA}.uq_documents_workspace_code"))
    conn.execute(text(f"DROP INDEX IF EXISTS {SCHEMA}.ix_documents_workspace_code"))
    conn.execute(text(f"DROP TABLE IF EXISTS {SCHEMA}.document_code_counters"))
    conn.execute(text(f"ALTER TABLE {SCHEMA}.document_type DROP COLUMN IF EXISTS code_prefix"))
    conn.execute(text(f"ALTER TABLE {SCHEMA}.documents DROP COLUMN IF EXISTS code"))
