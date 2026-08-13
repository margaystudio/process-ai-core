'use client'

import { useEffect, useState } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import type { WorkspaceResponse } from '@/lib/api'
import { isWorkspaceProfileIncomplete } from '@/lib/workspaceProfile'

/**
 * Usa datos del workspace ya cargados en WorkspaceContext (GET /users/me).
 * Evita un round-trip extra a GET /workspaces/{id} (~650 ms desde Uruguay).
 *
 * Solo se le pide a quien puede administrar el workspace (`canManageWorkspace`,
 * de `capabilities.can_manage_workspace`): completar el perfil es una acción
 * de administración, no algo que le compete a un miembro/cliente externo.
 */
export function useWorkspaceProfileIncomplete(
  workspace: WorkspaceResponse | null,
  canManageWorkspace: boolean,
  canManageWorkspaceLoading = false
): { incomplete: boolean; loading: boolean } {
  const { refreshWorkspaces } = useWorkspace()
  const [incomplete, setIncomplete] = useState(false)

  const shouldCheck = Boolean(workspace && canManageWorkspace)

  useEffect(() => {
    if (!shouldCheck || !workspace) {
      setIncomplete(false)
      return
    }

    setIncomplete(isWorkspaceProfileIncomplete(workspace))

    const onProfileUpdated = (e: Event) => {
      const detail = (e as CustomEvent<{ workspaceId?: string }>).detail
      if (!detail?.workspaceId || detail.workspaceId === workspace.id) {
        void refreshWorkspaces()
      }
    }
    window.addEventListener('workspaceProfileUpdated', onProfileUpdated)

    return () => {
      window.removeEventListener('workspaceProfileUpdated', onProfileUpdated)
    }
  }, [workspace, shouldCheck, refreshWorkspaces])

  return { incomplete: shouldCheck && incomplete, loading: canManageWorkspaceLoading }
}
