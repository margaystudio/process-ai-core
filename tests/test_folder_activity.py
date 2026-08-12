import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text as sa_text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.models.requests import FolderUpdateRequest
from api.routes import folders as folders_route
from process_ai_core.db.database import Base
from process_ai_core.db.models import AuditLog, Folder, User, Workspace


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine)()
    try:
        yield test_session
    finally:
        test_session.close()
        engine.dispose()


def _workspace_folder(session, suffix: str) -> tuple[Workspace, Folder]:
    workspace = Workspace(
        id=f"activity-ws-{suffix}",
        slug=f"activity-ws-{suffix}",
        name=f"Workspace {suffix}",
        workspace_type="organization",
    )
    folder = Folder(
        id=f"activity-folder-{suffix}",
        workspace_id=workspace.id,
        name=f"Carpeta {suffix}",
        path=f"Carpeta {suffix}",
    )
    session.add_all([workspace, folder])
    session.flush()
    return workspace, folder


def test_folder_activity_isolated_by_workspace(session, monkeypatch):
    suffix = str(uuid.uuid4())[:8]
    workspace_a, folder_a = _workspace_folder(session, f"a-{suffix}")
    workspace_b, folder_b = _workspace_folder(session, f"b-{suffix}")
    actor = User(
        id=f"activity-user-{suffix}",
        email=f"activity-{suffix}@example.com",
        name="Ana Auditora",
    )
    session.add(actor)
    session.flush()
    session.add_all(
        [
            AuditLog(
                folder_id=folder_a.id,
                document_id=None,
                user_id=actor.id,
                action="folder.updated",
                entity_type="folder",
                entity_id=folder_a.id,
            ),
            AuditLog(
                folder_id=folder_b.id,
                document_id=None,
                user_id=actor.id,
                action="folder.permissions_updated",
                entity_type="folder",
                entity_id=folder_b.id,
            ),
        ]
    )
    session.commit()

    monkeypatch.setattr(
        folders_route,
        "resolve_tenant_workspace_id",
        lambda _ctx: workspace_a.id,
    )
    monkeypatch.setattr(folders_route, "_require_workspace_member", lambda *_args: None)
    monkeypatch.setattr(folders_route, "can_view_folder", lambda *_args: True)

    response = folders_route.get_folder_activity(
        folder_id=folder_a.id,
        page=1,
        page_size=20,
        user_id=actor.id,
        session=session,
        ctx=None,
    )

    assert response["total"] == 1
    assert response["items"][0]["action"] == "folder.updated"
    assert response["items"][0]["actor"]["name"] == "Ana Auditora"

    with pytest.raises(HTTPException) as exc:
        folders_route.get_folder_activity(
            folder_id=folder_b.id,
            page=1,
            page_size=20,
            user_id=actor.id,
            session=session,
            ctx=None,
        )
    assert exc.value.status_code == 404


def test_folder_activity_requiere_permiso_de_carpeta(session, monkeypatch):
    """
    Ser del workspace no alcanza: la actividad expone quién hizo qué sobre la
    carpeta, así que respeta el mismo permiso de lectura que la carpeta misma.

    El test anterior cubre el aislamiento entre workspaces (404) pero
    monkeypatchea `can_view_folder` en True, así que el 403 —el caso de un
    miembro legítimo del workspace sin permiso sobre ESTA carpeta— quedaba sin
    ejercitar en un endpoint que devuelve auditoría.
    """
    suffix = str(uuid.uuid4())[:8]
    workspace, folder = _workspace_folder(session, f"perm-{suffix}")
    intruso = User(
        id=f"activity-intruso-{suffix}",
        email=f"intruso-{suffix}@example.com",
        name="Sin Permiso",
    )
    session.add(intruso)
    session.add(
        AuditLog(
            folder_id=folder.id,
            document_id=None,
            user_id=intruso.id,
            action="folder.updated",
            entity_type="folder",
            entity_id=folder.id,
        )
    )
    session.commit()

    monkeypatch.setattr(
        folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id
    )
    monkeypatch.setattr(folders_route, "_require_workspace_member", lambda *_args: None)
    monkeypatch.setattr(folders_route, "can_view_folder", lambda *_args: False)

    with pytest.raises(HTTPException) as exc:
        folders_route.get_folder_activity(
            folder_id=folder.id,
            page=1,
            page_size=20,
            user_id=intruso.id,
            session=session,
            ctx=None,
        )
    assert exc.value.status_code == 403


def test_el_orden_de_la_actividad_es_total(session, monkeypatch):
    """
    `created_at` lo pone Python (datetime.utcnow), así que un lote puede escribir
    varias filas con el mismo instante. Con el orden ambiguo, LIMIT/OFFSET puede
    repetir o saltear filas entre páginas: la página 2 deja de ser el complemento
    de la 1.

    Se afirma sobre el SQL emitido y no sobre las filas devueltas a propósito:
    con empate, el orden que sale sin desempate es el que se le cante al motor.
    SQLite devuelve las filas por rowid y una prueba de caja negra pasaría con y
    sin el arreglo — o sea, no probaría nada. Lo que hay que fijar es que el
    ORDER BY incluya una columna única.
    """
    from sqlalchemy import event

    suffix = str(uuid.uuid4())[:8]
    workspace, folder = _workspace_folder(session, f"orden-{suffix}")
    session.commit()

    monkeypatch.setattr(
        folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id
    )
    monkeypatch.setattr(folders_route, "_require_workspace_member", lambda *_args: None)
    monkeypatch.setattr(folders_route, "can_view_folder", lambda *_args: True)

    emitidas: list[str] = []

    @event.listens_for(session.bind, "before_cursor_execute")
    def _capturar(conn, cursor, statement, parameters, context, executemany):
        emitidas.append(statement)

    try:
        folders_route.get_folder_activity(
            folder_id=folder.id,
            page=1,
            page_size=20,
            user_id=None,
            session=session,
            ctx=None,
        )
    finally:
        event.remove(session.bind, "before_cursor_execute", _capturar)

    con_orden = [s for s in emitidas if "ORDER BY" in s.upper()]
    assert con_orden, "la consulta de actividad salió sin ORDER BY"
    order_by = con_orden[-1].upper().split("ORDER BY")[1]
    assert "CREATED_AT" in order_by
    assert "AUDIT_LOGS.ID" in order_by, (
        "el ORDER BY no desempata por una columna única: con created_at repetido "
        "la paginación puede repetir o saltear filas"
    )


def test_el_borrado_de_carpeta_queda_auditado(session, monkeypatch):
    """
    Borrar era la única de las cuatro acciones de carpeta que no dejaba rastro —
    y es la más auditable de todas.

    El evento se escribe ANTES del borrado (la FK tiene que resolver) y el
    `ondelete="SET NULL"` le deja el folder_id nulo después, así que la fila
    sobrevive pero deja de pertenecer a una carpeta. Por eso el nombre viaja en
    el metadata: sin la fila de folders, `entity_id` solo es un uuid.
    """
    import json

    suffix = str(uuid.uuid4())[:8]
    workspace, folder = _workspace_folder(session, f"del-{suffix}")
    actor = User(
        id=f"activity-borra-{suffix}",
        email=f"borra-{suffix}@example.com",
        name="Bruno Borrador",
    )
    session.add(actor)
    session.commit()

    monkeypatch.setattr(
        folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id
    )
    monkeypatch.setattr(folders_route, "_require_workspace_member", lambda *_args: None)
    monkeypatch.setattr(folders_route, "can_create_in_folder", lambda *_args: True)

    folders_route.delete_folder_endpoint(
        folder_id=folder.id,
        move_documents_to=None,
        user_id=actor.id,
        session=session,
        ctx=None,
    )
    session.commit()

    evento = (
        session.query(AuditLog).filter(AuditLog.action == "folder.deleted").one()
    )
    assert evento.entity_id == folder.id
    assert evento.user_id == actor.id
    assert json.loads(evento.metadata_json)["name"] == folder.name


# ── Criterio de aborto de la auditoría (gobernanza vs. organizativo) ─────────
#
# La auditoría corre dentro de la transacción del endpoint, así que un fallo al
# auditar puede tumbar la operación de negocio. Eso NO es una decisión uniforme:
# para un hecho de gobernanza el registro es el valor de la operación, y para uno
# organizativo convertir el audit log en punto único de falla significa que nadie
# puede ordenar su biblioteca si el logging tiene un problema.
#
# Los tests rompen la auditoría a propósito (un user_id que no existe viola la FK
# audit_logs.user_id -> users.id) y miran qué pasa con la operación.

_USUARIO_FANTASMA = "no-existe-en-users"


@pytest.fixture
def session_con_fk(session):
    """SQLite ignora las FK salvo que se le pidan; sin esto no hay nada que romper."""
    session.execute(sa_text("PRAGMA foreign_keys=ON"))
    return session


def test_renombrar_una_carpeta_sobrevive_a_una_auditoria_rota(session_con_fk, monkeypatch):
    """
    Organizativo: no aborta. Una carpeta renombrada sin registrar no debilita
    ninguna afirmación de gobernanza del sistema.
    """
    session = session_con_fk
    suffix = str(uuid.uuid4())[:8]
    workspace, folder = _workspace_folder(session, f"org-{suffix}")
    session.commit()

    monkeypatch.setattr(
        folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id
    )
    monkeypatch.setattr(
        folders_route, "get_membership_base_access", lambda *_a, **_k: "admin"
    )
    monkeypatch.setattr(folders_route, "is_workspace_admin", lambda *_a, **_k: True)
    monkeypatch.setattr(folders_route, "can_create_in_folder", lambda *_a, **_k: True)

    folders_route.update_folder_endpoint(
        folder_id=folder.id,
        request=FolderUpdateRequest(name="Nombre nuevo"),
        user_id=_USUARIO_FANTASMA,
        session=session,
        ctx=None,
    )
    session.commit()

    session.refresh(folder)
    assert folder.name == "Nombre nuevo", "el renombrado se perdió por un fallo de auditoría"
    assert session.query(AuditLog).filter_by(action="folder.updated").count() == 0


def test_borrar_una_carpeta_no_sobrevive_a_una_auditoria_rota(session_con_fk, monkeypatch):
    """
    Gobernanza: aborta. Borrar es irreversible; sin registro no queda ni rastro
    de que la carpeta existió, así que si no se puede auditar, no se borra.
    """
    session = session_con_fk
    suffix = str(uuid.uuid4())[:8]
    workspace, folder = _workspace_folder(session, f"gob-{suffix}")
    session.commit()
    nombre_original = folder.name

    monkeypatch.setattr(
        folders_route, "resolve_tenant_workspace_id", lambda _ctx: workspace.id
    )
    monkeypatch.setattr(folders_route, "_require_workspace_member", lambda *_args: None)
    monkeypatch.setattr(folders_route, "can_create_in_folder", lambda *_a, **_k: True)

    with pytest.raises(HTTPException) as exc:
        folders_route.delete_folder_endpoint(
            folder_id=folder.id,
            move_documents_to=None,
            user_id=_USUARIO_FANTASMA,
            session=session,
            ctx=None,
        )
    assert exc.value.status_code == 500

    session.rollback()
    sobreviviente = session.get(Folder, folder.id)
    assert sobreviviente is not None, "la carpeta se borró sin dejar registro"
    assert sobreviviente.name == nombre_original
