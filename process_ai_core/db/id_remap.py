"""Inventario de sitios que referencian a `process_ai.users.id`.

Fuente de verdad única del repunte de PK al id canónico (`workspace.users.id`),
§4 de `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`. Lo usan el censo
(`tools/censo_id_canonico.py`) y la migración `0022_id_canonico`: si estuviera
duplicado, uno de los dos se quedaría atrás y el que se quede atrás deja punteros
muertos.

POR QUÉ ESTE MÓDULO ES DISTINTO DE OMS Y DASHBOARDS
---------------------------------------------------
Allá las columnas ya guardaban un uuid de Auth y la migración cambia el **valor**
de una columna. Acá se cambia la **PK de `users`** y hay que arrastrar todo lo que
la referencia. `process_ai.users.id` es un uuid4 propio, generado por el módulo,
que no coincide con nada de la plataforma.

EL MAPEO EXISTE Y ES DETERMINÍSTICO (dos saltos)
------------------------------------------------
    process_ai.users.id
      → users.external_id                        (Supabase Auth UUID, sub del JWT)
      → users_directory.auth_user_id             (misma llave, la trae /directory)
      → users_directory.user_id                  (workspace.users.id — el canónico)

El puente pasa por `users_directory`, que es una tabla **nuestra**, poblada por la
API de Workspace. No hay un solo `JOIN workspace.*`: la regla dura de
`01-arquitectura.md` vale también para una migración de datos, y bajo el
enforcement previsto (un rol de base por módulo sin `GRANT` sobre `workspace`) un
join cross-schema acá fallaría en el peor momento posible.

Corolario que hay que tener presente: **el directorio tiene que estar poblado
antes de migrar**, y `/directory` solo devuelve a los miembros ACTIVOS del módulo.
Quien fue revocado antes del primer barrido no tiene mapeo posible por esta vía.
El censo los lista; la migración se planta y no sigue salvo override explícito.
"""

from __future__ import annotations

#: Columnas que guardan un `process_ai.users.id`. Son 12, no 8: las tres últimas
#: NO tienen foreign key y por lo tanto **un barrido por `information_schema` no
#: las ve**. Saltearlas es dejar punteros muertos sin que nada avise.
#:
#: `(tabla, columna, por_qué_está_acá)`
SITIOS_COLUMNA: list[tuple[str, str, str]] = [
    # ── Con FK declarada a users(id) ────────────────────────────────────────
    ("audit_logs", "user_id", "quién hizo la acción registrada"),
    ("document_relations", "confirmed_by", "quién decidió sobre la relación (confirm Y reject); NULL = el sistema"),
    ("document_versions", "approved_by", "quién aprobó la versión"),
    ("document_versions", "created_by", "quién creó la versión"),
    ("document_versions", "rejected_by", "quién rechazó la versión"),
    ("evidence", "added_by", "quién sumó la evidencia (tabla sin escritores hoy)"),
    ("user_operational_roles", "assigned_by", "quién asignó el rol operativo"),
    ("validations", "validator_user_id", "quién validó"),
    ("workspace_memberships", "user_id", "la membresía local; ancla del RBAC del módulo"),
    # ── SIN FK, a propósito: tablas de auditoría desacopladas ───────────────
    # `tyto_query_log` y `tyto_session` no llevan FK para que el rastro
    # sobreviva a los borrados (ver la migración 0018). Eso las vuelve
    # invisibles para cualquier inventario que se arme desde el catálogo.
    ("tyto_query_log", "user_id", "SIN FK — auditoría desacoplada (migración 0018)"),
    ("tyto_session", "user_id", "SIN FK — el historial de conversaciones es por usuario"),
]

#: Arrays JSON serializados en `Text` con ids adentro. **Ningún barrido por
#: catálogo los ve**: para Postgres es una columna de texto cualquiera. Es el
#: sitio que hay que buscar a mano y el que deja punteros muertos adentro de un
#: blob si se saltea.
SITIOS_JSON: list[tuple[str, str, str]] = [
    ("validations", "assigned_approver_ids", "array JSON de aprobadores sugeridos; sin integridad referencial"),
]

#: Lo que NO se toca, y por qué. Está escrito porque la tentación de "actualizar
#: todo lo que huela a usuario" es exactamente el error que arruinaría el acta.
NO_SE_TOCAN: list[tuple[str, str, str]] = [
    ("document_versions", "acta_elaborated_by_name", "SNAPSHOT §5: dice qué decía el acta ESE día"),
    ("document_versions", "acta_reviewed_by_name", "SNAPSHOT §5"),
    ("document_versions", "acta_approved_by_name", "SNAPSHOT §5"),
    ("document_versions", "acta_elaborated_by_role", "SNAPSHOT §5: el cargo del momento, no el actual"),
    ("document_versions", "acta_reviewed_by_role", "SNAPSHOT §5"),
    ("document_versions", "acta_approved_by_role", "SNAPSHOT §5"),
    ("document_versions", "acta_client_name", "SNAPSHOT §5: el workspace se puede renombrar"),
    ("users", "external_id", "es el Auth UUID, no un users.id; sigue siendo la llave de lookup del JWT"),
    ("users_directory", "user_id", "ya es el id canónico: es el ORIGEN del mapeo"),
]


def _cols_con_fk_a_users(conn, schema: str) -> set[tuple[str, str]]:
    """`(tabla, columna)` de cada FK declarada contra `users(id)`."""
    from sqlalchemy import text

    filas = conn.execute(
        text(
            """
            SELECT src.relname AS tabla, att.attname AS columna
              FROM pg_constraint con
              JOIN pg_class src ON src.oid = con.conrelid
              JOIN pg_namespace ns ON ns.oid = src.relnamespace
              JOIN unnest(con.conkey) AS k(attnum) ON TRUE
              JOIN pg_attribute att
                ON att.attrelid = src.oid AND att.attnum = k.attnum
             WHERE con.contype = 'f'
               AND ns.nspname = :schema
               AND pg_get_constraintdef(con.oid) ILIKE '%users(id)%'
            """
        ),
        {"schema": schema},
    ).fetchall()
    return {(f[0], f[1]) for f in filas}


def sitios_no_inventariados(conn, schema: str) -> set[tuple[str, str]]:
    """FKs a `users(id)` que existen en la base y NO están en `SITIOS_COLUMNA`.

    La guarda contra deriva: si alguien agrega una columna que apunta a usuarios
    y no la anota acá, el censo y la migración lo gritan en vez de dejarla atrás.

    La inversa —una entrada del inventario sin FK— es normal y esperada: tres de
    los doce sitios no tienen FK a propósito.
    """
    inventariados = {(t, c) for t, c, _ in SITIOS_COLUMNA}
    return _cols_con_fk_a_users(conn, schema) - inventariados


def columnas_existentes(conn, schema: str) -> set[tuple[str, str]]:
    """Sitios del inventario que realmente existen en ESTA base.

    Los ambientes no están todos en la misma revisión: prod estuvo mucho tiempo
    en `0012` sin las tablas de Tyto. Se opera sobre lo que hay, no sobre lo que
    debería haber.
    """
    from sqlalchemy import text

    filas = conn.execute(
        text(
            """
            SELECT table_name, column_name
              FROM information_schema.columns
             WHERE table_schema = :schema
            """
        ),
        {"schema": schema},
    ).fetchall()
    presentes = {(f[0], f[1]) for f in filas}
    return {
        (t, c)
        for t, c, _ in (SITIOS_COLUMNA + SITIOS_JSON)
        if (t, c) in presentes
    }
