"""Qué tipo documental exige aprobación, y que la migración diga lo mismo que el template.

El behavior `aprobacion` no lo leía nadie: la pantalla de importación mandaba
`requires_approval` fijo en `true`. Al conectarlo (ver
`domains/document_types/resolucion.py`) esos valores pasaron a decidir de verdad
si un documento entra a revisión, así que un `false` de más ahora significa
publicar sin que nadie lo mire.

El criterio es de quién es el documento: lo propio se aprueba, lo externo se
incorpora. Estos tests fijan el resultado de esa decisión y —lo más importante—
que la migración de datos y el template no se separen. Los tipos son por tenant:
el template siembra los workspaces nuevos y la migración corrige los que ya
existen. Si los dos no dicen exactamente lo mismo, un cliente viejo y uno nuevo
terminan gobernando sus documentos distinto sin que nadie lo haya decidido.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from process_ai_core.domains.document_types.defaults import (
    DEFAULT_DOCUMENT_TYPES,
    build_default_rows,
)


def _behaviors(key: str) -> dict[str, bool]:
    for tipo in DEFAULT_DOCUMENT_TYPES:
        if tipo["key"] == key:
            return tipo["behaviors"]
    raise AssertionError(f"No existe el tipo '{key}' en el template")


def _migracion():
    ruta = (
        pathlib.Path(__file__).resolve().parents[1]
        / "alembic" / "versions" / "0027_tipos_aprobacion.py"
    )
    spec = importlib.util.spec_from_file_location("migracion_0027", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ── Lo externo no se aprueba: se incorpora ──────────────────────────────────

@pytest.mark.parametrize("key", ["normativa", "presupuesto", "manual_externo"])
def test_el_material_de_terceros_no_pide_aprobacion_y_se_cita_como_referencia(key):
    """Nadie de la organización puede aprobar una ley ni el presupuesto que le
    pasó un proveedor. `es_referencia` es lo que hace que Tyto lo cite como 🟡
    en vez de 🟢: decir que está aprobado sería afirmar algo que no pasó."""
    b = _behaviors(key)
    assert b["aprobacion"] is False
    assert b["es_referencia"] is True


# ── Lo propio se aprueba ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "key",
    [
        "procedimiento", "instructivo", "manual_interno", "manual", "politica",
        "formulario", "contrato", "nda", "checklist", "tramite", "faq_validada",
    ],
)
def test_lo_que_escribe_la_organizacion_pasa_por_revision(key):
    """Ninguno de estos puede publicarse sin que alguien se haga responsable.
    Instructivo y trámite además alimentan a Tyto: sin aprobación entrarían como
    documentación 🟢 sin que nadie los haya mirado."""
    b = _behaviors(key)
    assert b["aprobacion"] is True, f"'{key}' se publicaría sin revisión"
    assert b["es_referencia"] is False


def test_no_hay_ningun_tipo_que_sea_propio_y_de_referencia_a_la_vez():
    """Las dos marcas responden a la misma pregunta —de quién es— así que
    contradecirse sería un error de configuración, no una combinación válida."""
    for tipo in DEFAULT_DOCUMENT_TYPES:
        b = tipo["behaviors"]
        if b["es_referencia"]:
            assert b["aprobacion"] is False, (
                f"'{tipo['key']}' es material de referencia y además pide aprobación"
            )


def test_todo_tipo_sembrado_declara_los_comportamientos_completos():
    """Un behavior ausente se lee como False, y para `aprobacion` eso significa
    publicar sin revisión. Ninguna key puede faltar por olvido."""
    from process_ai_core.domains.document_types.defaults import BEHAVIOR_KEYS

    for tipo in DEFAULT_DOCUMENT_TYPES:
        assert set(tipo["behaviors"]) == set(BEHAVIOR_KEYS), tipo["key"]


# ── La migración de datos y el template no se pueden separar ────────────────

def test_la_migracion_lleva_a_los_tenants_viejos_al_mismo_estado_que_el_template():
    """Aplicar los cambios de la migración sobre los valores VIEJOS tiene que dar
    exactamente lo que hoy siembra el template. Si alguien edita uno de los dos
    lados y se olvida del otro, este test lo caza: un cliente que ya existía y
    uno nuevo quedarían gobernando distinto."""
    cambios = _migracion().CAMBIOS

    for key, por_behavior in cambios.items():
        esperado = _behaviors(key)
        for behavior, (viejo, nuevo) in por_behavior.items():
            assert nuevo == esperado[behavior], (
                f"La migración deja '{key}.{behavior}' en {nuevo} y el template "
                f"lo siembra en {esperado[behavior]}"
            )
            assert viejo != nuevo, (
                f"'{key}.{behavior}' figura en la migración sin cambiar nada"
            )


def test_la_migracion_solo_toca_tipos_que_existen_en_el_template():
    cambios = _migracion().CAMBIOS
    keys = {t["key"] for t in DEFAULT_DOCUMENT_TYPES}
    assert set(cambios) <= keys, set(cambios) - keys


def test_las_filas_sembradas_se_marcan_como_del_template():
    """La migración solo corrige filas `origin='default'`: si el sembrado dejara
    de marcarlas así, no alcanzaría a ninguna y no se notaría."""
    filas = build_default_rows("ws-1")
    assert filas and all(f["origin"] == "default" for f in filas)
