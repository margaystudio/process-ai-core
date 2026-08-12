"""GET /users/me/capabilities: los permisos efectivos que consume la UI.

El contrato que se fija acá es el que reemplaza a la matriz hardcodeada del
frontend (useHasPermission.ts): lo que diga este endpoint es lo que la UI
pinta, y tiene que coincidir EXACTAMENTE con lo que el backend después
permite o rechaza en cada endpoint. Los casos claves:

  - `permissions` son los del rol — un admin NO recibe documents.delete,
    que era la discrepancia que hacía aparecer el botón Eliminar y devolver
    403 al usarlo.
  - `folders` trae el acceso por carpeta YA resuelto (herencia incluida),
    con el bypass de owner/admin/superadmin aplicado.
  - superadmin de plataforma (claim) recibe el catálogo completo.
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
    Permission,
    Role,
    RolePermission,
    User,
    UserOperationalRole,
    Workspace,
    WorkspaceMembership,
)

from api.routes import users as users_route

TABLES = [
    Workspace.__table__,
    User.__table__,
    Role.__table__,
    Permission.__table__,
    RolePermission.__table__,
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
    """Workspace con roles reales del seed (matriz reducida) y dos carpetas."""
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(ws)

    perms = {}
    for name in (
        "documents.view",
        "documents.create",
        "documents.edit",
        "documents.delete",
        "documents.approve",
    ):
        p = Permission(id=_uid(), name=name, category="documents")
        perms[name] = p
        session.add(p)

    roles = {}
    matriz = {
        # espejo del seed: admin SIN documents.delete
        "owner": ["documents.view", "documents.create", "documents.edit",
                  "documents.delete", "documents.approve"],
        "admin": ["documents.view", "documents.create", "documents.edit",
                  "documents.approve"],
        "creator": ["documents.view", "documents.create", "documents.edit"],
        "viewer": ["documents.view"],
        "superadmin": [],
    }
    for name, perm_names in matriz.items():
        r = Role(id=_uid(), name=name, is_system=True)
        roles[name] = r
        session.add(r)
        session.flush()
        for pn in perm_names:
            session.add(RolePermission(role_id=r.id, permission_id=perms[pn].id))

    root = Folder(id=_uid(), workspace_id=ws.id, name="root", path="root",
                  inherits_permissions=True)
    restricted = Folder(id=_uid(), workspace_id=ws.id, name="restringida",
                        path="restringida", inherits_permissions=False)
    session.add_all([root, restricted])
    session.flush()

    op_role = OperationalRole(id=_uid(), workspace_id=ws.id, name="Pista", slug="pista")
    session.add(op_role)
    session.flush()
    session.add(FolderPermission(id=_uid(), folder_id=restricted.id,
                                 operational_role_id=op_role.id))
    session.commit()

    return SimpleNamespace(
        session=session, ws=ws, roles=roles, perms=perms,
        root=root, restricted=restricted, op_role=op_role,
    )


def _user(env, role_name, *, op_roles=()):
    u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
    env.session.add(u)
    env.session.flush()
    m = WorkspaceMembership(
        id=_uid(), user_id=u.id, workspace_id=env.ws.id,
        role_id=env.roles[role_name].id,
    )
    env.session.add(m)
    env.session.flush()
    for op in op_roles:
        env.session.add(UserOperationalRole(
            id=_uid(), workspace_membership_id=m.id, operational_role_id=op.id,
        ))
    env.session.commit()
    return u


def _ctx(env, platform_roles=()):
    return SimpleNamespace(
        tenant=SimpleNamespace(id="tenant-1"),
        platform_roles=list(platform_roles),
        tenant_roles=["tenant_member"],
    )


def _call(env, user, monkeypatch, platform_roles=()):
    monkeypatch.setattr(users_route, "resolve_tenant_workspace_id", lambda ctx: env.ws.id)
    return users_route.get_my_capabilities(
        ctx=_ctx(env, platform_roles), user_id=user.id, session=env.session
    )


def test_admin_no_recibe_documents_delete(env, monkeypatch):
    """La discrepancia que la matriz del front tenía mal: admin sin delete."""
    admin = _user(env, "admin")
    caps = _call(env, admin, monkeypatch)
    assert "documents.delete" not in caps["permissions"]
    assert "documents.approve" in caps["permissions"]
    assert caps["role"] == "admin"
    # Pero el acceso por CARPETA sí tiene bypass de admin:
    assert caps["folders"][env.restricted.id] == {
        "view": True, "create": True, "approve": True,
    }


def test_creator_con_rol_operativo_ve_solo_sus_carpetas(env, monkeypatch):
    con_acceso = _user(env, "creator", op_roles=[env.op_role])
    sin_acceso = _user(env, "creator")

    caps_ok = _call(env, con_acceso, monkeypatch)
    assert caps_ok["folders"][env.root.id]["create"] is True
    assert caps_ok["folders"][env.restricted.id]["create"] is True
    # creator no aprueba en ningún lado (no tiene documents.approve)
    assert caps_ok["folders"][env.restricted.id]["approve"] is False

    caps_no = _call(env, sin_acceso, monkeypatch)
    assert caps_no["folders"][env.root.id]["create"] is True  # sin restricción
    assert caps_no["folders"][env.restricted.id] == {
        "view": False, "create": False, "approve": False,
    }
    assert caps_no["operational_role_ids"] == []
    assert caps_ok["operational_role_ids"] == [env.op_role.id]


def test_viewer_solo_lectura_y_sin_gestion(env, monkeypatch):
    viewer = _user(env, "viewer")
    caps = _call(env, viewer, monkeypatch)
    assert caps["permissions"] == ["documents.view"]
    assert caps["can_manage_workspace"] is False
    assert caps["can_manage_branding"] is False
    assert caps["folders"][env.root.id] == {
        "view": True, "create": False, "approve": False,
    }


def test_superadmin_de_plataforma_recibe_el_catalogo_completo(env, monkeypatch):
    """El claim platform_roles alcanza: no hace falta membership superadmin local."""
    viewer = _user(env, "viewer")
    caps = _call(env, viewer, monkeypatch, platform_roles=["superadmin"])
    assert caps["is_superadmin"] is True
    assert set(caps["permissions"]) == set(env.perms.keys())
    assert caps["folders"][env.restricted.id] == {
        "view": True, "create": True, "approve": True,
    }
    assert caps["can_manage_workspace"] is True


def test_owner_gestiona_workspace_y_branding(env, monkeypatch):
    owner = _user(env, "owner")
    caps = _call(env, owner, monkeypatch)
    assert caps["can_manage_workspace"] is True
    assert caps["can_manage_branding"] is True
    assert "documents.delete" in caps["permissions"]
