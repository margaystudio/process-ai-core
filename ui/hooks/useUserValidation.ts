'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { useWorkspace } from '@/contexts/WorkspaceContext'

const SUPABASE_TIMEOUT_MS = 6000

interface UserValidationState {
  isValid: boolean | null
  hasWorkspaces: boolean | null
  error: string | null
  localUserId: string | null
}

/**
 * Valida sesión Supabase y delega el perfil/workspaces a WorkspaceContext
 * (un solo GET /users/me para toda la app).
 */
export function useUserValidation(): UserValidationState {
  const { loading: workspaceLoading, workspaces, currentUser } = useWorkspace()
  const [authState, setAuthState] = useState<{
    checked: boolean
    hasSession: boolean
    error: string | null
  }>({ checked: false, hasSession: false, error: null })

  useEffect(() => {
    async function validateSession() {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
      const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

      if (!supabaseUrl || !supabaseKey) {
        setAuthState({ checked: true, hasSession: true, error: null })
        return
      }

      const supabase = createClient()
      try {
        const result = await Promise.race([
          supabase.auth.getSession(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error('SupabaseTimeout')), SUPABASE_TIMEOUT_MS)
          ),
        ])
        const session = result.data?.session
        if (!session?.user) {
          setAuthState({ checked: true, hasSession: false, error: 'No hay sesión activa' })
          return
        }
        setAuthState({ checked: true, hasSession: true, error: null })
      } catch (err) {
        const message =
          err instanceof Error && err.message === 'SupabaseTimeout'
            ? 'No se pudo conectar con el servicio de autenticación. Revisá tu conexión.'
            : 'Error verificando sesión'
        setAuthState({ checked: true, hasSession: false, error: message })
      }
    }

    validateSession()
  }, [])

  if (!authState.checked) {
    return { isValid: null, hasWorkspaces: null, error: null, localUserId: null }
  }

  if (!authState.hasSession) {
    return {
      isValid: false,
      hasWorkspaces: false,
      error: authState.error,
      localUserId: null,
    }
  }

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
