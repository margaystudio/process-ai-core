"""GET /users/me/capabilities: los permisos efectivos que consume la UI.

El contrato que se fija acá es el que reemplaza a la matriz hardcodeada del
frontend: lo que diga este endpoint es lo que la UI pinta, y tiene que
coincidir EXACTAMENTE con lo que el backend después permite o rechaza.

Modelo (fase 3): acceso base ('admin'|'member'|'external') + roles operativos
con nivel ('lectura'|'edicion'|'aprobacion') × carpetas.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.models import (
    Folder,
    FolderPermission,
    OperationalRole,
    User,
    UserOperationalRole,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.db.permissions import ALL_PERMISSIONS

from api.routes import users as users_route

TABLES = [
    Workspace.__table__,
    User.__table__,
    WorkspaceMembership.__table__,
    Folder.__table__,
    OperationalRole.__table__,
    UserOperationalRole.__table__,
    FolderPermission.__table__,
]


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def env(session):
    """Workspace con dos carpetas (una restringida) y roles de dos niveles."""
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(ws)
    session.flush()

    root = Folder(id=_uid(), workspace_id=ws.id, name="root", path="root",
                  inherits_permissions=True)
    restricted = Folder(id=_uid(), workspace_id=ws.id, name="restringida",
                        path="restringida", inherits_permissions=False)
    session.add_all([root, restricted])
    session.flush()

    op_edicion = OperationalRole(
        id=_uid(), workspace_id=ws.id, name="Pista", slug="pista", access_level="edicion"
    )
    op_aprobacion = OperationalRole(
        id=_uid(), workspace_id=ws.id, name="Gerencia", slug="gerencia",
        access_level="aprobacion",
    )
    session.add_all([op_edicion, op_aprobacion])
    session.flush()
    for op in (op_edicion, op_aprobacion):
        session.add(FolderPermission(id=_uid(), folder_id=restricted.id,
                                     operational_role_id=op.id))
    session.commit()

    return SimpleNamespace(
        session=session, ws=ws, root=root, restricted=restricted,
        op_edicion=op_edicion, op_aprobacion=op_aprobacion,
    )


def _user(env, base_access, *, op_roles=()):
    u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
    env.session.add(u)
    env.session.flush()
    m = WorkspaceMembership(
        id=_uid(), user_id=u.id, workspace_id=env.ws.id, base_access=base_access,
    )
    env.session.add(m)
    env.session.flush()
    for op in op_roles:
        env.session.add(UserOperationalRole(
            id=_uid(), workspace_membership_id=m.id, operational_role_id=op.id,
        ))
    env.session.commit()
    return u


def _ctx(platform_roles=()):
    return SimpleNamespace(
        tenant=SimpleNamespace(id="tenant-1"),
        platform_roles=list(platform_roles),
        tenant_roles=["tenant_member"],
    )


def _call(env, user, monkeypatch, platform_roles=()):
    monkeypatch.setattr(users_route, "resolve_tenant_workspace_id", lambda ctx: env.ws.id)
    return users_route.get_my_capabilities(
        ctx=_ctx(platform_roles), user_id=user.id, session=env.session
    )


def test_admin_recibe_catalogo_completo_y_bypass_por_carpeta(env, monkeypatch):
    admin = _user(env, "admin")
    caps = _call(env, admin, monkeypatch)
    assert caps["role"] == "admin"
    assert set(caps["permissions"]) == set(ALL_PERMISSIONS)
    assert caps["can_manage_workspace"] is True
    assert caps["can_manage_branding"] is True
    assert caps["folders"][env.restricted.id] == {
        "view": True, "create": True, "approve": True,
    }


def test_member_con_rol_operativo_ve_solo_sus_carpetas(env, monkeypatch):
    con_acceso = _user(env, "member", op_roles=[env.op_edicion])
    sin_acceso = _user(env, "member")

    caps_ok = _call(env, con_acceso, monkeypatch)
    assert caps_ok["folders"][env.root.id]["create"] is True
    assert caps_ok["folders"][env.restricted.id]["create"] is True
    # su rol es de edición: no aprueba en ningún lado
    assert caps_ok["folders"][env.restricted.id]["approve"] is False
    assert caps_ok["operational_role_ids"] == [env.op_edicion.id]

    caps_no = _call(env, sin_acceso, monkeypatch)
    assert caps_no["folders"][env.root.id]["create"] is True  # base edición
    assert caps_no["folders"][env.restricted.id] == {
        "view": False, "create": False, "approve": False,
    }
    assert caps_no["operational_role_ids"] == []


def test_member_con_rol_de_aprobacion_aprueba(env, monkeypatch):
    aprobador = _user(env, "member", op_roles=[env.op_aprobacion])
    caps = _call(env, aprobador, monkeypatch)
    assert "documents.approve" in caps["permissions"]
    assert caps["folders"][env.restricted.id]["approve"] is True
    # y no gestiona el workspace por eso
    assert caps["can_manage_workspace"] is False


def test_external_solo_lectura_y_sin_gestion(env, monkeypatch):
    externo = _user(env, "external", op_roles=[env.op_aprobacion])
    caps = _call(env, externo, monkeypatch)
    assert caps["role"] == "external"
    # el cap de external gana aunque su rol operativo sea de aprobación
    assert "documents.approve" not in caps["permissions"]
    assert "documents.create" not in caps["permissions"]
    assert "documents.view" in caps["permissions"]
    assert caps["can_manage_workspace"] is False
    assert caps["folders"][env.restricted.id] == {
        "view": True, "create": False, "approve": False,
    }


def test_superadmin_de_plataforma_recibe_el_catalogo_completo(env, monkeypatch):
    """El claim platform_roles alcanza: no hace falta membership admin local."""
    externo = _user(env, "external")
    caps = _call(env, externo, monkeypatch, platform_roles=["superadmin"])
    assert caps["is_superadmin"] is True
    assert set(caps["permissions"]) == set(ALL_PERMISSIONS)
    assert caps["folders"][env.restricted.id] == {
        "view": True, "create": True, "approve": True,
    }
    assert caps["can_manage_workspace"] is True
