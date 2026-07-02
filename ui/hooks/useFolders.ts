'use client'

import { useCallback, useEffect, useState } from 'react'
import { listFolders, type Folder } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Carpetas del workspace activo, cacheadas en memoria.
 *
 * Antes cada componente (y cada apertura del selector) refetcheaba `listFolders`,
 * lo que hacía que "Elegir" pegara al backend en cada click. Este hook carga las
 * carpetas UNA vez por workspace (al montar el consumidor → parte de la carga de
 * la pantalla) y las reutiliza; reabrir el selector o volver a un paso es instantáneo.
 *
 * `refresh()` invalida y vuelve a pedir (para cuando se conecte creación de carpetas).
 */
const cache = new Map<string, Folder[]>()
const inflight = new Map<string, Promise<Folder[]>>()

function loadFolders(workspaceId: string): Promise<Folder[]> {
  const cached = cache.get(workspaceId)
  if (cached) return Promise.resolve(cached)

  const existing = inflight.get(workspaceId)
  if (existing) return existing

  const promise = listFolders(workspaceId)
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

export function useFolders(): {
  folders: Folder[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
} {
  const { selectedWorkspaceId } = useWorkspace()
  const workspaceId = selectedWorkspaceId ?? ''

  const [folders, setFolders] = useState<Folder[]>(() => cache.get(workspaceId) ?? [])
  const [loading, setLoading] = useState<boolean>(() => Boolean(workspaceId) && !cache.has(workspaceId))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workspaceId) return

    const cached = cache.get(workspaceId)
    if (cached) {
      setFolders(cached)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    loadFolders(workspaceId)
      .then((data) => {
        if (!cancelled) {
          setFolders(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Error al cargar carpetas')
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
      const data = await loadFolders(workspaceId)
      setFolders(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar carpetas')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  return { folders, loading, error, refresh }
}
