'use client'

import { useEffect, useState } from 'react'
import { getWorkspace } from '@/lib/api'
import {
  isWorkspaceProfileIncomplete,
  shouldPromptWorkspaceProfile,
} from '@/lib/workspaceProfile'

export function useWorkspaceProfileIncomplete(
  workspaceId: string | null,
  role: string | null,
  platformRoles: string[] = []
): { incomplete: boolean; loading: boolean } {
  const [incomplete, setIncomplete] = useState(false)
  const [loading, setLoading] = useState(false)

  const shouldCheck = Boolean(
    workspaceId && shouldPromptWorkspaceProfile(role, platformRoles)
  )

  useEffect(() => {
    if (!shouldCheck || !workspaceId) {
      setIncomplete(false)
      setLoading(false)
      return
    }

    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const ws = await getWorkspace(workspaceId)
        if (!cancelled) {
          setIncomplete(isWorkspaceProfileIncomplete(ws))
        }
      } catch {
        if (!cancelled) setIncomplete(false)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()

    const onProfileUpdated = (e: Event) => {
      const detail = (e as CustomEvent<{ workspaceId?: string }>).detail
      if (!detail?.workspaceId || detail.workspaceId === workspaceId) {
        load()
      }
    }
    window.addEventListener('workspaceProfileUpdated', onProfileUpdated)

    return () => {
      cancelled = true
      window.removeEventListener('workspaceProfileUpdated', onProfileUpdated)
    }
  }, [workspaceId, shouldCheck])

  return { incomplete: shouldCheck && incomplete, loading }
}
