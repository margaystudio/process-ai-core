"""La identidad del request llega al directorio — y no se filtra entre requests.

`capture_request_identity` es una dependencia **async** a propósito: FastAPI
corre las dependencias `def` en el threadpool, y un contextvar seteado ahí NO
vuelve al contexto del request. Si alguien la convierte a `def` porque "no hace
nada asincrónico", el directorio deja de refrescarse y nadie se entera: los
nombres siguen resolviendo contra la proyección local y el único síntoma es que
se ven desactualizados. Este test es el que avisa.

Se prueban los dos tipos de endpoint que hay en los routers reales (`def` y
`async def`) y el aislamiento entre routers.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from process_ai_core.db.directory import (
    clear_request_identity,
    get_request_identity,
    set_request_identity,
)


@pytest.fixture(autouse=True)
def _sin_identidad():
    clear_request_identity()
    yield
    clear_request_identity()


async def _capturar_sin_red():
    """Réplica de `capture_request_identity` sin la llamada a Workspace.

    Lo que se está probando es la propagación del contextvar, no el HTTP.
    """
    set_request_identity("jwt-de-prueba", "tenant-42")


def _identidad() -> dict:
    ident = get_request_identity()
    return {
        "token": ident.token if ident else None,
        "tenant": ident.tenant_id if ident else None,
    }


@pytest.fixture
def client() -> TestClient:
    con_dep = APIRouter(dependencies=[Depends(_capturar_sin_red)])

    @con_dep.get("/sync")
    def _sync():          # endpoint `def`: FastAPI lo manda al threadpool
        return _identidad()

    @con_dep.get("/async")
    async def _async():   # endpoint `async def`: corre en el event loop
        return _identidad()

    sin_dep = APIRouter()

    @sin_dep.get("/aislado")
    def _aislado():
        return _identidad()

    app = FastAPI()
    app.include_router(con_dep)
    app.include_router(sin_dep)
    return TestClient(app)


def test_endpoint_sync_ve_la_identidad(client):
    """Un endpoint `def` corre en el threadpool, pero hereda una COPIA del
    contexto al despacharse, así que ve lo que seteó la dependencia."""
    assert client.get("/sync").json() == {
        "token": "jwt-de-prueba", "tenant": "tenant-42"
    }


def test_endpoint_async_ve_la_identidad(client):
    assert client.get("/async").json() == {
        "token": "jwt-de-prueba", "tenant": "tenant-42"
    }


def test_un_router_sin_la_dependencia_no_hereda_identidad(client):
    """Sin identidad el directorio no se refresca y sirve lo que tenga. Lo que
    NUNCA puede pasar es que agarre el JWT de otro usuario."""
    client.get("/sync")
    assert client.get("/aislado").json()["token"] is None


def test_la_dependencia_real_es_async():
    """El corazón del asunto: si esto pasa a ser `def`, el contextvar se pierde."""
    import inspect

    from api.request_identity import capture_request_identity

    assert inspect.iscoroutinefunction(capture_request_identity)
