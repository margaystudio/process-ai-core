"""El inventario de sitios que referencian a `users.id` no se puede quedar atrás.

`process_ai_core/db/id_remap.py` es la lista que usan el censo y la migración
`0022_id_canonico`. Si alguien agrega una columna que apunta a usuarios y no la
anota ahí, el repunte de PK la deja apuntando a un id que ya no existe — y como
no hay nada que se queje, se descubre meses después con un nombre en blanco.

Este test es la guarda: corre contra el esquema real y falla si aparece una FK a
`users(id)` fuera del inventario.
"""

from __future__ import annotations

import pytest

from process_ai_core.db.database import DATABASE_SCHEMA, get_db_engine
from process_ai_core.db.id_remap import (
    NO_SE_TOCAN,
    SITIOS_COLUMNA,
    SITIOS_JSON,
    columnas_existentes,
    sitios_no_inventariados,
)


@pytest.fixture
def conn():
    with get_db_engine().connect() as c:
        yield c


def test_ninguna_fk_a_users_queda_fuera_del_inventario(conn):
    faltantes = sitios_no_inventariados(conn, DATABASE_SCHEMA or "public")
    assert not faltantes, (
        "Estas columnas apuntan a users(id) y no están en id_remap.SITIOS_COLUMNA: "
        + ", ".join(f"{t}.{c}" for t, c in sorted(faltantes))
        + ". Agregalas, o la migración 0022 las va a dejar con ids muertos."
    )


def test_los_sitios_sin_fk_estan_inventariados():
    """Los tres que un barrido por catálogo NO ve.

    Son los peligrosos justamente porque `information_schema` no los delata:
    dos tablas de auditoría sin FK a propósito (migración 0018) y un array JSON
    serializado en `Text`, que para Postgres es una columna de texto cualquiera.
    """
    inventariados = {(t, c) for t, c, _ in SITIOS_COLUMNA} | {
        (t, c) for t, c, _ in SITIOS_JSON
    }
    for sitio in [
        ("tyto_query_log", "user_id"),
        ("tyto_session", "user_id"),
        ("validations", "assigned_approver_ids"),
    ]:
        assert sitio in inventariados, f"{sitio} salió del inventario"


def test_el_acta_congelada_no_esta_entre_los_sitios_a_migrar():
    """§5: los `acta_*` son TEXTO histórico, no ids. Tocarlos reescribe el acta.

    Si alguien los agregara a SITIOS_COLUMNA "para actualizar todo lo que huele
    a usuario", la migración les aplicaría un remap de ids sobre un nombre
    propio. No fallaría: simplemente no haría nada, y quedaría la idea de que
    esos campos se migran.
    """
    a_migrar = {(t, c) for t, c, _ in SITIOS_COLUMNA + SITIOS_JSON}
    intocables = {(t, c) for t, c, _ in NO_SE_TOCAN}
    assert not (a_migrar & intocables)
    assert ("document_versions", "acta_approved_by_name") in intocables
    assert ("users", "external_id") in intocables


def test_ninguna_migracion_importa_el_inventario_vivo():
    """Una migración no le pregunta al código de HOY cómo era el esquema de ayer.

    `SITIOS_COLUMNA` describe el esquema actual y evoluciona. Una migración corre
    contra el esquema de SU momento y tiene que poder correr desde una base vacía
    para siempre. Importar esas listas hace que un renombre posterior le cambie el
    comportamiento **retroactivamente**.

    Pasó y llegó al CI: la `0023` renombró `document_relations.confirmed_by` a
    `decided_by`, se actualizó el inventario, y la `0022` —que corre antes, cuando
    la columna todavía se llama `confirmed_by`— empezó a abortar con "hay FKs
    fuera del inventario". Contra una base ya migrada no se ve nunca.

    Las FUNCIONES sí se comparten: no envejecen, y reciben la lista por parámetro.
    Cada migración lleva su foto congelada (ver `_SITIOS_AL_MOMENTO_DE_LA_0022`).
    """
    import pathlib
    import re

    versiones = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
    culpables = []
    for archivo in sorted(versiones.glob("*.py")):
        texto = archivo.read_text(encoding="utf-8")
        for linea in texto.splitlines():
            if not re.search(r"import.*\bid_remap\b|from .*id_remap import", linea):
                continue
            if re.search(r"\bSITIOS_COLUMNA\b|\bSITIOS_JSON\b|\bNO_SE_TOCAN\b", linea):
                culpables.append(f"{archivo.name}: {linea.strip()}")

    assert not culpables, (
        "Estas migraciones importan listas del inventario vivo:\n  "
        + "\n  ".join(culpables)
        + "\nCopiá la lista adentro de la migración como foto congelada y pasásela "
        "por parámetro a los helpers."
    )


def test_columnas_existentes_solo_devuelve_lo_que_hay(conn):
    """Los ambientes no están todos en la misma revisión.

    Prod estuvo mucho tiempo en `0012`, sin las tablas de Tyto. La migración
    opera sobre lo que hay, no sobre lo que debería haber.
    """
    presentes = columnas_existentes(conn, DATABASE_SCHEMA or "public")
    inventario = {(t, c) for t, c, _ in SITIOS_COLUMNA + SITIOS_JSON}
    assert presentes <= inventario
    # En una base a head están todas.
    assert ("document_versions", "approved_by") in presentes
    assert ("validations", "assigned_approver_ids") in presentes
