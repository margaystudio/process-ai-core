"""
Las variables retiradas con la firma de URLs no rompen el arranque.

Contexto
--------
`ARTIFACT_SIGNING_SECRET` y `ARTIFACT_URL_TTL_SECONDS` se eliminaron junto con
`api/artifact_signing.py`. Pero una revisión de Cloud Run que ya las tiene
seteadas las conserva —`--update-env-vars` / `--update-secrets` son merge, no
reemplazo—, así que el proceso va a arrancar con ellas en el entorno durante al
menos un deploy. Que eso no lo voltee no es una suposición: es una propiedad, y
acá queda fijada.

La propiedad se sostiene por CÓMO está hecha la config, no por casualidad:
`Settings` es un `@dataclass` que no lee el entorno por su cuenta. Es
`get_settings()` el que hace un `os.getenv` explícito por campo. Una variable que
ningún campo pide no se lee, y no hay a dónde rechazarla. (Con `BaseSettings` de
Pydantic y `extra="forbid"` el resultado sería el opuesto: arranque roto.)
"""

from __future__ import annotations

import dataclasses

import pytest

from process_ai_core import config as cfg

VARIABLES_RETIRADAS = ("ARTIFACT_SIGNING_SECRET", "ARTIFACT_URL_TTL_SECONDS")


@pytest.fixture(autouse=True)
def cache_limpio():
    cfg.get_settings.cache_clear()
    yield
    cfg.get_settings.cache_clear()


def test_la_config_no_declara_los_campos_retirados():
    campos = {f.name for f in dataclasses.fields(cfg.Settings)}

    assert "artifact_signing_secret" not in campos
    assert "artifact_url_ttl_seconds" not in campos


def test_con_las_variables_en_el_entorno_la_config_se_resuelve_igual(monkeypatch):
    """El caso real del primer deploy: la revisión nueva las hereda de la vieja."""
    for nombre in VARIABLES_RETIRADAS:
        monkeypatch.setenv(nombre, "valor-que-ya-nadie-lee")

    settings = cfg.get_settings()

    assert settings.api_base_url  # se construyó sin lanzar
    assert not hasattr(settings, "artifact_signing_secret")


def test_sin_las_variables_la_config_se_resuelve_igual(monkeypatch):
    for nombre in VARIABLES_RETIRADAS:
        monkeypatch.delenv(nombre, raising=False)

    assert cfg.get_settings().api_base_url


def test_la_config_no_lee_el_entorno_por_su_cuenta(monkeypatch):
    """
    Es la razón de fondo de los dos tests de arriba. Si alguien migrara `Settings`
    a `BaseSettings` de Pydantic con `extra="forbid"`, cualquier variable de más
    en el entorno voltearía el arranque — y en Cloud Run las variables de más son
    lo normal durante una transición.
    """
    monkeypatch.setenv("UNA_VARIABLE_QUE_NADIE_DECLARA", "x")

    settings = cfg.get_settings()

    assert dataclasses.is_dataclass(settings)
    assert not hasattr(settings, "una_variable_que_nadie_declara")
