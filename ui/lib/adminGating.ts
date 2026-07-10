/**
 * Helper canónico de gating por administración de workspace.
 *
 * Unifica la condición dispersa en dos lugares del codebase:
 *   - settings/page.tsx:  isSuperadmin || canEditWorkspace || role === 'owner'|'admin'
 *   - workspace/page.tsx: platformRoles.includes('superadmin') || role === 'owner'|'creator'|'admin'
 *
 * Semántica:
 *  - "superadmin" (platformRoles o flag `isSuperadmin`) → acceso total en cualquier workspace.
 *  - "owner" → dueño del workspace.
 *  - "creator" → quien creó el workspace; tratado igual que admin en workspace/page.
 *  - "admin" → administrador del workspace.
 *  - `canEditWorkspace` → permiso granular (e.g. workspace.edit) que puede
 *    otorgarse independientemente del rol (settings/page lo usa).
 *
 * Los call-sites existentes NO se modifican con este helper (los unificará
 * el junior en tickets separados para no introducir cambios de comportamiento
 * en ramas en vuelo).
 */
export interface AdminGatingInput {
  /** Roles de plataforma (e.g. ['superadmin']). Opcional: si se omite, solo se evalúa `isSuperadmin`. */
  platformRoles?: string[];
  /** Flag explícito de superadmin (alias para no tener que pasar platformRoles). */
  isSuperadmin?: boolean;
  /** Rol del usuario en el workspace ('owner' | 'creator' | 'admin' | 'member' | 'viewer' | string). */
  workspaceRole?: string | null;
  /** Permiso granular workspace.edit (puede provenir de una política de permisos). */
  canEditWorkspace?: boolean;
}

/**
 * Devuelve `true` si el usuario tiene permisos de administración sobre el workspace.
 *
 * Verdadero si se cumple al menos UNA de:
 *   1. Es superadmin (vía platformRoles o isSuperadmin).
 *   2. Tiene el permiso granular `canEditWorkspace`.
 *   3. Su rol en el workspace es 'owner', 'creator' o 'admin'.
 */
export function canAdministerWorkspace({
  platformRoles,
  isSuperadmin,
  workspaceRole,
  canEditWorkspace,
}: AdminGatingInput): boolean {
  const superadmin =
    isSuperadmin === true ||
    (Array.isArray(platformRoles) && platformRoles.includes("superadmin"));

  if (superadmin) return true;
  if (canEditWorkspace === true) return true;

  const adminRoles = ["owner", "creator", "admin"] as const;
  if (workspaceRole && (adminRoles as readonly string[]).includes(workspaceRole)) return true;

  return false;
}
