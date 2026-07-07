'use client'

import { useWorkspace } from '@/contexts/WorkspaceContext'

interface UserInfo {
  email: string | null
  name: string | null
  avatarUrl: string | null
  supabaseUserId: string | null
}

/**
 * Información del usuario autenticado desde WorkspaceContext (GET /users/me).
 * Evita getSession() en el cliente con cookies HttpOnly del SSO del Hub.
 */
export function useUser(): UserInfo | null {
  const { currentUser, loading } = useWorkspace()

  if (loading || !currentUser) return null

  return {
    email: currentUser.email,
    name: currentUser.name,
    avatarUrl: null,
    supabaseUserId: null,
  }
}
