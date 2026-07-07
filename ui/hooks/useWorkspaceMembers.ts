'use client'

import { useCallback, useEffect, useState } from 'react'
import { getWorkspaceMembers, type WorkspaceMember } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Miembros del workspace activo, cacheados en memoria.
 *
 * El endpoint /members es caro (N+1 en el backend + round-trips al Postgres remoto),
 * así que antes cada entrada al Paso 3 lo refetcheaba y se sentía lento. Este hook lo
 * pide UNA vez por workspace y lo reutiliza. Además se puede `prefetchWorkspaceMembers`
 * al abrir el wizard para que el Paso 3 renderice instantáneo.
 *
 * `refresh()` invalida y vuelve a pedir.
 */
const cache = new Map<string, WorkspaceMember[]>()
const inflight = new Map<string, Promise<WorkspaceMember[]>>()

function loadMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  const cached = cache.get(workspaceId)
  if (cached) return Promise.resolve(cached)

  const existing = inflight.get(workspaceId)
  if (existing) return existing

  const promise = getWorkspaceMembers(workspaceId)
    .then(({ members }) => {
      cache.set(workspaceId, members)
      inflight.delete(workspaceId)
      return members
    })
    .catch((err) => {
      inflight.delete(workspaceId)
      throw err
    })

  inflight.set(workspaceId, promise)
  return promise
}

/** Dispara la carga (y el cacheo) sin montar el hook. Fire-and-forget. */
export function prefetchWorkspaceMembers(workspaceId: string | null | undefined): void {
  if (!workspaceId) return
  void loadMembers(workspaceId).catch(() => {
    /* el error real se maneja cuando un componente monta useWorkspaceMembers */
  })
}

export function useWorkspaceMembers(): {
  members: WorkspaceMember[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
} {
  const { selectedWorkspaceId } = useWorkspace()
  const workspaceId = selectedWorkspaceId ?? ''

  const [members, setMembers] = useState<WorkspaceMember[]>(() => cache.get(workspaceId) ?? [])
  const [loading, setLoading] = useState<boolean>(() => Boolean(workspaceId) && !cache.has(workspaceId))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workspaceId) return

    const cached = cache.get(workspaceId)
    if (cached) {
      setMembers(cached)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    loadMembers(workspaceId)
      .then((data) => {
        if (!cancelled) {
          setMembers(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Error al cargar miembros')
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [workspaceId])

  const refresh = useCallback(async () => {
    if (!workspaceId) return
    cache.delete(workspaceId)
    inflight.delete(workspaceId)
    setLoading(true)
    setError(null)
    try {
      const data = await loadMembers(workspaceId)
      setMembers(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar miembros')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  return { members, loading, error, refresh }
}
