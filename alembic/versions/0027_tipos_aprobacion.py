"""Corrige el comportamiento `aprobacion` (y `es_referencia`) de seis tipos documentales.

Hasta ahora la pantalla de importación mandaba `requires_approval` fijo en `true`,
así que el behavior `aprobacion` de cada tipo no lo leía nadie y podía estar mal
sin que se notara. Al conectarlo, esos valores pasan a decidir de verdad si un
documento entra a revisión — y tal como estaban, cuatro tipos habrían empezado a
publicarse sin que nadie los mirara.

Dos correcciones, con el mismo criterio: **de quién es el documento**.

- Lo EXTERNO no se aprueba, se incorpora. Nadie de la organización puede aprobar
  una ley, y un presupuesto que nos pasa un proveedor tampoco lo firmamos
  nosotros. `normativa` y `presupuesto` pasan a `aprobacion=false` +
  `es_referencia=true`, que es lo que hace que Tyto los cite como 🟡 "referencia"
  en vez de 🟢 "aprobado".
- Lo PROPIO se aprueba. `instructivo`, `formulario`, `checklist` y `tramite`
  tenían `aprobacion=false`: pasan a `true`. No es endurecer nada — hoy TODOS
  requieren aprobación de hecho, porque estaba forzado. Dejarlos en false habría
  sido estrenar un permiso para publicar sin revisión que nunca existió.

POR QUÉ NO ES UN UPDATE A SECAS
-------------------------------
Los tipos son una entidad POR TENANT (copy-on-provision): cambiar el archivo de
defaults solo afecta a los workspaces que se creen de acá en adelante. Los que ya
existen tienen su propia fila, y esa fila el tenant la puede haber editado.

Por eso cada behavior se toca SOLO si todavía tiene el valor viejo del template.
Si alguien ya lo cambió a mano —aunque sea al mismo valor que queremos poner— se
respeta y no se pisa: una decisión explícita de un cliente sobre cómo gobierna
sus documentos no la revierte una migración nuestra.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0027_tipos_aprobacion"
down_revision = "0026_base_access_fail_closed"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


#: key del tipo → {behavior: (valor_viejo_del_template, valor_nuevo)}
#: Solo se reescribe si el valor actual es el viejo.
CAMBIOS: dict[str, dict[str, tuple[bool, bool]]] = {
    "normativa": {"aprobacion": (True, False), "es_referencia": (False, True)},
    "presupuesto": {
        "aprobacion": (True, False),
        "es_referencia": (False, True),
        "tyto": (False, True),
    },
    "instructivo": {"aprobacion": (False, True)},
    "formulario": {"aprobacion": (False, True)},
    "checklist": {"aprobacion": (False, True)},
    "tramite": {"aprobacion": (False, True)},
}


def _aplicar(sentido: str) -> None:
    """`sentido` es 'upgrade' o 'downgrade'; invierte el par (viejo, nuevo)."""
    conn = op.get_bind()
    filas = conn.execute(
        sa.text(
            f'SELECT id, key, behaviors_json FROM "{SCHEMA}".document_type '
            "WHERE origin = 'default' AND key = ANY(:keys)"
        ),
        {"keys": list(CAMBIOS)},
    ).fetchall()

    for fila in filas:
        try:
            behaviors = json.loads(fila.behaviors_json or "{}")
        except (json.JSONDecodeError, TypeError):
            # Un JSON roto no se arregla a ciegas desde una migración.
            continue
        if not isinstance(behaviors, dict):
            continue

        cambio = False
        for behavior, (viejo, nuevo) in CAMBIOS[fila.key].items():
            desde, hasta = (viejo, nuevo) if sentido == "upgrade" else (nuevo, viejo)
            if bool(behaviors.get(behavior, False)) == desde:
                behaviors[behavior] = hasta
                cambio = True

        if cambio:
            conn.execute(
                sa.text(
                    f'UPDATE "{SCHEMA}".document_type '
                    "SET behaviors_json = :b WHERE id = :id"
                ),
                {"b": json.dumps(behaviors), "id": fila.id},
            )


def upgrade() -> None:
    _aplicar("upgrade")


def downgrade() -> None:
    _aplicar("downgrade")
