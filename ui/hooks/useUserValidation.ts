'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

interface UserValidationState {
  isValid: boolean | null  // null = loading, true = válido, false = inválido
  hasWorkspaces: boolean | null
  error: string | null
  localUserId: string | null
}

/**
 * Hook para validar que el usuario autenticado en Supabase existe en la BD local
 * y tiene al menos un workspace asociado.
 * 
 * @returns Estado de validación del usuario
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
      console.log('[useUserValidation] Iniciando validación...')
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

        // Si Supabase no está configurado, permitir acceso (modo desarrollo)
        if (!supabaseUrl || !supabaseKey) {
          console.log('[useUserValidation] Supabase no configurado, permitiendo acceso')
          setState({
            isValid: true,
            hasWorkspaces: null,
            error: null,
            localUserId: null,
          })
          return
        }

        console.log('[useUserValidation] Obteniendo sesión de Supabase...')
        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()
        console.log('[useUserValidation] Sesión obtenida:', session ? 'Sí' : 'No')

        if (!session?.user) {
          console.log('[useUserValidation] No hay usuario en la sesión')
          setState({
            isValid: false,
            hasWorkspaces: false,
            error: 'No hay sesión activa',
            localUserId: null,
          })
          return
        }

        const token = session.access_token
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

        console.log('[useUserValidation] Verificando usuario en BD local...', `${apiUrl}/api/v1/auth/user`)
        
        // Agregar timeout al fetch para evitar que se cuelgue
        const controller = new AbortController()
        const timeoutId = setTimeout(() => {
          console.error('[useUserValidation] Timeout en fetch a /api/v1/auth/user (10 segundos)')
          controller.abort()
        }, 10000)
        
        let userResponse: Response
        try {
          // Verificar que el usuario existe en la BD local
          userResponse = await fetch(`${apiUrl}/api/v1/auth/user`, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
            signal: controller.signal,
          })
          clearTimeout(timeoutId)
          console.log('[useUserValidation] Respuesta de /api/v1/auth/user:', userResponse.status)

        } catch (fetchError: any) {
          clearTimeout(timeoutId)
          if (fetchError.name === 'AbortError') {
            console.error('[useUserValidation] Fetch abortado por timeout')
            setState({
              isValid: false,
              hasWorkspaces: false,
              error: 'Timeout verificando usuario en la base de datos. El servidor no respondió a tiempo.',
              localUserId: null,
            })
            return
          }
          throw fetchError
        }
        
        if (userResponse.status === 404) {
          // Usuario no existe en BD local
          console.log('[useUserValidation] Usuario no encontrado (404)')
          setState({
            isValid: false,
            hasWorkspaces: false,
            error: 'Usuario no encontrado en la base de datos. Por favor, contacta al administrador.',
            localUserId: null,
          })
          return
        }

        if (!userResponse.ok) {
          console.error('[useUserValidation] Error en respuesta:', userResponse.status, userResponse.statusText)
          // Intentar obtener el mensaje de error del backend
          let errorMessage = `Error verificando usuario: ${userResponse.statusText}`
          try {
            const errorData = await userResponse.json()
            errorMessage = errorData.detail || errorData.message || errorMessage
            console.error('[useUserValidation] Error del backend:', errorMessage)
          } catch {
            // Si no es JSON, intentar leer como texto
            try {
              const errorText = await userResponse.text()
              if (errorText) {
                errorMessage = errorText
              }
            } catch {
              // Usar el mensaje por defecto
            }
          }
          throw new Error(errorMessage)
        }

        const userData = await userResponse.json()
        const localUserId = userData.user?.id
        const localUserEmail = userData.user?.email

        console.log('[useUserValidation] Datos del usuario obtenidos:', { localUserId, localUserEmail })

        if (!localUserId) {
          setState({
            isValid: false,
            hasWorkspaces: false,
            error: 'No se pudo obtener el ID del usuario local',
            localUserId: null,
          })
          return
        }

        // Guardar el userId local en localStorage
        localStorage.setItem('local_user_id', localUserId)
        console.log('[useUserValidation] userId guardado en localStorage:', localUserId)

        // Verificar si el usuario tiene workspaces
        const workspacesResponse = await fetch(`${apiUrl}/api/v1/users/${localUserId}/workspaces`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        })

        if (!workspacesResponse.ok) {
          // Si falla, asumir que no tiene workspaces
          setState({
            isValid: true,
            hasWorkspaces: false,
            error: null,
            localUserId,
          })
          return
        }

        const workspaces = await workspacesResponse.json()
        console.log('[useUserValidation] Workspaces obtenidos:', workspaces)
        const hasWorkspaces = Array.isArray(workspaces) && workspaces.length > 0
        console.log('[useUserValidation] hasWorkspaces:', hasWorkspaces)

        console.log('[useUserValidation] Estableciendo estado final:', { isValid: true, hasWorkspaces, localUserId })
        setState({
          isValid: true,
          hasWorkspaces,
          error: null,
          localUserId,
        })
        console.log('[useUserValidation] Estado establecido correctamente')
      } catch (err) {
        console.error('Error validando usuario:', err)
        setState({
          isValid: false,
          hasWorkspaces: false,
          error: err instanceof Error ? err.message : 'Error desconocido validando usuario',
          localUserId: null,
        })
      }
    }

    validateUser()
  }, [])

  return state
}
