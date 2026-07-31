"""id_canonico

Repunte de `process_ai.users.id` al id canónico de la plataforma
(`workspace.users.id`). §4 de `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`.

ESTO NO ES LO MISMO QUE EN OMS Y DASHBOARDS, Y CONVIENE DECIRLO FUERTE
----------------------------------------------------------------------
Allá las columnas ya guardaban un uuid de Auth y la migración cambia el **valor
de una columna**: un `UPDATE` con join y listo. Acá se cambia la **PRIMARY KEY de
`users`** y hay que arrastrar los 12 sitios que la referencian. `users.id` es un
uuid4 propio del módulo que no coincide con nada de la plataforma.

EL MAPEO, Y POR QUÉ NO ES UN JOIN A workspace.users
----------------------------------------------------
    users.id → users.external_id → users_directory.auth_user_id → users_directory.user_id
    (respaldo, si el puente quedó NULL: users.email → users_directory.email)

El puente pasa por `users_directory`, tabla NUESTRA, poblada por la API de
Workspace (migración 0021). Ni un `JOIN workspace.*`: la regla dura de
`01-arquitectura.md` vale también para una migración de datos, y bajo el
enforcement previsto —un rol de base por módulo sin `GRANT` sobre `workspace`—
un join cross-schema fallaría acá adentro, con las FKs ya dropeadas.

PRECONDICIÓN: el directorio tiene que estar POBLADO. Como se llena por escritura
al leer, alcanza con que un miembro del módulo abra una pantalla que resuelva
nombres. Sin eso no hay mapa y la migración se planta.

LOS 12 SITIOS, Y LOS 3 QUE UN BARRIDO POR CATÁLOGO NO VE
---------------------------------------------------------
El inventario vive en `process_ai_core/db/id_remap.py` y lo comparten esta
migración y `tools/censo_id_canonico.py`. Nueve tienen FK a `users(id)`. Los
otros tres no, y son los peligrosos:

  - `tyto_query_log.user_id` y `tyto_session.user_id` — sin FK a propósito
    (auditoría desacoplada, migración 0018). Invisibles para `information_schema`.
  - `validations.assigned_approver_ids` — array JSON serializado en `Text`. Para
    Postgres es una columna de texto cualquiera. Saltearla deja punteros muertos
    adentro de un blob, sin FK que los delate.

Hay una guarda contra deriva: si aparece una FK a `users(id)` que no está en el
inventario, la migración aborta en vez de dejarla atrás.

LO QUE NO SE TOCA
-----------------
Los `acta_*_by_name` / `acta_*_by_role` congelados (migración 0017) son TEXTO, no
ids: dicen qué decía el acta ESE día. Tocarlos sería reescribir el histórico.
`users.external_id` tampoco se toca: sigue siendo la llave con la que
`get_or_create_local_user_from_workspace` resuelve el `sub` del JWT.

REVERSIBLE
----------
`users_id_remap` guarda `(id_viejo, id_nuevo, email)` y no se borra: es el rastro
de auditoría y lo que hace posible el `downgrade`.

USUARIOS SIN MAPEO
------------------
`/directory` solo devuelve MIEMBROS ACTIVOS del módulo, así que quien fue
revocado antes del primer barrido no tiene id canónico que traer. Por defecto la
migración **aborta** y dice quiénes son. Con
`PROCESS_AI_REMAP_PERMITIR_SIN_MAPEO=1` sigue y los deja con su id local: su
nombre se sigue resolviendo por la proyección local (`users.name`), pero no se
refresca nunca. Queda registrado en `users_id_remap` con `id_viejo = id_nuevo`,
así el censo los sigue reportando en vez de darlos por migrados.

Revision ID: 0022_id_canonico
Revises: 0021_users_directory
Create Date: 2026-07-30
"""

from __future__ import annotations

import json
import os

from alembic import op
from sqlalchemy import text

revision = "0022_id_canonico"
down_revision = "0021_users_directory"
branch_labels = None
depends_on = None

try:
    from process_ai_core.db.database import DATABASE_SCHEMA as SCHEMA
except Exception:  # pragma: no cover
    SCHEMA = "process_ai"
if not SCHEMA:
    SCHEMA = "process_ai"


def _q(tabla: str) -> str:
    return f'"{SCHEMA}".{tabla}'


def _permitir_sin_mapeo() -> bool:
    return os.getenv("PROCESS_AI_REMAP_PERMITIR_SIN_MAPEO", "").strip().lower() in {
        "1", "true", "yes",
    }


# ── El mapa local → canónico ─────────────────────────────────────────────────


def _MAPA_SQL(schema: str) -> str:
    """`users.id → users_directory.user_id`, por dos puentes, en ese orden.

    Devuelve `(id_local, email, id_canonico, puentes_ambiguos, referencias)`.
    Espera que el llamador defina una CTE `refs`.

    POR QUÉ SON DOS PUENTES Y NO UNO
    --------------------------------
    El diseñado es `users.external_id = users_directory.auth_user_id`: el auth id
    no cambia nunca y es el puente correcto.

    Pero hay una trampa de ordenamiento que se cobró un intento en prod: **el
    código que ESCRIBE `auth_user_id` desaparece en el mismo release que la
    migración que lo LEE.** `_guardar_directorio` dejó de guardarlo porque el
    modelo ya no tiene la columna —correcto DESPUÉS de esta migración, no
    antes—, así que el primer barrido del directorio la dejó en NULL y el mapa
    quedó vacío con el directorio lleno. Es un modo de falla silencioso: la
    tabla se ve bien y el mapeo no existe.

    El respaldo es el email, que las dos tablas tienen sin depender del orden de
    despliegue. Es peor puente —el email se puede cambiar en el Hub, y
    `users.email` local no se refresca— por eso va segundo y nunca primero.

    Si los dos puentes están vacíos para alguien, no se lo mapea: se lo informa.
    """
    q = lambda t: f'"{schema}".{t}'  # noqa: E731
    return f"""
        , dir AS (
            SELECT auth_user_id, lower(email) AS email_lc, user_id
              FROM {q('users_directory')}
        ),
        por_auth AS (
            SELECT auth_user_id AS k, min(user_id) AS user_id,
                   count(DISTINCT user_id) AS n
              FROM dir WHERE auth_user_id IS NOT NULL GROUP BY auth_user_id
        ),
        por_email AS (
            SELECT email_lc AS k, min(user_id) AS user_id,
                   count(DISTINCT user_id) AS n
              FROM dir WHERE email_lc IS NOT NULL GROUP BY email_lc
        )
        SELECT u.id,
               u.email,
               coalesce(a.user_id, e.user_id)      AS id_canonico,
               coalesce(a.n, e.n, 0)               AS ambiguos,
               (SELECT count(*) FROM refs r WHERE r.uid = u.id) AS referencias
          FROM {q('users')} u
          LEFT JOIN por_auth  a ON a.k = u.external_id
          LEFT JOIN por_email e ON e.k = lower(u.email)
         ORDER BY 5 DESC, u.email
    """


# ── Conteo por sitio: el protocolo de antes y después ────────────────────────


def _conteos(conn, sitios) -> dict[str, int]:
    """Filas con id no nulo por sitio. Tiene que dar IGUAL antes y después.

    Si cambia, la migración perdió o duplicó referencias — que es exactamente el
    modo de falla que un repunte de PK puede tener sin que nada más se queje.
    """
    out: dict[str, int] = {}
    for tabla, columna in sitios:
        out[f"{tabla}.{columna}"] = conn.execute(
            text(f"SELECT count({columna}) FROM {_q(tabla)}")
        ).scalar()
    return out


def upgrade() -> None:
    from process_ai_core.db.id_remap import (
        SITIOS_COLUMNA,
        SITIOS_JSON,
        columnas_existentes,
        sitios_no_inventariados,
    )

    conn = op.get_bind()

    # ── 0. Guardas ──────────────────────────────────────────────────────────
    faltantes = sorted(sitios_no_inventariados(conn, SCHEMA))
    if faltantes:
        raise RuntimeError(
            "Hay columnas con FK a users(id) fuera del inventario: "
            + ", ".join(f"{t}.{c}" for t, c in faltantes)
            + ". Agregalas a process_ai_core/db/id_remap.SITIOS_COLUMNA antes de "
            "migrar: si no, quedan apuntando a ids que ya no existen."
        )

    if not conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{SCHEMA}.users_directory"}
    ).scalar():
        raise RuntimeError(
            "No existe users_directory: sin él no hay mapeo posible sin leer "
            "workspace.* por SQL, que es justo lo que no se hace. Aplicá la 0021 "
            "y dejá que un miembro del módulo abra una pantalla que resuelva "
            "nombres (el directorio se llena por escritura al leer)."
        )

    presentes = columnas_existentes(conn, SCHEMA)
    sitios_col = [(t, c) for t, c, _ in SITIOS_COLUMNA if (t, c) in presentes]
    sitios_json = [(t, c) for t, c, _ in SITIOS_JSON if (t, c) in presentes]

    # Se cuenta cuántas referencias tiene cada usuario, con el mismo criterio que
    # `tools/censo_id_canonico.py`. Si los dos no coincidieran, el censo diría
    # "se puede migrar" y la migración se plantaría igual — o peor, al revés.
    union_refs = " UNION ALL ".join(
        f"SELECT {c} AS uid FROM {_q(t)} WHERE {c} IS NOT NULL" for t, c in sitios_col
    ) or "SELECT NULL::varchar AS uid WHERE FALSE"

    mapa = conn.execute(text(f"WITH refs AS ({union_refs}) {_MAPA_SQL(SCHEMA)}")).fetchall()

    # Ambigüedad: el mismo puente apuntando a dos ids canónicos distintos. No se
    # promedia ni se elige uno — es un error de datos y hay que verlo.
    ambiguos = [(email, n) for _uid, email, _canon, n, _refs in mapa if n and n > 1]
    if ambiguos:
        raise RuntimeError(
            "Hay usuarios cuyo puente apunta a más de un id canónico en "
            "users_directory: " + ", ".join(f"{e} ({n})" for e, n in ambiguos)
        )

    # Solo bloquea quien NO tiene mapeo **y sí tiene referencias**. Un usuario sin
    # una sola referencia no le importa a nadie: dejarlo con su id local no rompe
    # nada, y plantarse por él convertiría la guarda en ruido que se termina
    # salteando con el override sin leerlo — que es justo lo que la haría inútil.
    sin_mapeo = [(uid, email) for uid, email, canon, _n, refs in mapa if not canon and refs]
    if sin_mapeo and not _permitir_sin_mapeo():
        detalle = ", ".join(f"{email} ({uid})" for uid, email in sin_mapeo)
        raise RuntimeError(
            f"{len(sin_mapeo)} usuario(s) CON referencias y sin id canónico: {detalle}. "
            "/directory solo devuelve miembros ACTIVOS del módulo, así que quien "
            "fue revocado antes del primer barrido no aparece. Corré "
            "tools/censo_id_canonico.py para el detalle. Opciones: reactivarles el "
            "acceso en el Hub y volver a barrer, o correr con "
            "PROCESS_AI_REMAP_PERMITIR_SIN_MAPEO=1 para dejarlos con su id local."
        )

    # `id_nuevo = id_viejo` para los que se quedan sin mapear: quedan registrados
    # y el censo los sigue viendo como pendientes en vez de darlos por migrados.
    remap = {uid: (canon or uid) for uid, _email, canon, _n, _refs in mapa}
    emails = {uid: email for uid, email, _c, _n, _r in mapa}

    viejos, nuevos = set(remap), {v for k, v in remap.items() if v != k}
    choques = viejos & nuevos
    if choques:
        raise RuntimeError(
            "El id canónico de alguien ya está en uso como users.id de otra fila: "
            + ", ".join(sorted(choques))
            + ". Un UPDATE directo violaría la PK."
        )
    if len(set(remap.values())) != len(remap):
        raise RuntimeError("Dos usuarios locales mapean al mismo id canónico.")

    antes = _conteos(conn, sitios_col)

    # ── 1. Rastro de auditoría y reversibilidad ─────────────────────────────
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {_q('users_id_remap')} (
                id_viejo   VARCHAR(36) PRIMARY KEY,
                id_nuevo   VARCHAR(36) NOT NULL,
                email      VARCHAR(200),
                migrado_at TIMESTAMP   NOT NULL DEFAULT now()
            )
            """
        )
    )
    for viejo, nuevo in remap.items():
        conn.execute(
            text(
                f"""
                INSERT INTO {_q('users_id_remap')} (id_viejo, id_nuevo, email)
                VALUES (:v, :n, :e)
                ON CONFLICT (id_viejo) DO UPDATE
                   SET id_nuevo = EXCLUDED.id_nuevo, email = EXCLUDED.email
                """
            ),
            {"v": viejo, "n": nuevo, "e": emails.get(viejo)},
        )

    # ── 2. Capturar y soltar las FKs ────────────────────────────────────────
    # Se descubren del catálogo y no por nombre: los ambientes no son iguales
    # (prod estuvo mucho tiempo en 0012 y con CERO FKs declaradas), así que una
    # lista fija de nombres funcionaría en uno y explotaría en el otro.
    fks = conn.execute(
        text(
            """
            SELECT con.conname, src.relname, pg_get_constraintdef(con.oid)
              FROM pg_constraint con
              JOIN pg_class src ON src.oid = con.conrelid
              JOIN pg_namespace ns ON ns.oid = src.relnamespace
             WHERE con.contype = 'f' AND ns.nspname = :schema
               AND pg_get_constraintdef(con.oid) ILIKE '%users(id)%'
            """
        ),
        {"schema": SCHEMA},
    ).fetchall()

    for conname, tabla, _definicion in fks:
        conn.execute(text(f'ALTER TABLE {_q(tabla)} DROP CONSTRAINT "{conname}"'))

    # ── 3. Repunte ──────────────────────────────────────────────────────────
    for viejo, nuevo in remap.items():
        if viejo == nuevo:
            continue
        conn.execute(
            text(f"UPDATE {_q('users')} SET id = :n WHERE id = :v"),
            {"n": nuevo, "v": viejo},
        )
        for tabla, columna in sitios_col:
            conn.execute(
                text(f"UPDATE {_q(tabla)} SET {columna} = :n WHERE {columna} = :v"),
                {"n": nuevo, "v": viejo},
            )

    # ── 4. Los arrays JSON, uno por uno ─────────────────────────────────────
    # No hay SQL que remapee esto sin volverse ilegible, y son pocas filas.
    for tabla, columna in sitios_json:
        for fid, crudo in conn.execute(
            text(f"SELECT id, {columna} FROM {_q(tabla)}")
        ).fetchall():
            try:
                ids = json.loads(crudo or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(ids, list) or not ids:
                continue
            nuevos_ids = [remap.get(i, i) for i in ids]
            if nuevos_ids != ids:
                conn.execute(
                    text(f"UPDATE {_q(tabla)} SET {columna} = :j WHERE id = :i"),
                    {"j": json.dumps(nuevos_ids), "i": fid},
                )

    # ── 5. Reponer las FKs tal cual estaban ─────────────────────────────────
    for conname, tabla, definicion in fks:
        conn.execute(
            text(f'ALTER TABLE {_q(tabla)} ADD CONSTRAINT "{conname}" {definicion}')
        )

    # ── 6. El puente ya no hace falta ───────────────────────────────────────
    # Criterio de salida de la columna, escrito en la 0021: desde ahora
    # users_directory.user_id == users.id y el join es directo.
    conn.execute(
        text(f'ALTER TABLE {_q("users_directory")} DROP COLUMN IF EXISTS auth_user_id')
    )

    # ── 7. Conteo posterior ─────────────────────────────────────────────────
    despues = _conteos(conn, sitios_col)
    if antes != despues:
        difs = {k: (antes[k], despues[k]) for k in antes if antes[k] != despues[k]}
        raise RuntimeError(
            f"El conteo por sitio cambió durante la migración: {difs}. "
            "Se perdieron o duplicaron referencias; la transacción se revierte."
        )

    huerfanas = {}
    for tabla, columna in sitios_col:
        n = conn.execute(
            text(
                f"""
                SELECT count(*) FROM {_q(tabla)}
                 WHERE {columna} IS NOT NULL
                   AND {columna} NOT IN (SELECT id FROM {_q('users')})
                """
            )
        ).scalar()
        if n:
            huerfanas[f"{tabla}.{columna}"] = n
    if huerfanas:
        raise RuntimeError(f"Quedaron referencias huérfanas: {huerfanas}")


def downgrade() -> None:
    """Vuelve a los ids locales usando `users_id_remap`, y repone el puente."""
    from process_ai_core.db.id_remap import (
        SITIOS_COLUMNA,
        SITIOS_JSON,
        columnas_existentes,
    )

    conn = op.get_bind()

    if not conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{SCHEMA}.users_id_remap"}
    ).scalar():
        raise RuntimeError(
            "No existe users_id_remap: sin esa tabla no se puede reconstruir el "
            "mapa viejo, porque los ids locales originales no están en ningún "
            "otro lado."
        )

    presentes = columnas_existentes(conn, SCHEMA)
    sitios_col = [(t, c) for t, c, _ in SITIOS_COLUMNA if (t, c) in presentes]
    sitios_json = [(t, c) for t, c, _ in SITIOS_JSON if (t, c) in presentes]

    inverso = {
        n: v
        for v, n in conn.execute(
            text(f"SELECT id_viejo, id_nuevo FROM {_q('users_id_remap')}")
        ).fetchall()
        if v != n
    }

    fks = conn.execute(
        text(
            """
            SELECT con.conname, src.relname, pg_get_constraintdef(con.oid)
              FROM pg_constraint con
              JOIN pg_class src ON src.oid = con.conrelid
              JOIN pg_namespace ns ON ns.oid = src.relnamespace
             WHERE con.contype = 'f' AND ns.nspname = :schema
               AND pg_get_constraintdef(con.oid) ILIKE '%users(id)%'
            """
        ),
        {"schema": SCHEMA},
    ).fetchall()
    for conname, tabla, _d in fks:
        conn.execute(text(f'ALTER TABLE {_q(tabla)} DROP CONSTRAINT "{conname}"'))

    for nuevo, viejo in inverso.items():
        conn.execute(
            text(f"UPDATE {_q('users')} SET id = :v WHERE id = :n"),
            {"v": viejo, "n": nuevo},
        )
        for tabla, columna in sitios_col:
            conn.execute(
                text(f"UPDATE {_q(tabla)} SET {columna} = :v WHERE {columna} = :n"),
                {"v": viejo, "n": nuevo},
            )

    for tabla, columna in sitios_json:
        for fid, crudo in conn.execute(
            text(f"SELECT id, {columna} FROM {_q(tabla)}")
        ).fetchall():
            try:
                ids = json.loads(crudo or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(ids, list) or not ids:
                continue
            viejos_ids = [inverso.get(i, i) for i in ids]
            if viejos_ids != ids:
                conn.execute(
                    text(f"UPDATE {_q(tabla)} SET {columna} = :j WHERE id = :i"),
                    {"j": json.dumps(viejos_ids), "i": fid},
                )

    for conname, tabla, definicion in fks:
        conn.execute(
            text(f'ALTER TABLE {_q(tabla)} ADD CONSTRAINT "{conname}" {definicion}')
        )

    # Repone el puente: se reconstruye desde users.external_id, que nunca se tocó.
    conn.execute(
        text(
            f'ALTER TABLE {_q("users_directory")} ADD COLUMN IF NOT EXISTS auth_user_id VARCHAR(36)'
        )
    )
    conn.execute(
        text(
            f"""
            UPDATE {_q('users_directory')} d
               SET auth_user_id = u.external_id
              FROM {_q('users_id_remap')} m
              JOIN {_q('users')} u ON u.id = m.id_viejo
             WHERE d.user_id = m.id_nuevo
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS users_directory_tenant_auth_uid_key
                ON {_q('users_directory')} (tenant_id, auth_user_id)
             WHERE auth_user_id IS NOT NULL
            """
        )
    )
