#!/usr/bin/env python3
"""Censo del repunte de PK al id canónico. NO ESCRIBE NADA.

Es el "conteo previo" del protocolo, y también el posterior: es el **mismo
comando**. Se corre antes de `0022_id_canonico`, se guarda la salida, se corre
después y se comparan. Si los totales por sitio no son idénticos, la migración
perdió o duplicó referencias.

    .venv/bin/python tools/censo_id_canonico.py            # censo completo
    .venv/bin/python tools/censo_id_canonico.py --json     # para diffear

Códigos de salida
-----------------
    0  todo mapeable (o ya migrado): la migración puede correr
    1  hay usuarios CON referencias que no se pueden mapear
    2  hay deriva de inventario, colisión de ids, o huérfanas

Qué mira, en orden:

  1. **Deriva de inventario.** ¿Hay alguna FK a `users(id)` que no esté anotada
     en `process_ai_core/db/id_remap.py`? Si la hay, el inventario mintió y
     cualquier conteo posterior es falso.
  2. **Conteo por sitio.** Filas, ids distintos y huérfanas de los 12 sitios,
     incluidos los tres que no tienen FK y el array JSON — que son justamente los
     que un barrido por catálogo no ve.
  3. **Mapeo.** Para cada usuario local: su id canónico según `users_directory`,
     y cuántas referencias tiene. Sin cross-schema.
  4. **Colisiones.** ¿Algún id canónico ya está en uso como `users.id` de otra
     persona? Sería un choque durante el UPDATE.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from process_ai_core.db.database import DATABASE_SCHEMA, get_db_engine  # noqa: E402
from process_ai_core.db.id_remap import (  # noqa: E402
    NO_SE_TOCAN,
    SITIOS_COLUMNA,
    SITIOS_JSON,
    columnas_existentes,
    sitios_no_inventariados,
)

VERDE, ROJO, AMARILLO, GRIS, FIN = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def _q(schema: str, tabla: str) -> str:
    return f'"{schema}".{tabla}' if schema else tabla


def censar(conn, schema: str) -> dict:
    presentes = columnas_existentes(conn, schema)
    reporte: dict = {"schema": schema, "sitios": [], "usuarios": [], "problemas": []}

    # ── 1. Deriva de inventario ─────────────────────────────────────────────
    faltantes = sorted(sitios_no_inventariados(conn, schema))
    reporte["sitios_no_inventariados"] = [f"{t}.{c}" for t, c in faltantes]
    if faltantes:
        reporte["problemas"].append(
            "Hay FKs a users(id) fuera del inventario: "
            + ", ".join(f"{t}.{c}" for t, c in faltantes)
        )

    # ── 2. Conteo por sitio ─────────────────────────────────────────────────
    for tabla, columna, nota in SITIOS_COLUMNA:
        if (tabla, columna) not in presentes:
            reporte["sitios"].append(
                {"sitio": f"{tabla}.{columna}", "estado": "ausente", "nota": nota}
            )
            continue
        fila = conn.execute(
            text(
                f"""
                SELECT count({columna})                                   AS filas,
                       count(DISTINCT {columna})                          AS ids,
                       count(*) FILTER (
                           WHERE {columna} IS NOT NULL
                             AND {columna} NOT IN (SELECT id FROM {_q(schema, 'users')})
                       )                                                  AS huerfanas
                  FROM {_q(schema, tabla)}
                """
            )
        ).first()
        reporte["sitios"].append(
            {
                "sitio": f"{tabla}.{columna}",
                "estado": "ok",
                "filas": fila[0],
                "ids_distintos": fila[1],
                "huerfanas": fila[2],
                "nota": nota,
            }
        )
        if fila[2]:
            reporte["problemas"].append(f"{tabla}.{columna} tiene {fila[2]} huérfanas")

    # ── 2b. Los arrays JSON, que ningún catálogo ve ─────────────────────────
    for tabla, columna, nota in SITIOS_JSON:
        if (tabla, columna) not in presentes:
            reporte["sitios"].append(
                {"sitio": f"{tabla}.{columna}", "estado": "ausente", "nota": nota}
            )
            continue
        filas = conn.execute(
            text(f"SELECT id, {columna} FROM {_q(schema, tabla)}")
        ).fetchall()
        locales = {r[0] for r in conn.execute(text(f"SELECT id FROM {_q(schema, 'users')}"))}
        total_ids, huerfanas, con_contenido = 0, 0, 0
        for _fid, crudo in filas:
            try:
                ids = json.loads(crudo or "[]")
            except (TypeError, json.JSONDecodeError):
                reporte["problemas"].append(f"{tabla}.{columna}: JSON ilegible en id={_fid}")
                continue
            if not isinstance(ids, list) or not ids:
                continue
            con_contenido += 1
            total_ids += len(ids)
            huerfanas += sum(1 for i in ids if i not in locales)
        reporte["sitios"].append(
            {
                "sitio": f"{tabla}.{columna}",
                "estado": "ok",
                "filas": con_contenido,
                "ids_distintos": total_ids,
                "huerfanas": huerfanas,
                "nota": nota + " · JSON: invisible para information_schema",
            }
        )
        if huerfanas:
            reporte["problemas"].append(
                f"{tabla}.{columna} tiene {huerfanas} ids que no existen en users"
            )

    # ── 3. Mapeo por usuario ────────────────────────────────────────────────
    tiene_directorio = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{schema}.users_directory"}
    ).scalar()
    reporte["directorio_existe"] = bool(tiene_directorio)

    # El censo tiene que correr ANTES y DESPUÉS de la 0022 — es el mismo comando y
    # sus dos salidas son las que se comparan. Antes, el puente es `auth_user_id`;
    # después, esa columna ya no existe y `users_directory.user_id` ES `users.id`.
    # Se detecta por catálogo en vez de por revisión de alembic: si el censo
    # dependiera de la revisión, mentiría en una base a medio migrar.
    hay_puente = bool(
        tiene_directorio
        and conn.execute(
            text(
                """
                SELECT count(*) FROM information_schema.columns
                 WHERE table_schema = :s AND table_name = 'users_directory'
                   AND column_name = 'auth_user_id'
                """
            ),
            {"s": schema},
        ).scalar()
    )
    reporte["fase"] = "pre-0022 (puente por auth_user_id)" if hay_puente else "post-0022 (id canónico)"

    sitios_ok = [
        (t, c) for t, c, _ in SITIOS_COLUMNA if (t, c) in presentes
    ]
    union_refs = " UNION ALL ".join(
        f"SELECT {c} AS uid FROM {_q(schema, t)} WHERE {c} IS NOT NULL"
        for t, c in sitios_ok
    ) or "SELECT NULL::varchar AS uid WHERE FALSE"

    if hay_puente:
        # Ojo: se resuelve por auth_user_id, NO por tenant. La misma persona tiene
        # el mismo id canónico en todos los tenants; si dos filas discrepan es un
        # error de datos y hay que verlo, no promediarlo.
        mapa_sql = f"""
            WITH refs AS ({union_refs}),
            dir AS (
                SELECT auth_user_id,
                       min(user_id)                AS user_id,
                       count(DISTINCT user_id)     AS distintos
                  FROM {_q(schema, 'users_directory')}
                 WHERE auth_user_id IS NOT NULL
                 GROUP BY auth_user_id
            )
            SELECT u.id, u.email, u.external_id,
                   d.user_id, coalesce(d.distintos, 0),
                   (SELECT count(*) FROM refs r WHERE r.uid = u.id)
              FROM {_q(schema, 'users')} u
              LEFT JOIN dir d ON d.auth_user_id = u.external_id
             ORDER BY 6 DESC, u.email
        """
    elif tiene_directorio:
        # Post-0022: el mapa vive en users_id_remap, que es lo que deja constancia
        # de quién se migró y quién se quedó con su id local (id_viejo = id_nuevo).
        # Sin esa tabla —base creada de cero, ya canónica— se toma como migrado
        # todo el que esté en el directorio.
        hay_remap = conn.execute(
            text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{schema}.users_id_remap"}
        ).scalar()
        origen = (
            f"""SELECT m.id_nuevo AS uid,
                       CASE WHEN m.id_viejo = m.id_nuevo THEN NULL ELSE m.id_nuevo END AS canonico
                  FROM {_q(schema, 'users_id_remap')} m"""
            if hay_remap
            else f"""SELECT d.user_id AS uid, d.user_id AS canonico
                       FROM {_q(schema, 'users_directory')} d"""
        )
        mapa_sql = f"""
            WITH refs AS ({union_refs}), mapa AS ({origen})
            SELECT u.id, u.email, u.external_id,
                   m.canonico, 0,
                   (SELECT count(*) FROM refs r WHERE r.uid = u.id)
              FROM {_q(schema, 'users')} u
              LEFT JOIN mapa m ON m.uid = u.id
             ORDER BY 6 DESC, u.email
        """
    else:
        mapa_sql = f"""
            WITH refs AS ({union_refs})
            SELECT u.id, u.email, u.external_id,
                   NULL::varchar, 0,
                   (SELECT count(*) FROM refs r WHERE r.uid = u.id)
              FROM {_q(schema, 'users')} u
             ORDER BY 6 DESC, u.email
        """

    sin_mapeo_con_refs = 0
    for uid, email, ext, canonico, distintos, refs in conn.execute(text(mapa_sql)):
        ya_migrado = bool(canonico) and uid == canonico
        estado = (
            "ya migrado" if ya_migrado
            else "mapeable" if canonico
            else "SIN MAPEO"
        )
        if distintos and distintos > 1:
            estado = "AMBIGUO"
            reporte["problemas"].append(
                f"{email}: {distintos} ids canónicos distintos para el mismo auth id"
            )
        if estado == "SIN MAPEO" and refs:
            sin_mapeo_con_refs += 1
        reporte["usuarios"].append(
            {
                "email": email,
                "id_local": uid,
                "external_id": ext,
                "id_canonico": canonico,
                "referencias": refs,
                "estado": estado,
            }
        )
    reporte["sin_mapeo_con_referencias"] = sin_mapeo_con_refs

    # ── 4. Colisiones ───────────────────────────────────────────────────────
    colisiones = []
    if hay_puente:
        colisiones = [
            r[0]
            for r in conn.execute(
                text(
                    f"""
                    SELECT u.email
                      FROM {_q(schema, 'users')} u
                      JOIN {_q(schema, 'users_directory')} d
                        ON d.auth_user_id = u.external_id
                      JOIN {_q(schema, 'users')} otro
                        ON otro.id = d.user_id AND otro.id <> u.id
                    """
                )
            )
        ]
    reporte["colisiones"] = colisiones
    if colisiones:
        reporte["problemas"].append(
            "El id canónico de " + ", ".join(colisiones) + " ya está en uso por otra fila"
        )

    return reporte


def imprimir(rep: dict) -> None:
    print(f"\n{'═' * 78}")
    print(f"  CENSO · repunte al id canónico · schema {rep['schema']}")
    print(f"  fase: {rep.get('fase', 'sin directorio')}")
    print(f"{'═' * 78}\n")

    if rep["sitios_no_inventariados"]:
        print(f"{ROJO}✗ DERIVA DE INVENTARIO{FIN}")
        for s in rep["sitios_no_inventariados"]:
            print(f"    {s} apunta a users(id) y no está en id_remap.SITIOS_COLUMNA")
        print("    Cualquier conteo de acá para abajo es incompleto.\n")
    else:
        print(f"{VERDE}✓{FIN} inventario completo: ninguna FK a users(id) quedó afuera\n")

    print(f"  {'SITIO':<42} {'FILAS':>7} {'IDS':>6} {'HUÉRF':>7}")
    print(f"  {'─' * 42} {'─' * 7} {'─' * 6} {'─' * 7}")
    total_filas = 0
    for s in rep["sitios"]:
        if s["estado"] == "ausente":
            print(f"  {s['sitio']:<42} {GRIS}{'— no existe en esta base':>22}{FIN}")
            continue
        total_filas += s["filas"]
        color = ROJO if s["huerfanas"] else ""
        fin = FIN if s["huerfanas"] else ""
        print(
            f"  {s['sitio']:<42} {s['filas']:>7} {s['ids_distintos']:>6} "
            f"{color}{s['huerfanas']:>7}{fin}"
        )
    print(f"  {'─' * 42} {'─' * 7} {'─' * 6} {'─' * 7}")
    print(f"  {'TOTAL DE REFERENCIAS':<42} {total_filas:>7}\n")

    if not rep["directorio_existe"]:
        print(
            f"{AMARILLO}!{FIN} no existe users_directory: sin él no hay mapeo posible.\n"
            f"    Aplicá la migración 0021 y dejá que un miembro del módulo\n"
            f"    abra una pantalla que resuelva nombres (escritura al leer).\n"
        )

    print(f"  {'USUARIO':<34} {'REFS':>5}  {'ESTADO':<12} ID CANÓNICO")
    print(f"  {'─' * 34} {'─' * 5}  {'─' * 12} {'─' * 36}")
    for u in rep["usuarios"]:
        color = {
            "ya migrado": VERDE, "mapeable": VERDE,
            "SIN MAPEO": ROJO, "AMBIGUO": ROJO,
        }[u["estado"]]
        print(
            f"  {(u['email'] or '(sin email)')[:34]:<34} {u['referencias']:>5}  "
            f"{color}{u['estado']:<12}{FIN} {u['id_canonico'] or '—'}"
        )
    print()

    if rep["problemas"]:
        print(f"{ROJO}  PROBLEMAS{FIN}")
        for p in rep["problemas"]:
            print(f"    · {p}")
        print()

    if rep["sin_mapeo_con_referencias"]:
        print(
            f"{ROJO}  ✗ {rep['sin_mapeo_con_referencias']} usuario(s) con referencias y sin mapeo.{FIN}\n"
            f"    /directory solo devuelve MIEMBROS ACTIVOS del módulo, así que quien\n"
            f"    fue revocado antes del primer barrido no tiene id canónico que traer.\n"
            f"    Opciones: (a) reactivarle el acceso en el Hub, correr un barrido y\n"
            f"    volver a censar; (b) migrar igual con --permitir-sin-mapeo, que los\n"
            f"    deja con su id local — su nombre sigue resolviendo por la proyección\n"
            f"    local, pero nunca se refresca.\n"
        )

    print(f"  {GRIS}No se tocan ({len(NO_SE_TOCAN)}): "
          f"{', '.join(f'{t}.{c}' for t, c, _ in NO_SE_TOCAN[:3])}, …{FIN}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="salida JSON para diffear")
    args = ap.parse_args()

    engine = get_db_engine()
    with engine.connect() as conn:
        rep = censar(conn, DATABASE_SCHEMA or "public")

    if args.json:
        print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    else:
        imprimir(rep)

    if rep["sitios_no_inventariados"] or rep["colisiones"]:
        return 2
    if any("huérfanas" in p or "no existen" in p or "ilegible" in p for p in rep["problemas"]):
        return 2
    if rep["sin_mapeo_con_referencias"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
