"""Los payloads traen el nombre resuelto, no el uuid — y sin N+1.

Lo que se está protegiendo es un bug que el usuario veía en pantalla: el
historial decía "Aprobada el 3/2/2026 por 8a5f4e82-2ca9-4515-90fd-392947ec87a3".
La UI intentaba resolverlo con un `getUser()` por id contra
`GET /api/v1/users/{id}`, que es **self-only por diseño** (403 para cualquiera
que no seas vos), y el `catch` terminaba pintando el uuid.

La corrección es de servidor: los nombres se resuelven contra el directorio del
módulo y viajan en el payload que ya se pedía. Un solo round-trip, un solo lote,
y sin exponer un endpoint de resolución nuevo.

Los `*_name` NO son columnas: se resuelven al leer. Es la diferencia con el
anti-patrón #2 (`oms.orders.created_by_name`), donde el nombre quedó guardado y
los pedidos viejos muestran para siempre el nombre que la persona tenía ese día.
"""

from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

from api.routes import validations as validations_route
from api.routes.documents import versions as versions_route
from process_ai_core.db import directory as dir_mod
from process_ai_core.db.database import get_db_session
from process_ai_core.db.directory import clear_request_identity, set_request_identity
from process_ai_core.db.models import (
    AuditLog,
    Document,
    Folder,
    DocumentVersion,
    User,
    UserDirectory,
    Validation,
    Workspace,
    WorkspaceMembership,
)


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    with get_db_session() as s:
        yield s


@pytest.fixture(autouse=True)
def _sin_identidad():
    clear_request_identity()
    yield
    clear_request_identity()


@pytest.fixture
def escenario(session):
    """Documento con dos versiones y dos validaciones, de dos personas distintas.

    Dos personas y varias filas a propósito: es lo que hace visible un N+1.
    """
    tenant = f"tenant-pl-{_uid()[:8]}"
    ws = Workspace(
        id=f"pl-ws-{_uid()[:8]}", slug=f"pl-ws-{_uid()[:8]}", name="Estación",
        tenant_id=tenant, workspace_type="organization",
    )
    autor = User(id=_uid(), email=f"{_uid()[:8]}@pl.local", name="Autor Viejo",
                 external_id=_uid())
    aprobador = User(id=_uid(), email=f"{_uid()[:8]}@pl.local", name="Aprob Viejo",
                     external_id=_uid())
    session.add_all([ws, autor, aprobador])
    session.flush()

    # Los endpoints exigen identidad + permiso por carpeta: el autor es admin
    # del workspace (bypass del permiso operativo, como en producción).
    session.add(WorkspaceMembership(
        id=_uid(), user_id=autor.id, workspace_id=ws.id, base_access="admin"
    ))
    session.flush()

    folder = Folder(id=f"pl-fol-{_uid()[:8]}", workspace_id=ws.id, name="root", path="root")
    session.add(folder)
    session.flush()

    doc = Document(
        id=f"pl-doc-{_uid()[:8]}", workspace_id=ws.id, folder_id=folder.id,
        name="Manual de playa", document_type="procedimiento", status="approved",
    )
    session.add(doc)
    session.flush()

    val_ok = Validation(
        id=_uid(), document_id=doc.id, validator_user_id=aprobador.id,
        status="approved", observations="", checklist_json="{}",
    )
    val_no = Validation(
        id=_uid(), document_id=doc.id, validator_user_id=autor.id,
        status="rejected", observations="Falta el paso 3", checklist_json="{}",
    )
    session.add_all([val_ok, val_no])
    session.flush()

    v1 = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=1, version_status="OBSOLETE",
        content_type="generated", content_json="{}", content_markdown="# v1",
        created_by=autor.id, approved_by=aprobador.id, approved_at=datetime.utcnow(),
        validation_id=val_ok.id, is_current=False,
    )
    v2 = DocumentVersion(
        id=_uid(), document_id=doc.id, version_number=2, version_status="APPROVED",
        content_type="generated", content_json="{}", content_markdown="# v2",
        created_by=autor.id, approved_by=aprobador.id, approved_at=datetime.utcnow(),
        rejected_by=autor.id, validation_id=val_no.id, is_current=True,
    )
    session.add_all([v1, v2])
    session.add(
        AuditLog(
            id=_uid(), document_id=doc.id, action="version.approved",
            entity_type="document_version", entity_id=v2.id, user_id=aprobador.id,
        )
    )
    session.commit()

    return SimpleNamespace(
        tenant=tenant, ws=ws, doc=doc, autor=autor, aprobador=aprobador,
        v1=v1, v2=v2,
    )


def _poblar_directorio(monkeypatch, esc, mapa: dict[User, str]) -> None:
    """Puebla el directorio por escritura al leer, con los nombres ACTUALES."""
    entradas = [
        {
            # Post-0022 el id canónico ES users.id: el join con el directorio es
            # directo y no hay puente por auth_user_id.
            "auth_user_id": f"auth-{u.id[:8]}",
            "user_id": u.id,
            "email": u.email,
            "first_name": None,
            "last_name": None,
            "display_name": nombre,
        }
        for u, nombre in mapa.items()
    ]
    monkeypatch.setattr(dir_mod, "_fetch_directorio", lambda tid, tok: entradas)
    set_request_identity("jwt", esc.tenant)


def _ctx(esc) -> SimpleNamespace:
    return SimpleNamespace(tenant=SimpleNamespace(id=esc.tenant))


@pytest.fixture
def rutas_con_sesion(monkeypatch, session, esc_ws_id):
    """Ambas rutas contra la sesión del test y el workspace del escenario."""
    @contextmanager
    def fake_db_session():
        yield session

    monkeypatch.setattr(versions_route, "get_db_session", fake_db_session)
    monkeypatch.setattr(validations_route, "get_db_session", fake_db_session)
    monkeypatch.setattr(
        versions_route, "resolve_tenant_workspace_id", lambda _ctx: esc_ws_id
    )
    monkeypatch.setattr(
        validations_route, "resolve_tenant_workspace_id", lambda _ctx: esc_ws_id
    )


@pytest.fixture
def esc_ws_id(escenario):
    return escenario.ws.id


# ── Versiones ────────────────────────────────────────────────────────────────


def test_versiones_traen_el_nombre_resuelto(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """Ningún uuid en los campos que la pantalla pinta."""
    _poblar_directorio(
        monkeypatch, escenario,
        {escenario.autor: "Ana Gómez", escenario.aprobador: "Beto Ruiz"},
    )

    filas = versions_route.get_document_versions(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )

    assert len(filas) == 2
    for fila in filas:
        assert fila["created_by_name"] == "Ana Gómez"
        assert fila["approved_by_name"] == "Beto Ruiz"
        # El uuid sigue viajando: es lo único persistido y lo que la UI usa
        # para comparar contra el usuario actual.
        assert fila["created_by"] == escenario.autor.id
    assert [f for f in filas if f["rejected_by"]][0]["rejected_by_name"] == "Ana Gómez"


def test_el_nombre_sigue_al_directorio_y_no_a_la_tabla_local(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """`users.name` quedó congelado en el primer login; el payload no.

    Es la prueba de que el nombre se resuelve al leer. Si estuviera guardado en
    una columna `*_name`, este test mostraría "Aprob Viejo".
    """
    assert escenario.aprobador.name == "Aprob Viejo"
    _poblar_directorio(
        monkeypatch, escenario,
        {escenario.autor: "Ana Gómez", escenario.aprobador: "Beto Ruiz Nuevo"},
    )

    filas = versions_route.get_document_versions(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )
    assert filas[0]["approved_by_name"] == "Beto Ruiz Nuevo"


def test_sin_directorio_cae_al_nombre_local_y_nunca_al_uuid(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """Workspace caído: se muestra lo que hay. Lo que NUNCA se muestra es el uuid."""
    filas = versions_route.get_document_versions(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )
    for fila in filas:
        assert fila["created_by_name"] == "Autor Viejo"
        assert fila["approved_by_name"] == "Aprob Viejo"
        assert escenario.autor.id not in fila["created_by_name"]


def test_versiones_resuelve_en_lote_sin_n_mas_1(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """Dos versiones × tres campos × dos personas ⇒ sigue siendo un lote fijo.

    El bug original era exactamente esto del lado del cliente: un `getUser()`
    por id. Traerlo al servidor sin resolver en lote no arreglaría nada.
    """
    _poblar_directorio(
        monkeypatch, escenario,
        {escenario.autor: "Ana Gómez", escenario.aprobador: "Beto Ruiz"},
    )

    from sqlalchemy import event

    engine = session.get_bind()
    queries: list[str] = []

    def registrar(conn, cursor, statement, params, ctx, many):
        # `\b(?!_)` para no contar `users_directory`: el refresh del directorio
        # hace sus propias queries y no son las que este test mide.
        if re.search(r"FROM process_ai\.users\b(?!_)", statement):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", registrar)
    try:
        versions_route.get_document_versions(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )
    finally:
        event.remove(engine, "before_cursor_execute", registrar)

    assert len(queries) == 1, (
        f"se hicieron {len(queries)} queries a users; se esperaba UNA en lote:\n"
        + "\n".join(queries)
    )


def test_audit_log_trae_el_nombre_del_actor(
    escenario, session, monkeypatch, rutas_con_sesion
):
    _poblar_directorio(monkeypatch, escenario, {escenario.aprobador: "Beto Ruiz"})
    filas = versions_route.get_document_audit_log(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )
    assert filas[0]["user_name"] == "Beto Ruiz"
    assert filas[0]["user_id"] == escenario.aprobador.id


# ── Validaciones ─────────────────────────────────────────────────────────────


def test_validaciones_traen_el_nombre_del_validador(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """Alimenta el historial de validaciones y la pantalla de corrección."""
    _poblar_directorio(
        monkeypatch, escenario,
        {escenario.autor: "Ana Gómez", escenario.aprobador: "Beto Ruiz"},
    )

    filas = validations_route.get_document_validations(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )

    nombres = {f.status: f.validator_user_name for f in filas}
    assert nombres["approved"] == "Beto Ruiz"
    assert nombres["rejected"] == "Ana Gómez"


def test_validacion_sin_validador_devuelve_vacio_no_uuid(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """Una validación pendiente no tiene validador. El campo va vacío: la
    pantalla decide el texto, y "" es más honesto que un uuid."""
    pendiente = Validation(
        id=_uid(), document_id=escenario.doc.id, validator_user_id=None,
        status="pending", observations="", checklist_json="{}",
    )
    session.add(pendiente)
    session.commit()

    filas = validations_route.get_document_validations(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )
    fila = next(f for f in filas if f.id == pendiente.id)
    assert fila.validator_user_name == ""


def test_validaciones_resuelve_en_lote_sin_n_mas_1(
    escenario, session, monkeypatch, rutas_con_sesion
):
    _poblar_directorio(
        monkeypatch, escenario,
        {escenario.autor: "Ana Gómez", escenario.aprobador: "Beto Ruiz"},
    )

    from sqlalchemy import event

    engine = session.get_bind()
    queries: list[str] = []

    def registrar(conn, cursor, statement, params, ctx, many):
        # `\b(?!_)` para no contar `users_directory`: el refresh del directorio
        # hace sus propias queries y no son las que este test mide.
        if re.search(r"FROM process_ai\.users\b(?!_)", statement):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", registrar)
    try:
        validations_route.get_document_validations(
            escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
        )
    finally:
        event.remove(engine, "before_cursor_execute", registrar)

    assert len(queries) == 1, (
        f"se hicieron {len(queries)} queries a users; se esperaba UNA en lote:\n"
        + "\n".join(queries)
    )


# ── El directorio no se filtra entre tenants ─────────────────────────────────


def test_no_se_resuelve_con_el_directorio_de_otro_tenant(
    escenario, session, monkeypatch, rutas_con_sesion
):
    """Una fila del directorio de otro tenant no puede nombrar a este usuario."""
    session.add(
        UserDirectory(
            tenant_id=f"otro-{escenario.tenant}",
            user_id=escenario.aprobador.id,
            email="intruso@otro.local",
            display_name="Nombre De Otro Tenant",
            status="active",
        )
    )
    session.commit()

    filas = versions_route.get_document_versions(
        escenario.doc.id, user_id=escenario.autor.id, ctx=_ctx(escenario)
    )
    assert filas[0]["approved_by_name"] == "Aprob Viejo"
