"""
Tests de caracterización de can_view_folder / can_create_in_folder /
can_approve_in_folder y de paridad con PermissionContext (evaluación bulk).

Modelo (fase 3): acceso base de la membership ('admin'|'member'|'external') +
roles operativos con nivel ('lectura'|'edicion'|'aprobacion') × carpetas.

Estructura: cada escenario verifica
  1. El comportamiento de la función original (caracterización — fija la
     semántica del modelo).
  2. Que PermissionContext devuelve EXACTAMENTE lo mismo (paridad).

Si un cambio futuro rompe la paridad, estos tests fallan: PermissionContext
debe replicar siempre la semántica de las funciones individuales.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event
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
from process_ai_core.db.permissions import (
    build_permission_context,
    can_approve_in_folder,
    can_create_in_folder,
    can_view_folder,
)

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


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    test_session = sessionmaker(bind=engine)()
    try:
        yield test_session
    finally:
        test_session.close()
        engine.dispose()


def _uid() -> str:
    return str(uuid.uuid4())


class Env:
    """Workspace con roles operativos de los tres niveles y carpetas de prueba."""

    def __init__(self, session):
        self.session = session
        self.workspace = Workspace(
            id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization"
        )
        session.add(self.workspace)

        # Rol legacy 'superadmin': lo único que queda de las tablas de roles
        # (fallback del superadmin por membership, pre-cleanup).
        self.legacy_superadmin_role = Role(id=_uid(), name="superadmin", is_system=True)
        session.add(self.legacy_superadmin_role)

        # Carpetas:
        #   root (hereda, sin permisos explícitos) → sin restricción
        #   restricted (inherits=False + permisos para op_edicion/op_aprobacion/op_lectura)
        #   child_of_restricted (hereda de restricted)
        #   empty_explicit (inherits=False, CERO filas) → quirk: sin restricción
        self.root = self._folder("root", parent=None, inherits=True)
        self.restricted = self._folder("restricted", parent=None, inherits=False)
        self.child_of_restricted = self._folder(
            "child", parent=self.restricted, inherits=True
        )
        self.empty_explicit = self._folder("empty-explicit", parent=None, inherits=False)

        # Roles operativos, uno por nivel + uno "equivocado" (sin acceso a restricted)
        self.op_lectura = self._op_role("Lector", "lectura")
        self.op_edicion = self._op_role("Pistero", "edicion")
        self.op_aprobacion = self._op_role("Gerencia", "aprobacion")
        self.op_otro = self._op_role("Otro", "edicion")

        for op in (self.op_lectura, self.op_edicion, self.op_aprobacion):
            session.add(
                FolderPermission(
                    id=_uid(),
                    folder_id=self.restricted.id,
                    operational_role_id=op.id,
                )
            )
        session.commit()

    def _folder(self, name, *, parent, inherits) -> Folder:
        f = Folder(
            id=_uid(),
            workspace_id=self.workspace.id,
            name=name,
            path=name,
            parent_id=parent.id if parent else None,
            inherits_permissions=inherits,
        )
        self.session.add(f)
        self.session.flush()
        return f

    def _op_role(self, name: str, level: str) -> OperationalRole:
        r = OperationalRole(
            id=_uid(),
            workspace_id=self.workspace.id,
            name=name,
            slug=name.lower(),
            access_level=level,
        )
        self.session.add(r)
        self.session.flush()
        return r

    def user_with(self, base_access: str | None, *, op_roles=()) -> User:
        """Crea usuario; base_access=None → sin membership en el workspace."""
        u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
        self.session.add(u)
        self.session.flush()
        if base_access is not None:
            m = WorkspaceMembership(
                id=_uid(),
                user_id=u.id,
                workspace_id=self.workspace.id,
                base_access=base_access,
            )
            self.session.add(m)
            self.session.flush()
            for op in op_roles:
                self.session.add(
                    UserOperationalRole(
                        id=_uid(),
                        workspace_membership_id=m.id,
                        operational_role_id=op.id,
                    )
                )
        self.session.commit()
        return u

    def legacy_superadmin(self) -> User:
        """Superadmin legacy: membership con rol superadmin en OTRO workspace."""
        other_ws = Workspace(
            id=_uid(), slug=f"sistema-{_uid()[:8]}", name="Sistema", workspace_type="organization"
        )
        self.session.add(other_ws)
        u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="SA")
        self.session.add(u)
        self.session.flush()
        self.session.add(
            WorkspaceMembership(
                id=_uid(),
                user_id=u.id,
                workspace_id=other_ws.id,
                base_access="admin",
                role_id=self.legacy_superadmin_role.id,
            )
        )
        self.session.commit()
        return u


@pytest.fixture
def env(session):
    return Env(session)


def _assert_parity(session, env, user, folder_id, *, platform_is_superadmin=False):
    """Compara las 3 funciones originales contra el contexto, y devuelve la tupla."""
    ctx = build_permission_context(
        session, user.id, env.workspace.id, platform_is_superadmin
    )
    results = {}
    for fn, method in (
        (can_view_folder, ctx.can_view_folder),
        (can_create_in_folder, ctx.can_create_in_folder),
        (can_approve_in_folder, ctx.can_approve_in_folder),
    ):
        original = fn(
            session, user.id, env.workspace.id, folder_id,
            platform_is_superadmin=platform_is_superadmin,
        )
        bulk = method(folder_id)
        assert bulk == original, (
            f"Paridad rota en {fn.__name__}(folder={folder_id}): "
            f"original={original} bulk={bulk}"
        )
        results[fn.__name__] = original
    return results


# --- Caracterización + paridad, escenario por escenario ---


def test_platform_superadmin_bypass(session, env):
    user = env.user_with(None)  # ni siquiera es miembro
    r = _assert_parity(session, env, user, env.restricted.id, platform_is_superadmin=True)
    assert r == {
        "can_view_folder": True,
        "can_create_in_folder": True,
        "can_approve_in_folder": True,
    }


def test_legacy_superadmin_membership_bypass(session, env):
    user = env.legacy_superadmin()  # membership superadmin en otro workspace
    r = _assert_parity(session, env, user, env.restricted.id)
    assert all(r.values())


def test_base_admin_bypass(session, env):
    user = env.user_with("admin")
    r = _assert_parity(session, env, user, env.restricted.id)
    assert all(r.values()), "el admin del workspace tiene bypass total"


def test_sin_membership_deniega(session, env):
    user = env.user_with(None)
    r = _assert_parity(session, env, user, env.root.id)
    assert not any(r.values())


def test_member_sin_roles_en_carpeta_sin_restriccion(session, env):
    """Nivel base del member = edición: crea/edita donde no hay restricción."""
    user = env.user_with("member")
    r = _assert_parity(session, env, user, env.root.id)
    assert r["can_view_folder"] is True
    assert r["can_create_in_folder"] is True
    assert r["can_approve_in_folder"] is False


def test_external_en_carpeta_sin_restriccion(session, env):
    """external = tope de solo lectura, siempre."""
    user = env.user_with("external")
    r = _assert_parity(session, env, user, env.root.id)
    assert r["can_view_folder"] is True
    assert r["can_create_in_folder"] is False
    assert r["can_approve_in_folder"] is False


def test_member_con_rol_aprobacion_aprueba_en_carpeta_sin_restriccion(session, env):
    """El nivel del rol operativo SUMA sobre el nivel base en zona sin restricción."""
    user = env.user_with("member", op_roles=[env.op_aprobacion])
    r = _assert_parity(session, env, user, env.root.id)
    assert all(r.values())


def test_carpeta_restringida_con_rol_de_edicion(session, env):
    user = env.user_with("member", op_roles=[env.op_edicion])
    r = _assert_parity(session, env, user, env.restricted.id)
    assert r["can_view_folder"] is True
    assert r["can_create_in_folder"] is True
    assert r["can_approve_in_folder"] is False  # su rol no llega a 'aprobacion'


def test_carpeta_restringida_con_rol_de_lectura(session, env):
    """Los niveles son acumulativos hacia abajo, nunca hacia arriba."""
    user = env.user_with("member", op_roles=[env.op_lectura])
    r = _assert_parity(session, env, user, env.restricted.id)
    assert r["can_view_folder"] is True
    assert r["can_create_in_folder"] is False
    assert r["can_approve_in_folder"] is False


def test_carpeta_restringida_con_rol_de_aprobacion(session, env):
    user = env.user_with("member", op_roles=[env.op_aprobacion])
    r = _assert_parity(session, env, user, env.restricted.id)
    assert all(r.values())


def test_carpeta_restringida_sin_rol_operativo(session, env):
    """El nivel base del member NO abre carpetas restringidas."""
    user = env.user_with("member")
    r = _assert_parity(session, env, user, env.restricted.id)
    assert not any(r.values())


def test_carpeta_restringida_rol_operativo_equivocado(session, env):
    user = env.user_with("member", op_roles=[env.op_otro])
    r = _assert_parity(session, env, user, env.restricted.id)
    assert not any(r.values())


def test_external_con_rol_de_aprobacion_sigue_siendo_solo_lectura(session, env):
    """El cap de external gana siempre, tenga el rol que tenga."""
    user = env.user_with("external", op_roles=[env.op_aprobacion])
    r = _assert_parity(session, env, user, env.restricted.id)
    assert r["can_view_folder"] is True
    assert r["can_create_in_folder"] is False
    assert r["can_approve_in_folder"] is False


def test_evaluacion_por_par_permiso_carpeta(session, env):
    """Aprueba en la carpeta de su rol de aprobación, solo lee en la del otro.

    Es lo que el modelo viejo no podía expresar: la capacidad va POR CARPETA,
    no global. Se arma una segunda carpeta restringida a op_otro (edición) y
    un usuario con op_aprobacion (→ restricted) + op_otro (→ otra).
    """
    otra = env._folder("otra-restringida", parent=None, inherits=False)
    env.session.add(
        FolderPermission(
            id=_uid(), folder_id=otra.id, operational_role_id=env.op_otro.id
        )
    )
    env.session.commit()

    user = env.user_with("member", op_roles=[env.op_aprobacion, env.op_otro])

    en_restricted = _assert_parity(session, env, user, env.restricted.id)
    assert en_restricted["can_approve_in_folder"] is True

    en_otra = _assert_parity(session, env, user, otra.id)
    assert en_otra["can_view_folder"] is True
    assert en_otra["can_create_in_folder"] is True
    assert en_otra["can_approve_in_folder"] is False  # op_otro es 'edicion'


def test_herencia_desde_ancestro_restringido(session, env):
    con_acceso = env.user_with("member", op_roles=[env.op_aprobacion])
    sin_acceso = env.user_with("member", op_roles=[env.op_otro])
    r1 = _assert_parity(session, env, con_acceso, env.child_of_restricted.id)
    r2 = _assert_parity(session, env, sin_acceso, env.child_of_restricted.id)
    assert r1["can_view_folder"] is True
    assert r1["can_approve_in_folder"] is True
    assert r2["can_view_folder"] is False


def test_rol_operativo_inactivo_no_cuenta(session, env):
    user = env.user_with("member", op_roles=[env.op_edicion])
    env.op_edicion.is_active = False
    env.session.commit()
    r = _assert_parity(session, env, user, env.restricted.id)
    assert not any(r.values())


def test_quirk_explicit_sin_filas_es_sin_restriccion(session, env):
    """inherits_permissions=False con CERO folder_permissions == sin restricción."""
    user = env.user_with("external")  # sin roles operativos
    r = _assert_parity(session, env, user, env.empty_explicit.id)
    assert r["can_view_folder"] is True


def test_folder_id_none_es_sin_restriccion(session, env):
    user = env.user_with("external")
    r = _assert_parity(session, env, user, None)
    assert r["can_view_folder"] is True


def test_folder_inexistente_es_sin_restriccion(session, env):
    user = env.user_with("external")
    r = _assert_parity(session, env, user, "no-existe")
    assert r["can_view_folder"] is True


def test_ciclo_en_jerarquia_es_sin_restriccion(session, env):
    """Ciclo padre↔hijo: el original corta con visited y devuelve set() → acceso."""
    a = env._folder("ciclo-a", parent=None, inherits=True)
    b = env._folder("ciclo-b", parent=a, inherits=True)
    a.parent_id = b.id
    session.commit()
    user = env.user_with("external")
    r = _assert_parity(session, env, user, a.id)
    assert r["can_view_folder"] is True


def test_carpeta_de_otro_workspace_camino_fallback(session, env):
    """get_folder_by_id no filtra por workspace: el contexto debe caer al camino
    por-item y dar el mismo resultado que el original."""
    other_ws = Workspace(
        id=_uid(), slug=f"otro-{_uid()[:8]}", name="Otro", workspace_type="organization"
    )
    session.add(other_ws)
    session.flush()
    foreign_restricted = Folder(
        id=_uid(),
        workspace_id=other_ws.id,
        name="foreign",
        path="foreign",
        parent_id=None,
        inherits_permissions=False,
    )
    session.add(foreign_restricted)
    session.flush()
    op_foreign = OperationalRole(
        id=_uid(), workspace_id=other_ws.id, name="F", slug="f"
    )
    session.add(op_foreign)
    session.flush()
    session.add(
        FolderPermission(
            id=_uid(),
            folder_id=foreign_restricted.id,
            operational_role_id=op_foreign.id,
        )
    )
    session.commit()
    user = env.user_with("member")
    r = _assert_parity(session, env, user, foreign_restricted.id)
    # restringida a un rol que el usuario no tiene → False (y paridad exacta)
    assert r["can_view_folder"] is False


# --- Conteo de queries: el contexto debe ser O(1) en carpetas evaluadas ---


def test_conteo_queries_bulk_es_constante(session, env):
    user = env.user_with("member", op_roles=[env.op_aprobacion])
    folders = [env._folder(f"extra-{i}", parent=None, inherits=True) for i in range(30)]
    session.commit()
    folder_ids = [f.id for f in folders] + [
        env.root.id,
        env.restricted.id,
        env.child_of_restricted.id,
    ]

    counter = {"n": 0}

    def _count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counter["n"] += 1

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", _count)
    try:
        counter["n"] = 0
        expected = [
            can_view_folder(session, user.id, env.workspace.id, fid)
            for fid in folder_ids
        ]
        n_original = counter["n"]

        counter["n"] = 0
        ctx = build_permission_context(session, user.id, env.workspace.id)
        got = [ctx.can_view_folder(fid) for fid in folder_ids]
        n_bulk = counter["n"]
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert got == expected
    assert n_bulk < n_original, (
        f"el contexto bulk ({n_bulk} queries) debería ejecutar menos SELECTs "
        f"que el camino por-item ({n_original})"
    )
