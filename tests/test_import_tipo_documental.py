"""Qué tipo documental tiene lo que se importa, y quién decide si se aprueba.

Antes: todo lo importado nacía como `procedimiento` —el default de la columna,
no una decisión— y pedía aprobación siempre, porque la pantalla mandaba
`requires_approval` fijo en `true`. Una ley entraba por el mismo camino que un
procedimiento de pista, y el acta del PDF congelado terminaba afirmando que
alguien había aprobado una ley.

Ahora la decisión sale del behavior `aprobacion` del tipo documental, que es
configuración del workspace y no un campo del request. Estos tests fijan las dos
mitades: de dónde sale el tipo (elección explícita > default de la carpeta,
heredable > fallback) y que la aprobación se derive de él sin que el cliente
pueda opinar.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.models import DocumentType, Folder, Workspace
from process_ai_core.domains.document_types import (
    TIPO_POR_DEFECTO,
    TipoDocumentalInvalido,
    resolver_tipo_de_importacion,
)


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def ws(session):
    w = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(w)
    session.commit()
    return w


def _tipo(session, ws, key, *, aprobacion, referencia=False, activo=True):
    t = DocumentType(
        id=_uid(), workspace_id=ws.id, key=key, label=key.title(),
        code_prefix=key[:2].upper(),
        behaviors_json=json.dumps({"aprobacion": aprobacion, "es_referencia": referencia}),
        is_active=activo, sort_order=10, origin="default",
    )
    session.add(t)
    session.commit()
    return t


def _carpeta(session, ws, nombre, *, padre=None, default_tipo=None):
    f = Folder(
        id=_uid(), workspace_id=ws.id, name=nombre,
        path=f"{padre.path}/{nombre}" if padre else nombre,
        parent_id=padre.id if padre else None,
        default_document_type=default_tipo,
    )
    session.add(f)
    session.commit()
    return f


def _resolver(session, ws, folder, tipo=None):
    return resolver_tipo_de_importacion(
        session, workspace_id=ws.id, folder=folder, tipo_pedido=tipo
    )


# ── La aprobación sale del tipo ─────────────────────────────────────────────

def test_un_procedimiento_entra_a_revision(session, ws):
    _tipo(session, ws, "procedimiento", aprobacion=True)
    carpeta = _carpeta(session, ws, "Operación")

    key, requiere = _resolver(session, ws, carpeta, "procedimiento")
    assert (key, requiere) == ("procedimiento", True)


def test_material_externo_entra_vigente_sin_aprobacion(session, ws):
    """Una ley o un presupuesto de un proveedor no los aprueba nadie de adentro:
    se incorporan. Aprobarlos sería firmar algo que no escribimos."""
    _tipo(session, ws, "normativa", aprobacion=False, referencia=True)
    carpeta = _carpeta(session, ws, "Normativa")

    key, requiere = _resolver(session, ws, carpeta, "normativa")
    assert (key, requiere) == ("normativa", False)


# ── De dónde sale el tipo ───────────────────────────────────────────────────

def test_sin_eleccion_manda_el_default_de_la_carpeta(session, ws):
    """En una carpeta de normativa no hay que decidir archivo por archivo."""
    _tipo(session, ws, "procedimiento", aprobacion=True)
    _tipo(session, ws, "normativa", aprobacion=False, referencia=True)
    carpeta = _carpeta(session, ws, "Normativa", default_tipo="normativa")

    assert _resolver(session, ws, carpeta) == ("normativa", False)


def test_lo_que_elige_quien_importa_le_gana_al_default_de_la_carpeta(session, ws):
    """En "Clientes" conviven presupuestos y algún procedimiento: la carpeta
    propone, no impone."""
    _tipo(session, ws, "procedimiento", aprobacion=True)
    _tipo(session, ws, "presupuesto", aprobacion=False, referencia=True)
    carpeta = _carpeta(session, ws, "Clientes", default_tipo="presupuesto")

    assert _resolver(session, ws, carpeta, "procedimiento") == ("procedimiento", True)


def test_el_default_se_hereda_de_la_carpeta_padre(session, ws):
    _tipo(session, ws, "procedimiento", aprobacion=True)
    _tipo(session, ws, "normativa", aprobacion=False, referencia=True)
    padre = _carpeta(session, ws, "Normativa", default_tipo="normativa")
    hija = _carpeta(session, ws, "Ambiental", padre=padre)

    assert _resolver(session, ws, hija) == ("normativa", False)


def test_la_hija_puede_pisar_el_default_del_padre(session, ws):
    _tipo(session, ws, "procedimiento", aprobacion=True)
    _tipo(session, ws, "normativa", aprobacion=False, referencia=True)
    padre = _carpeta(session, ws, "Normativa", default_tipo="normativa")
    hija = _carpeta(session, ws, "Nuestros procedimientos", padre=padre,
                    default_tipo="procedimiento")

    assert _resolver(session, ws, hija) == ("procedimiento", True)


def test_sin_default_en_ninguna_parte_cae_al_tipo_por_defecto(session, ws):
    _tipo(session, ws, TIPO_POR_DEFECTO, aprobacion=True)
    carpeta = _carpeta(session, ws, "Suelta")

    assert _resolver(session, ws, carpeta) == (TIPO_POR_DEFECTO, True)


# ── Ante la duda, se pide aprobación ────────────────────────────────────────

def test_un_tipo_inexistente_elegido_a_mano_es_un_error_explicito(session, ws):
    """Quien eligió algo que no está tiene que enterarse, no recibir otra cosa."""
    _tipo(session, ws, TIPO_POR_DEFECTO, aprobacion=True)
    carpeta = _carpeta(session, ws, "Operación")

    with pytest.raises(TipoDocumentalInvalido):
        _resolver(session, ws, carpeta, "tipo_que_no_existe")


def test_un_default_de_carpeta_que_quedo_colgado_no_rompe_la_importacion(session, ws):
    """Que alguien haya borrado un tipo no puede impedir importar. Se cae al tipo
    por defecto, que es el más exigente."""
    _tipo(session, ws, TIPO_POR_DEFECTO, aprobacion=True)
    carpeta = _carpeta(session, ws, "Vieja", default_tipo="tipo_borrado")

    assert _resolver(session, ws, carpeta) == (TIPO_POR_DEFECTO, True)


def test_un_tipo_desactivado_no_se_usa(session, ws):
    _tipo(session, ws, TIPO_POR_DEFECTO, aprobacion=True)
    _tipo(session, ws, "obsoleto", aprobacion=False, activo=False)
    carpeta = _carpeta(session, ws, "Operación", default_tipo="obsoleto")

    assert _resolver(session, ws, carpeta) == (TIPO_POR_DEFECTO, True)
    with pytest.raises(TipoDocumentalInvalido):
        _resolver(session, ws, carpeta, "obsoleto")


def test_si_el_workspace_no_tiene_tipos_se_exige_aprobacion(session, ws):
    """Un tenant a medio provisionar no puede terminar publicando sin revisión."""
    carpeta = _carpeta(session, ws, "Operación")

    assert _resolver(session, ws, carpeta) == (TIPO_POR_DEFECTO, True)


def test_behaviors_ilegibles_no_habilitan_publicar_sin_revision(session, ws):
    t = _tipo(session, ws, "roto", aprobacion=True)
    t.behaviors_json = "{esto no es json"
    session.commit()
    carpeta = _carpeta(session, ws, "Operación")

    assert _resolver(session, ws, carpeta, "roto") == ("roto", True)


def test_un_tipo_de_otro_workspace_no_se_puede_usar(session, ws):
    otro = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="Otro",
                     workspace_type="organization")
    session.add(otro)
    session.commit()
    _tipo(session, otro, "normativa", aprobacion=False, referencia=True)
    _tipo(session, ws, TIPO_POR_DEFECTO, aprobacion=True)
    carpeta = _carpeta(session, ws, "Operación")

    with pytest.raises(TipoDocumentalInvalido):
        _resolver(session, ws, carpeta, "normativa")
