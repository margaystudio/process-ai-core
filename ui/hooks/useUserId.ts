'use client'

import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Devuelve el ID local del usuario (UUID de la BD de process-ai).
 * Proviene de WorkspaceContext (GET /users/me), no de getSession() en el cliente.
 */
export function useUserId(): string | null {
  const { currentUser, loading } = useWorkspace()
  if (loading) return null
  return currentUser?.id ?? null
}
