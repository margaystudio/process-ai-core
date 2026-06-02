'use client'

import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Devuelve el rol del usuario en el workspace seleccionado.
 * El rol viene directo del WorkspaceContext (GET /api/v1/users/me),
 * sin llamadas adicionales al backend.
 */
export function useUserRole() {
  const { selectedWorkspace, loading } = useWorkspace()
  const role = selectedWorkspace?.role ?? null

  return { role, loading, error: null }
}

export function useIsApprover() {
  const { role } = useUserRole()
  return role === 'owner' || role === 'admin' || role === 'approver'
}

export function useIsCreator() {
  const { role } = useUserRole()
  return role === 'creator'
}

export function useIsViewer() {
  const { role } = useUserRole()
  return role === 'viewer'
}
