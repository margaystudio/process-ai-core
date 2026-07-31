"""Directorio de usuarios: escritura al leer, revocación sin borrado, degradación.

Cubre el §3 de `margay-dev-agent/knowledge/11-directorio-de-usuarios.md` tal como
lo implementa `process_ai_core/db/directory.py`.

Lo que se prueba acá es lo que falló en OMS: que **el código que lee es el que
escribe**. Un test que llenara la tabla a mano y después leyera no probaría nada
del patrón — probaría un SELECT.

Corre contra la base real (`get_db_session`) y no contra SQLite en memoria a
propósito: el refresh abre su **propia** sesión para no mezclarse con la
transacción de negocio del que está leyendo, así que un engine por fixture haría
que la escritura y la lectura fueran a dos bases distintas. Levantar la base con
`./tools/dev_db.sh up`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from process_ai_core.db import directory as dir_mod
from process_ai_core.db.database import get_db_session
from process_ai_core.db.directory import (
    clear_request_identity,
    resolve_usuarios,
    set_request_identity,
    tenant_id_de_workspace,
)
from process_ai_core.db.models import User, UserDirectory, Workspace
from process_ai_core.db.signatories import resolve_signatories


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture(autouse=True)
def _sin_identidad():
    """Cada test decide si hay JWT; ninguno hereda el del anterior."""
    clear_request_identity()
    yield
    clear_request_identity()


@pytest.fixture
def tenant() -> str:
    """Un tenant propio por test: el directorio se llavea por tenant y así los
    barridos de un test no pisan las filas de otro."""
    return f"tenant-dir-{_uid()[:8]}"


@pytest.fixture
def workspace(session, tenant):
    ws = Workspace(
        id=f"dir-ws-{_uid()[:8]}",
        slug=f"dir-ws-{_uid()[:8]}",
        name="Estación Centro",
        tenant_id=tenant,
        workspace_type="organization",
    )
    session.add(ws)
    session.commit()
    return ws


def _usuario(session, *, nombre: str, external_id: str) -> User:
    """Usuario local. Su `id` ya es el canónico (post-0022); `external_id` es el
    sub del JWT y no participa de la resolución de nombres."""
    u = User(
        id=_uid(), email=f"{_uid()[:8]}@dirtest.local", name=nombre,
        external_id=external_id,
    )
    session.add(u)
    session.commit()
    return u


def _entrada(user_id: str, display_name: str, email: str) -> dict:
    """Una fila como la manda `/directory` de Workspace.

    `user_id` es el id CANÓNICO (`workspace.users.id`). Desde la migración
    `0022_id_canonico` es **el mismo valor** que `process_ai.users.id`, así que
    acá se pasa el id del usuario local directamente: esa igualdad es justo lo
    que hace que el join del directorio sea directo.

    `auth_user_id` sigue viniendo en el DTO real (otros módulos indexan por ahí)
    y acá se ignora a propósito: el módulo ya no lo guarda.
    """
    partes = display_name.split(" ")
    return {
        "auth_user_id": f"auth-{user_id[:8]}",
        "user_id": user_id,
        "email": email,
        "first_name": partes[0],
        "last_name": " ".join(partes[1:]) or None,
        "display_name": display_name,
    }


def _vencer_ttl(tenant: str) -> None:
    with get_db_session() as s:
        s.query(UserDirectory).filter_by(tenant_id=tenant).update(
            {"synced_at": datetime.utcnow() - timedelta(days=1)}
        )


def _filas(tenant: str) -> dict[str, dict]:
    """`user_id → {status, display_name}` leído en una sesión propia.

    Se devuelven dicts y no instancias del ORM: la sesión se cierra al salir del
    `with` y cualquier atributo que no se haya cargado ahí adentro explotaría
    con `DetachedInstanceError`.
    """
    with get_db_session() as s:
        return {
            f.user_id: {"status": f.status, "display_name": f.display_name}
            for f in s.query(UserDirectory).filter_by(tenant_id=tenant)
        }


# ── Escritura al leer ────────────────────────────────────────────────────────


class TestEscrituraAlLeer:
    def test_leer_llena_la_tabla(self, session, tenant, workspace, monkeypatch):
        """La tabla arranca vacía y se llena porque alguien pidió un nombre.

        Es el invariante entero: no hay job, ni cron, ni webhook. Si esta tabla
        queda vacía es porque nadie está resolviendo nombres — que es
        exactamente lo que nadie notó en `oms.tenant_users_cache`.
        """
        sub = _uid()
        u = _usuario(session, nombre="Viejo", external_id=sub)

        monkeypatch.setattr(
            dir_mod, "_fetch_directorio",
            lambda tid, tok: [_entrada(u.id, "Ana Gómez", "a@t.com")],
        )
        set_request_identity("jwt", tenant)

        assert _filas(tenant) == {}
        nombres = resolve_usuarios(session, tenant, [u.id])
        assert len(_filas(tenant)) == 1
        assert nombres[u.id]["nombre"] == "Ana Gómez"

    def test_el_directorio_gana_sobre_la_proyeccion_local(
        self, session, tenant, workspace, monkeypatch
    ):
        """`users.name` queda congelado en el primer login; el directorio no.

        Es lo que la tabla aporta a las columnas que Process AI ya tenía: no
        resuelve lo irresoluble, resuelve lo desactualizado.
        """
        sub = _uid()
        u = _usuario(session, nombre="Ana Perez", external_id=sub)

        monkeypatch.setattr(
            dir_mod, "_fetch_directorio",
            lambda tid, tok: [_entrada(u.id, "Ana Gómez de Perez", "a@t.com")],
        )
        set_request_identity("jwt", tenant)

        nombres = resolve_usuarios(session, tenant, [u.id])
        assert nombres[u.id]["nombre"] == "Ana Gómez de Perez"

    def test_no_se_llama_a_workspace_dentro_del_ttl(
        self, session, tenant, workspace, monkeypatch
    ):
        sub = _uid()
        u = _usuario(session, nombre="Ana", external_id=sub)

        llamadas: list[str] = []

        def _fetch(tid, tok):
            llamadas.append(tid)
            return [_entrada(u.id, "Ana Gómez", "a@t.com")]

        monkeypatch.setattr(dir_mod, "_fetch_directorio", _fetch)
        set_request_identity("jwt", tenant)

        for _ in range(3):
            resolve_usuarios(session, tenant, [u.id])
        assert len(llamadas) == 1

    def test_no_se_llama_al_directorio_de_otro_tenant(
        self, session, tenant, workspace, monkeypatch
    ):
        """El JWT autoriza el directorio del tenant activo, no el de cualquiera."""
        u = _usuario(session, nombre="Ana", external_id=_uid())

        llamadas: list[str] = []

        def _fetch(tid, tok):
            llamadas.append(tid)
            return []

        monkeypatch.setattr(dir_mod, "_fetch_directorio", _fetch)
        set_request_identity("jwt", tenant)

        resolve_usuarios(session, f"otro-{tenant}", [u.id])
        assert llamadas == []


# ── Nunca se borra una fila ──────────────────────────────────────────────────


class TestRevocacion:
    def test_el_que_sale_queda_revoked_y_sigue_resolviendo(
        self, session, tenant, workspace, monkeypatch
    ):
        """El histórico de hace dos años tiene que seguir mostrando el nombre."""
        sub_a, sub_b = _uid(), _uid()
        a = _usuario(session, nombre="A", external_id=sub_a)
        b = _usuario(session, nombre="B", external_id=sub_b)

        padron = [
            _entrada(a.id, "Ana Gómez", "a@t.com"),
            _entrada(b.id, "Beto Ruiz", "b@t.com"),
        ]
        monkeypatch.setattr(dir_mod, "_fetch_directorio", lambda tid, tok: padron)
        set_request_identity("jwt", tenant)
        resolve_usuarios(session, tenant, [a.id, b.id])

        # Beto sale del módulo.
        _vencer_ttl(tenant)
        monkeypatch.setattr(dir_mod, "_fetch_directorio", lambda tid, tok: [padron[0]])

        session.expire_all()
        nombres = resolve_usuarios(session, tenant, [a.id, b.id])

        filas = _filas(tenant)
        assert len(filas) == 2, "una fila borrada es un nombre perdido para siempre"
        assert filas[a.id]["status"] == "active"
        assert filas[b.id]["status"] == "revoked"
        assert nombres[b.id]["nombre"] == "Beto Ruiz"


# ── Degradación elegante ─────────────────────────────────────────────────────


class TestDegradacion:
    def test_workspace_caido_sirve_lo_vencido(
        self, session, tenant, workspace, monkeypatch
    ):
        sub = _uid()
        u = _usuario(session, nombre="Ana", external_id=sub)

        monkeypatch.setattr(
            dir_mod, "_fetch_directorio",
            lambda tid, tok: [_entrada(u.id, "Ana Gómez", "a@t.com")],
        )
        set_request_identity("jwt", tenant)
        resolve_usuarios(session, tenant, [u.id])

        # Vence el TTL y Workspace deja de responder.
        _vencer_ttl(tenant)
        monkeypatch.setattr(dir_mod, "_fetch_directorio", lambda tid, tok: None)

        session.expire_all()
        nombres = resolve_usuarios(session, tenant, [u.id])
        assert nombres[u.id]["nombre"] == "Ana Gómez"
        assert len(_filas(tenant)) == 1

    def test_sin_directorio_cae_a_la_proyeccion_local(self, session, tenant, workspace):
        """Primer arranque con Workspace caído: se muestra lo que hay."""
        u = _usuario(session, nombre="Ana Perez", external_id=_uid())
        nombres = resolve_usuarios(session, tenant, [u.id])
        assert nombres[u.id]["nombre"] == "Ana Perez"

    def test_sin_identidad_no_llama_a_workspace(
        self, session, tenant, workspace, monkeypatch
    ):
        """Jobs, scripts de tooling y tests no tienen JWT."""
        u = _usuario(session, nombre="Ana", external_id=_uid())

        def _explota(tid, tok):
            raise AssertionError("no hay JWT: no se debe llamar a Workspace")

        monkeypatch.setattr(dir_mod, "_fetch_directorio", _explota)
        assert resolve_usuarios(session, tenant, [u.id])[u.id]["nombre"] == "Ana"

    def test_error_de_workspace_no_rompe_la_resolucion(
        self, session, tenant, workspace, monkeypatch
    ):
        u = _usuario(session, nombre="Ana", external_id=_uid())

        def _explota(tid, tok):
            raise RuntimeError("boom")

        monkeypatch.setattr(dir_mod, "_fetch_directorio", _explota)
        set_request_identity("jwt", tenant)
        assert resolve_usuarios(session, tenant, [u.id])[u.id]["nombre"] == "Ana"

    def test_id_desconocido_devuelve_vacio_sin_faltar_la_key(self, session, tenant):
        fantasma = _uid()
        assert resolve_usuarios(session, tenant, [fantasma]) == {
            fantasma: {"nombre": "", "email": ""}
        }


# ── Integración con el acta ──────────────────────────────────────────────────


class TestFirmantes:
    def test_resolve_signatories_toma_el_nombre_del_directorio(
        self, session, tenant, workspace, monkeypatch
    ):
        sub = _uid()
        u = _usuario(session, nombre="Congelado", external_id=sub)

        monkeypatch.setattr(
            dir_mod, "_fetch_directorio",
            lambda tid, tok: [_entrada(u.id, "Ana Gómez", "a@t.com")],
        )
        set_request_identity("jwt", tenant)

        firmantes = resolve_signatories(session, workspace.id, [u.id])
        assert firmantes[u.id][0] == "Ana Gómez"
        assert firmantes[u.id][1] is None  # sin rol operativo asignado

    def test_tenant_id_de_workspace(self, session, tenant, workspace):
        assert tenant_id_de_workspace(session, workspace.id) == tenant
        assert tenant_id_de_workspace(session, None) is None
        assert tenant_id_de_workspace(session, _uid()) is None
