'use client'

import { useState, useEffect } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { getUserRole } from '@/lib/api'

/**
 * Hook para obtener el rol del usuario en el workspace seleccionado.
 * 
 * TODO: Obtener userId de autenticación cuando esté implementada.
 * Por ahora, usa un userId hardcodeado o de localStorage.
 */
export function useUserRole() {
  const { selectedWorkspaceId } = useWorkspace()
  const [role, setRole] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // TODO: Obtener userId de autenticación
  // Por ahora, usar un userId de prueba o de localStorage
  const getUserId = (): string | null => {
    // Intentar obtener de localStorage (para desarrollo)
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('userId')
      if (stored) return stored
    }
    // TODO: Retornar null cuando tengamos autenticación real
    return null
  }

  useEffect(() => {
    async function loadRole() {
      if (!selectedWorkspaceId) {
        setRole(null)
        setLoading(false)
        return
      }

      const userId = getUserId()
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
  }, [selectedWorkspaceId])

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

