'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { getCurrentUser } from '@/lib/api'

const SUPABASE_TIMEOUT_MS = 6000

interface UserValidationState {
  isValid: boolean | null  // null = loading, true = válido, false = inválido
  hasWorkspaces: boolean | null
  error: string | null
  localUserId: string | null
}

/**
 * Valida que el usuario autenticado en Supabase existe en la BD local
 * y tiene al menos un workspace asociado.
 *
 * Llama a GET /api/v1/users/me que, al depender de sync_workspace_access,
 * crea el User+Workspace+Membership si es la primera vez que el usuario
 * entra a process-ai.
 */
export function useUserValidation(): UserValidationState {
  const [state, setState] = useState<UserValidationState>({
    isValid: null,
    hasWorkspaces: null,
    error: null,
    localUserId: null,
  })

  useEffect(() => {
    async function validateUser() {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
      const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

      // Modo desarrollo sin Supabase
      if (!supabaseUrl || !supabaseKey) {
        setState({ isValid: true, hasWorkspaces: null, error: null, localUserId: null })
        return
      }

      const supabase = createClient()
      const getSessionWithTimeout = () =>
        Promise.race([
          supabase.auth.getSession(),
          new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error('SupabaseTimeout')), SUPABASE_TIMEOUT_MS)
          ),
        ])

      let session
      try {
        const result = await getSessionWithTimeout()
        session = result.data?.session
      } catch (err) {
        if (err instanceof Error && err.message === 'SupabaseTimeout') {
          setState({
            isValid: false,
            hasWorkspaces: false,
            error: 'No se pudo conectar con el servicio de autenticación. Revisá tu conexión.',
            localUserId: null,
          })
          return
        }
        throw err
      }

      if (!session?.user) {
        setState({ isValid: false, hasWorkspaces: false, error: 'No hay sesión activa', localUserId: null })
        return
      }

      try {
        const { user, workspaces } = await getCurrentUser()

        // Guardar local_user_id para hooks que lo necesiten (useUserId, Header profile, etc.)
        localStorage.setItem('local_user_id', user.id)
        window.dispatchEvent(
          new CustomEvent('localStorageChange', { detail: { key: 'local_user_id', value: user.id } })
        )

        const hasWorkspaces = workspaces.length > 0
        setState({ isValid: true, hasWorkspaces, error: null, localUserId: user.id })
      } catch (err) {
        console.error('[useUserValidation] Error al obtener usuario:', err)
        setState({
          isValid: false,
          hasWorkspaces: false,
          error: err instanceof Error ? err.message : 'Error verificando usuario',
          localUserId: null,
        })
      }
    }

    validateUser()
  }, [])

  return state
}
