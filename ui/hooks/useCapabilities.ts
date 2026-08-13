'use client'

import { useEffect, useState } from 'react'
import { getMyCapabilities, type MyCapabilities } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Capacidades efectivas del usuario en el tenant activo
 * (GET /api/v1/users/me/capabilities). Fuente de verdad compartida por
 * `useHasPermission`, `useFolderAccess` y los hooks de gating de
 * administración (`useCanManageWorkspace`, `useCanManageBranding`):
 * un solo fetch (cacheado/deduplicado en `lib/api`), muchos consumidores.
 *
 * `capabilities` es `null` mientras carga o si falló — los hooks derivados
 * son fail-closed en ese caso.
 */
export function useCapabilities(): { capabilities: MyCapabilities | null; loading: boolean } {
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

  return { capabilities, loading }
}
