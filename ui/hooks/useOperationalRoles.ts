'use client'

import { useCallback, useEffect, useState } from 'react'
import { listOperationalRoles, type OperationalRoleResponse } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Roles operativos del workspace activo, cacheados en memoria (mismo patrón
 * que `useFolders`/`useWorkspaceMembers`): se piden UNA vez por workspace y se
 * reutilizan entre componentes (ej. el selector de aprobadores del wizard
 * necesita cruzar `operational_role_ids` de cada miembro con el
 * `access_level` de cada rol).
 *
 * `refresh()` invalida y vuelve a pedir.
 */
const cache = new Map<string, OperationalRoleResponse[]>()
const inflight = new Map<string, Promise<OperationalRoleResponse[]>>()

/** Invalida la cache de un workspace específico (llamar tras crear/editar/borrar un rol). */
export function invalidateOperationalRolesCache(workspaceId: string): void {
  cache.delete(workspaceId)
  inflight.delete(workspaceId)
}

function loadRoles(workspaceId: string): Promise<OperationalRoleResponse[]> {
  const cached = cache.get(workspaceId)
  if (cached) return Promise.resolve(cached)

  const existing = inflight.get(workspaceId)
  if (existing) return existing

  const promise = listOperationalRoles(workspaceId)
    .then((data) => {
      cache.set(workspaceId, data)
      inflight.delete(workspaceId)
      return data
    })
    .catch((err) => {
      inflight.delete(workspaceId)
      throw err
    })

  inflight.set(workspaceId, promise)
  return promise
}

export function useOperationalRoles(): {
  roles: OperationalRoleResponse[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
} {
  const { selectedWorkspaceId } = useWorkspace()
  const workspaceId = selectedWorkspaceId ?? ''

  const [roles, setRoles] = useState<OperationalRoleResponse[]>(() => cache.get(workspaceId) ?? [])
  const [loading, setLoading] = useState<boolean>(() => Boolean(workspaceId) && !cache.has(workspaceId))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workspaceId) return

    const cached = cache.get(workspaceId)
    if (cached) {
      setRoles(cached)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    loadRoles(workspaceId)
      .then((data) => {
        if (!cancelled) {
          setRoles(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Error al cargar roles operativos')
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [workspaceId])

  const refresh = useCallback(async () => {
    if (!workspaceId) return
    invalidateOperationalRolesCache(workspaceId)
    setLoading(true)
    setError(null)
    try {
      const data = await loadRoles(workspaceId)
      setRoles(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar roles operativos')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  return { roles, loading, error, refresh }
}
