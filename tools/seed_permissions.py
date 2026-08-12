"""
DEPRECATED — ya no hay nada que sembrar.

Este script creaba los roles de sistema (owner/admin/approver/creator/viewer/
superadmin), el catálogo de permisos y la matriz rol→permiso. Ese modelo se
eliminó en la fase 3 del rediseño de permisos:

  - El acceso base ('admin' | 'member' | 'external') vive en
    `workspace_memberships.base_access` y lo escribe el sync desde el rol
    macro del tenant en margay-workspace. No requiere seed.
  - Los permisos finos salen del nivel de acceso de los roles operativos
    (`operational_roles.access_level`: lectura/edicion/aprobacion), que se
    expanden a los nombres de permiso en process_ai_core/db/permissions.py.
    Tampoco requieren seed.

Las tablas roles/permissions/role_permissions quedan como legacy (solo el
fallback del superadmin por membership las consulta) hasta que corra
tools/cleanup_workspace_sistema.py.

`seed_permissions()` se conserva como no-op porque bootstrap_db.py y otros
scripts la importan; imprimir y no hacer nada es el comportamiento correcto
para cualquier entorno nuevo.
"""

import sys


def seed_permissions() -> None:
    print(
        "ℹ️  seed_permissions: no-op. Los roles de sistema se eliminaron; "
        "el acceso base viene de margay-workspace y los permisos finos de los "
        "roles operativos (ver process_ai_core/db/permissions.py)."
    )


if __name__ == "__main__":
    seed_permissions()
    sys.exit(0)
