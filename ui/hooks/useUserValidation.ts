'use client'

import { useWorkspace } from '@/contexts/WorkspaceContext'

interface UserValidationState {
  isValid: boolean | null
  hasWorkspaces: boolean | null
  error: string | null
  localUserId: string | null
}

/**
 * Valida el perfil/workspaces vía WorkspaceContext (GET /users/me).
 * No usa getSession() en el cliente: la cookie SSO del Hub es HttpOnly y solo
 * el servidor/middleware puede leerla de forma fiable.
 */
export function useUserValidation(): UserValidationState {
  const { loading: workspaceLoading, workspaces, currentUser } = useWorkspace()

  if (workspaceLoading) {
    return { isValid: null, hasWorkspaces: null, error: null, localUserId: null }
  }

  if (!currentUser) {
    return {
      isValid: false,
      hasWorkspaces: false,
      error: 'No se pudo cargar el perfil del usuario',
      localUserId: null,
    }
  }

  return {
    isValid: true,
    hasWorkspaces: workspaces.length > 0,
    error: null,
    localUserId: currentUser.id,
  }
}
