'use client'

import { useCapabilities } from './useCapabilities'

/**
 * Verifica permisos contra las capacidades EFECTIVAS del backend
 * (GET /api/v1/users/me/capabilities) — la misma decisión que el backend va a
 * aplicar al autorizar cada request, incluido el bypass de superadmin.
 *
 * Ya no reimplementa una matriz de permisos por rol acá: esa matriz vivía
 * hardcodeada y se desincronizaba del backend (ej. admin nunca tuvo
 * documents.delete, pero el front igual mostraba el botón y el backend
 * respondía 403).
 *
 * Fail-closed: mientras `capabilities` no cargó, `hasPermission` es `false`.
 */
export function useHasPermission(permissionName: string): { hasPermission: boolean; loading: boolean } {
  const { capabilities, loading } = useCapabilities()

  const hasPermission = Boolean(
    capabilities && (capabilities.is_superadmin || capabilities.permissions.includes(permissionName))
  )

  return { hasPermission, loading }
}

export function useCanEditWorkspace() {
  return useHasPermission('workspaces.edit')
}

export function useCanManageUsers() {
  return useHasPermission('workspaces.manage_users')
}

export function useCanApproveDocuments() {
  return useHasPermission('documents.approve')
}

export function useCanRejectDocuments() {
  return useHasPermission('documents.reject')
}

/**
 * Gate de administración del workspace (settings, importación por lote,
 * relaciones globales, menú "Administración" del sidebar, etc.).
 * `capabilities.can_manage_workspace` ya resuelve el bypass de superadmin y
 * el acceso base 'admin' del workspace — no hay más roles de sistema que
 * comparar acá (reemplaza a `canAdministerWorkspace` de `lib/adminGating`).
 */
export function useCanManageWorkspace(): { canManage: boolean; loading: boolean } {
  const { capabilities, loading } = useCapabilities()
  return { canManage: Boolean(capabilities?.can_manage_workspace), loading }
}

/** Gate de personalización (branding) del workspace. */
export function useCanManageBranding(): { canManage: boolean; loading: boolean } {
  const { capabilities, loading } = useCapabilities()
  return { canManage: Boolean(capabilities?.can_manage_branding), loading }
}
