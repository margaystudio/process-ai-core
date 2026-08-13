"""GET /workspaces/{id}/members/{mid}/effective-access — el visor del admin.

Convierte "¿por qué Juan no puede aprobar acá?" en una consulta: para un
miembro dado devuelve su acceso base, sus roles operativos con nivel, sus
permisos globales y, POR CARPETA, qué puede hacer, si la carpeta está
restringida, de qué ancestro hereda la lista y qué rol suyo se la abre.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
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

from api.routes import workspaces as workspaces_route

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
    """root (sin restricción) → restringida (corta herencia) → hija (hereda)."""
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(ws)
    session.flush()

    root = Folder(id=_uid(), workspace_id=ws.id, name="root", path="root",
                  inherits_permissions=True)
    restricted = Folder(id=_uid(), workspace_id=ws.id, name="Pista", path="Pista",
                        inherits_permissions=False)
    session.add_all([root, restricted])
    session.flush()
    child = Folder(id=_uid(), workspace_id=ws.id, name="Turnos", path="Pista/Turnos",
                   parent_id=restricted.id, inherits_permissions=True)
    session.add(child)
    session.flush()

    op = OperationalRole(id=_uid(), workspace_id=ws.id, name="Jefe de pista",
                         slug="jefe-pista", access_level="aprobacion")
    session.add(op)
    session.flush()
    session.add(FolderPermission(id=_uid(), folder_id=restricted.id,
                                 operational_role_id=op.id))
    session.commit()

    return SimpleNamespace(session=session, ws=ws, root=root,
                           restricted=restricted, child=child, op=op)


def _member(env, base_access, *, op_roles=()):
    u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
    env.session.add(u)
    env.session.flush()
    m = WorkspaceMembership(id=_uid(), user_id=u.id, workspace_id=env.ws.id,
                            base_access=base_access)
    env.session.add(m)
    env.session.flush()
    for op in op_roles:
        env.session.add(UserOperationalRole(
            id=_uid(), workspace_membership_id=m.id, operational_role_id=op.id,
        ))
    env.session.commit()
    return u, m


def _ctx(platform_roles=()):
    return SimpleNamespace(platform_roles=list(platform_roles))


def _call(env, *, caller, membership):
    return workspaces_route.get_member_effective_access(
        workspace_id=env.ws.id,
        membership_id=membership.id,
        user_id=caller.id,
        session=env.session,
        ctx=_ctx(),
    )


def test_solo_el_admin_puede_consultar(env):
    admin, _ = _member(env, "admin")
    member, m_member = _member(env, "member")

    # member no puede mirar el acceso de otros
    with pytest.raises(HTTPException) as exc:
        _call(env, caller=member, membership=m_member)
    assert exc.value.status_code == 403

    # admin sí
    out = _call(env, caller=admin, membership=m_member)
    assert out["base_access"] == "member"


def test_explica_el_acceso_por_carpeta(env):
    admin, _ = _member(env, "admin")
    _, m_jefe = _member(env, "member", op_roles=[env.op])
    _, m_raso = _member(env, "member")

    jefe = _call(env, caller=admin, membership=m_jefe)
    por_id = {f["id"]: f for f in jefe["folders"]}

    # root: sin restricción, entra por nivel base (sin rol que lo explique)
    assert por_id[env.root.id]["restricted"] is False
    assert por_id[env.root.id]["create"] is True
    assert por_id[env.root.id]["granted_by_role_ids"] == []

    # restringida: entra por su rol, con nivel aprobación
    assert por_id[env.restricted.id]["restricted"] is True
    assert por_id[env.restricted.id]["approve"] is True
    assert por_id[env.restricted.id]["granted_by_role_ids"] == [env.op.id]
    assert por_id[env.restricted.id]["source_folder_id"] == env.restricted.id

    # la hija hereda: misma lista, y el origen apunta al ancestro
    assert por_id[env.child.id]["restricted"] is True
    assert por_id[env.child.id]["source_folder_id"] == env.restricted.id
    assert por_id[env.child.id]["source_folder_name"] == "Pista"
    assert por_id[env.child.id]["approve"] is True

    # el miembro sin roles no entra a las restringidas, y el visor lo muestra
    raso = _call(env, caller=admin, membership=m_raso)
    por_id = {f["id"]: f for f in raso["folders"]}
    assert por_id[env.restricted.id]["view"] is False
    assert por_id[env.restricted.id]["granted_by_role_ids"] == []
    assert por_id[env.root.id]["create"] is True

    # los roles del miembro viajan con su nivel
    assert jefe["operational_roles"][0]["access_level"] == "aprobacion"
    assert raso["operational_roles"] == []


def test_membresia_de_otro_workspace_da_404(env):
    admin, _ = _member(env, "admin")
    otro_ws = Workspace(id=_uid(), slug=f"otro-{_uid()[:8]}", name="Otro",
                        workspace_type="organization")
    env.session.add(otro_ws)
    env.session.flush()
    u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="X")
    env.session.add(u)
    env.session.flush()
    ajena = WorkspaceMembership(id=_uid(), user_id=u.id, workspace_id=otro_ws.id,
                                base_access="member")
    env.session.add(ajena)
    env.session.commit()

    with pytest.raises(HTTPException) as exc:
        _call(env, caller=admin, membership=ajena)
    assert exc.value.status_code == 404
