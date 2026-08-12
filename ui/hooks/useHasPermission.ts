'use client'

import { useEffect, useState } from 'react'
import { getMyCapabilities, type MyCapabilities } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

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
  const { selectedWorkspaceId, activeTenantId } = useWorkspace()
  const [capabilities, setCapabilities] = useState<MyCapabilities | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getMyCapabilities()
      .then((data) => {
        if (!cancelled) setCapabilities(data)
      })
      .catch(() => {
        if (!cancelled) setCapabilities(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // Refetch al cambiar de workspace/tenant activo (el caché de 5s en lib/api
    // amortigua las llamadas duplicadas entre hooks montados en simultáneo).
  }, [selectedWorkspaceId, activeTenantId])

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
