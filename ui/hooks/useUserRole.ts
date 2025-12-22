'use client'

import { useState, useEffect } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { getUserRole } from '@/lib/api'
import { useUserId } from './useUserId'

/**
 * Hook para obtener el rol del usuario en el workspace seleccionado.
 * 
 * TODO: Obtener userId de autenticación cuando esté implementada.
 * Por ahora, usa un userId de localStorage.
 */
export function useUserRole() {
  const { selectedWorkspaceId } = useWorkspace()
  const userId = useUserId()
  const [role, setRole] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadRole() {
      if (!selectedWorkspaceId) {
        setRole(null)
        setLoading(false)
        return
      }

      if (!userId) {
        setError('Usuario no autenticado')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const result = await getUserRole(userId, selectedWorkspaceId)
        setRole(result.role)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
        setRole(null)
      } finally {
        setLoading(false)
      }
    }

    loadRole()
  }, [selectedWorkspaceId, userId])

  return { role, loading, error }
}

/**
 * Determina si el usuario es aprobador (puede aprobar documentos).
 */
export function useIsApprover() {
  const { role } = useUserRole()
  return role === 'owner' || role === 'admin' || role === 'approver'
}

/**
 * Determina si el usuario es creador.
 */
export function useIsCreator() {
  const { role } = useUserRole()
  return role === 'creator'
}

/**
 * Determina si el usuario es viewer.
 */
export function useIsViewer() {
  const { role } = useUserRole()
  return role === 'viewer'
}

