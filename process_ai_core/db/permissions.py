"""
Autorización de Process AI: dos capas, un solo objeto administrable.

Modelo (fase 3 del rediseño de permisos — ver docs/ROLES_OPERATIVOS_Y_PERMISOS_POR_CARPETA.md):

  1. **Acceso base** (`workspace_memberships.base_access`), derivado del rol
     macro del tenant en margay-workspace y escrito solo por el sync:
       - 'admin'    → gestión total + bypass del permiso por carpeta.
       - 'member'   → nivel "edición" en carpetas sin restricción.
       - 'external' → tope de SOLO LECTURA, tenga los roles que tenga.

  2. **Roles operativos** (`operational_roles`), definidos por el cliente:
     cada uno tiene un nivel de acceso (lectura/edicion/aprobacion) y un
     conjunto de carpetas (folder_permissions, con herencia). La evaluación es
     por par (permiso, carpeta): alcanza con que ALGÚN rol del usuario tenga
     el nivel necesario Y acceso a esa carpeta.

Los roles de sistema (owner/admin/approver/creator/viewer) se eliminaron; las
tablas roles/permissions quedan como legacy (solo el fallback del superadmin
por membership las consulta). La API por NOMBRE de permiso ("documents.view",
"documents.approve"…) se conserva: los niveles se expanden a esos nombres.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    Role, WorkspaceMembership,
    Folder, OperationalRole, UserOperationalRole, FolderPermission,
)
from .helpers import get_folder_by_id


# ── Niveles de acceso y su expansión a permisos ──────────────────────────────

#: Orden creciente de privilegio. Los niveles son ACUMULATIVOS.
ACCESS_LEVELS = ("lectura", "edicion", "aprobacion")

_LEVEL_GRANTS: dict[str, frozenset[str]] = {
    "lectura": frozenset({"documents.view", "documents.export", "workspaces.view"}),
    "edicion": frozenset({"documents.create", "documents.edit"}),
    "aprobacion": frozenset({"documents.approve", "documents.reject"}),
}

#: Catálogo completo (lo que recibe un admin/superadmin). Los nombres son los
#: mismos del seed histórico para no romper ningún call-site ni la UI.
ALL_PERMISSIONS = frozenset(
    {
        "documents.create", "documents.view", "documents.edit", "documents.delete",
        "documents.approve", "documents.reject", "documents.export",
        "workspaces.view", "workspaces.edit", "workspaces.manage_users",
        "workspaces.manage_folders", "users.view", "users.manage",
    }
)

#: Permisos que ningún nivel otorga: exclusivos del admin del workspace.
ADMIN_ONLY_PERMISSIONS = ALL_PERMISSIONS - frozenset().union(*_LEVEL_GRANTS.values())

#: Nivel base implícito de cada acceso (admin no está: es bypass total).
_BASE_LEVEL = {"member": "edicion", "external": "lectura"}

BASE_ACCESS_VALUES = ("admin", "member", "external")


def permissions_for_level(level: str | None) -> frozenset[str]:
    """Permisos efectivos de un nivel, acumulando los niveles inferiores."""
    if level not in ACCESS_LEVELS:
        return frozenset()
    granted: set[str] = set()
    for candidate in ACCESS_LEVELS:
        granted |= _LEVEL_GRANTS[candidate]
        if candidate == level:
            break
    return frozenset(granted)


_LECTURA_SET = permissions_for_level("lectura")


# ── Membership y superadmin ──────────────────────────────────────────────────

def get_membership_base_access(
    session: Session, user_id: str, workspace_id: str
) -> str | None:
    """'admin' | 'member' | 'external', o None si no es miembro del workspace."""
    row = (
        session.query(WorkspaceMembership.base_access)
        .filter_by(user_id=user_id, workspace_id=workspace_id)
        .first()
    )
    return row[0] if row else None


def _is_superadmin(
    session: Session,
    user_id: str,
    platform_is_superadmin: bool = False,
) -> bool:
    """
    True si el usuario es superadmin de plataforma.

    Orden de verificación:
      1. platform_is_superadmin=True → bypass inmediato por claim del contexto.
      2. Membership legacy con rol 'superadmin' (workspace 'sistema'). Se
         mantiene para compatibilidad hasta que corra cleanup_workspace_sistema.py.
    """
    if platform_is_superadmin:
        return True
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        return False
    return session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        role_id=superadmin_role.id,
    ).first() is not None


def is_workspace_admin(
    session: Session,
    user_id: str,
    workspace_id: str,
    platform_is_superadmin: bool = False,
) -> bool:
    """Admin del módulo en este workspace: superadmin o base_access='admin'."""
    if _is_superadmin(session, user_id, platform_is_superadmin):
        return True
    return get_membership_base_access(session, user_id, workspace_id) == "admin"


def _get_user_operational_levels(
    session: Session, user_id: str, workspace_id: str
) -> dict[str, str]:
    """{operational_role_id: access_level} de los roles ACTIVOS del usuario."""
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    if not membership:
        return {}
    rows = (
        session.query(OperationalRole.id, OperationalRole.access_level)
        .join(
            UserOperationalRole,
            UserOperationalRole.operational_role_id == OperationalRole.id,
        )
        .filter(
            UserOperationalRole.workspace_membership_id == membership.id,
            OperationalRole.is_active.is_(True),
        )
        .all()
    )
    return {rid: level for rid, level in rows}


def _effective_global_permissions(
    base_access: str, levels: dict[str, str]
) -> frozenset[str]:
    """
    Permisos efectivos SIN considerar carpetas: nivel base del acceso ∪ los
    niveles de todos los roles del usuario. El cap de external se aplica al
    final y gana siempre. Para 'admin' no se llama (bypass total).
    """
    effective: set[str] = set(permissions_for_level(_BASE_LEVEL.get(base_access)))
    for level in levels.values():
        effective |= permissions_for_level(level)
    if base_access == "external":
        effective &= _LECTURA_SET
    return frozenset(effective)


def has_permission(
    session: Session,
    user_id: str,
    workspace_id: str,
    permission_name: str,
    platform_is_superadmin: bool = False,
) -> bool:
    """
    Verifica un permiso GLOBAL al workspace (sin carpeta).

    Es deliberadamente laxo respecto de las carpetas: si el único derecho de
    aprobar del usuario viene de un rol operativo con carpetas restringidas,
    esto devuelve True y es can_approve_in_folder quien decide dónde. Los
    endpoints siempre combinan ambos.
    """
    if _is_superadmin(session, user_id, platform_is_superadmin):
        return True
    base = get_membership_base_access(session, user_id, workspace_id)
    if base is None:
        return False
    if base == "admin":
        return True
    if permission_name in ADMIN_ONLY_PERMISSIONS:
        return False
    levels = _get_user_operational_levels(session, user_id, workspace_id)
    return permission_name in _effective_global_permissions(base, levels)


# ── Permisos por carpeta ─────────────────────────────────────────────────────


def resolve_folder_permissions_source(
    session: Session, folder: "Folder | None"
) -> tuple[list[str], "Folder | None"]:
    """
    Resolución CANÓNICA de la herencia de permisos de una carpeta.

    Devuelve (ids de roles operativos efectivos, carpeta que los define).
    Sube por parent_id mientras inherits_permissions sea True; la primera
    carpeta con herencia cortada define la lista. Lista vacía == sin
    restricción (cualquier miembro con el permiso pasa), tanto para la raíz
    heredando como para una carpeta con herencia cortada y cero filas. Ciclo
    en la jerarquía → sin restricción.

    Única implementación con acceso a DB: la usan los checks por-ítem de este
    módulo y el GET/PUT de permisos de carpeta. PermissionContext replica esta
    semántica en memoria, con tests de paridad en tests/test_permission_context.py.
    """
    if not folder:
        return [], None
    visited: set[str] = set()
    current = folder
    while current:
        if current.id in visited:
            return [], None
        visited.add(current.id)
        if not getattr(current, "inherits_permissions", True):
            rows = (
                session.query(FolderPermission.operational_role_id)
                .filter_by(folder_id=current.id)
                .all()
            )
            return [r[0] for r in rows], current
        if current.parent_id:
            current = get_folder_by_id(session, current.parent_id)
        else:
            return [], None
    return [], None


def _get_folder_allowed_operational_role_ids(session: Session, folder_id: str) -> set[str]:
    """
    IDs de roles operativos que pueden acceder a la carpeta.
    Si inherits_permissions es True, sube al padre hasta encontrar permisos explícitos.
    Si la carpeta raíz hereda y no tiene permisos, se considera que no hay restricción (todos).
    """
    role_ids, _ = resolve_folder_permissions_source(
        session, get_folder_by_id(session, folder_id)
    )
    return set(role_ids)


def _can_in_folder_db(
    session: Session,
    user_id: str,
    workspace_id: str,
    folder_id: str,
    permission_name: str,
    platform_is_superadmin: bool,
) -> bool:
    """
    Evaluación por par (permiso, carpeta) — el cuerpo común de can_*_in_folder.

      - superadmin / base 'admin' → True.
      - external → solo permisos de lectura, siempre.
      - Carpeta SIN restricción → nivel base del acceso ∪ niveles de todos
        los roles del usuario.
      - Carpeta restringida → algún rol del usuario tiene que estar en la
        lista de la carpeta Y su nivel tiene que otorgar el permiso. El nivel
        base NO abre carpetas restringidas.
    """
    if _is_superadmin(session, user_id, platform_is_superadmin):
        return True
    base = get_membership_base_access(session, user_id, workspace_id)
    if base is None:
        return False
    if base == "admin":
        return True
    if base == "external" and permission_name not in _LECTURA_SET:
        return False

    levels = _get_user_operational_levels(session, user_id, workspace_id)
    allowed = _get_folder_allowed_operational_role_ids(session, folder_id)
    if not allowed:
        return permission_name in _effective_global_permissions(base, levels)
    return any(
        permission_name in permissions_for_level(levels[rid])
        for rid in levels.keys() & allowed
    )


def can_view_folder(
    session: Session,
    user_id: str,
    workspace_id: str,
    folder_id: str,
    platform_is_superadmin: bool = False,
) -> bool:
    """¿Puede VER los documentos de la carpeta?"""
    return _can_in_folder_db(
        session, user_id, workspace_id, folder_id, "documents.view", platform_is_superadmin
    )


def can_create_in_folder(
    session: Session,
    user_id: str,
    workspace_id: str,
    folder_id: str,
    platform_is_superadmin: bool = False,
) -> bool:
    """¿Puede CREAR/EDITAR documentos en la carpeta?"""
    return _can_in_folder_db(
        session, user_id, workspace_id, folder_id, "documents.create", platform_is_superadmin
    )


def can_approve_in_folder(
    session: Session,
    user_id: str,
    workspace_id: str,
    folder_id: str,
    platform_is_superadmin: bool = False,
) -> bool:
    """¿Puede APROBAR/RECHAZAR documentos de la carpeta?"""
    return _can_in_folder_db(
        session, user_id, workspace_id, folder_id, "documents.approve", platform_is_superadmin
    )


# ── Contexto de permisos precargado (evaluación bulk sin N+1) ────────────────


class PermissionContext:
    """
    Precarga en un número constante de queries (~6) todo lo necesario para
    evaluar can_view_folder / can_create_in_folder / can_approve_in_folder en
    memoria sobre N carpetas/documentos, en lugar de varias queries por item.

    Replica EXACTAMENTE la semántica de las funciones individuales de este
    módulo, que siguen siendo la fuente de verdad para chequeos de un solo
    item. Cualquier cambio de semántica debe hacerse primero en ellas y
    replicarse aquí (los tests de paridad en tests/test_permission_context.py
    lo verifican).

    Casos borde replicados a propósito:
      - Carpeta inexistente o folder_id=None → sin restricciones (acceso si
        tiene el permiso), igual que _get_folder_allowed_operational_role_ids.
      - Carpeta con inherits_permissions=False y cero filas en
        folder_permissions → sin restricciones (lista vacía == sin restricción).
      - Ciclo en la jerarquía → set() → sin restricciones.
      - Carpeta (o ancestro) fuera del workspace precargado: cae al camino
        por-item original, porque get_folder_by_id no filtra por workspace.
    """

    def __init__(
        self,
        session: Session,
        user_id: str,
        workspace_id: str,
        platform_is_superadmin: bool = False,
    ) -> None:
        self._session = session
        self.user_id = user_id
        self.workspace_id = workspace_id

        # 1) Superadmin: claim de plataforma o membership legacy (1 query).
        if platform_is_superadmin:
            self.is_superadmin = True
        else:
            self.is_superadmin = (
                session.query(WorkspaceMembership.id)
                .join(Role, Role.id == WorkspaceMembership.role_id)
                .filter(
                    WorkspaceMembership.user_id == user_id,
                    Role.name == "superadmin",
                    Role.is_system.is_(True),
                )
                .first()
                is not None
            )

        # 2) Membership → acceso base (1 query).
        membership = (
            session.query(WorkspaceMembership)
            .filter_by(user_id=user_id, workspace_id=workspace_id)
            .first()
        )
        self.base_access: str | None = membership.base_access if membership else None

        # 3) Roles operativos del usuario con su nivel (1 query).
        self.operational_levels: dict[str, str] = {}
        if membership:
            rows = (
                session.query(OperationalRole.id, OperationalRole.access_level)
                .join(
                    UserOperationalRole,
                    UserOperationalRole.operational_role_id == OperationalRole.id,
                )
                .filter(
                    UserOperationalRole.workspace_membership_id == membership.id,
                    OperationalRole.is_active.is_(True),
                )
                .all()
            )
            self.operational_levels = {rid: level for rid, level in rows}
        self.operational_role_ids: set[str] = set(self.operational_levels)

        # 4) Permisos globales efectivos (sin carpeta), para capabilities y
        #    para el caso "carpeta sin restricción".
        if self.is_superadmin or self.base_access == "admin":
            self.permission_names: frozenset[str] = ALL_PERMISSIONS
        elif self.base_access is None:
            self.permission_names = frozenset()
        else:
            self.permission_names = _effective_global_permissions(
                self.base_access, self.operational_levels
            )

        # 5) Jerarquía de carpetas del workspace (1 query).
        folder_rows = (
            session.query(Folder.id, Folder.parent_id, Folder.inherits_permissions)
            .filter_by(workspace_id=workspace_id)
            .all()
        )
        self._folders: dict[str, tuple[str | None, bool]] = {
            fid: (parent_id, True if inherits is None else bool(inherits))
            for fid, parent_id, inherits in folder_rows
        }

        # 6) Permisos por carpeta del workspace (1 query).
        perm_rows = (
            session.query(FolderPermission.folder_id, FolderPermission.operational_role_id)
            .join(Folder, Folder.id == FolderPermission.folder_id)
            .filter(Folder.workspace_id == workspace_id)
            .all()
        )
        self._folder_perms: dict[str, set[str]] = {}
        for fid, op_role_id in perm_rows:
            self._folder_perms.setdefault(fid, set()).add(op_role_id)

    def _folder_allowed_role_ids(self, folder_id: str | None) -> set[str]:
        """Réplica en memoria de _get_folder_allowed_operational_role_ids."""
        if folder_id not in self._folders:
            # None, inexistente o de otro workspace: camino por-item original
            # (mantiene semántica exacta; caso raro en la práctica).
            return _get_folder_allowed_operational_role_ids(self._session, folder_id)
        visited: set[str] = set()
        current: str | None = folder_id
        while current is not None:
            if current in visited:
                return set()
            visited.add(current)
            entry = self._folders.get(current)
            if entry is None:
                # Ancestro fuera del workspace precargado: camino original
                # desde la carpeta inicial (get_folder_by_id no filtra por ws).
                return _get_folder_allowed_operational_role_ids(self._session, folder_id)
            parent_id, inherits = entry
            if not inherits:
                return self._folder_perms.get(current, set())
            current = parent_id
        # Raíz heredando sin permisos explícitos: sin restricción
        return set()

    def _can_in_folder(self, permission_name: str, folder_id: str | None) -> bool:
        """Réplica en memoria de _can_in_folder_db."""
        if self.is_superadmin:
            return True
        if self.base_access is None:
            return False
        if self.base_access == "admin":
            return True
        if self.base_access == "external" and permission_name not in _LECTURA_SET:
            return False
        allowed = self._folder_allowed_role_ids(folder_id)
        if not allowed:
            return permission_name in self.permission_names
        return any(
            permission_name in permissions_for_level(self.operational_levels[rid])
            for rid in self.operational_levels.keys() & allowed
        )

    def can_view_folder(self, folder_id: str | None) -> bool:
        return self._can_in_folder("documents.view", folder_id)

    def can_create_in_folder(self, folder_id: str | None) -> bool:
        return self._can_in_folder("documents.create", folder_id)

    def can_approve_in_folder(self, folder_id: str | None) -> bool:
        return self._can_in_folder("documents.approve", folder_id)


def build_permission_context(
    session: Session,
    user_id: str,
    workspace_id: str,
    platform_is_superadmin: bool = False,
) -> PermissionContext:
    """
    Construye el contexto de permisos precargado para evaluar accesos a
    carpetas en memoria. Usar en listados (N items); para chequeos puntuales
    seguir usando can_view_folder / can_create_in_folder / can_approve_in_folder.
    """
    return PermissionContext(session, user_id, workspace_id, platform_is_superadmin)
