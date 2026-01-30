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
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

        // Si Supabase no está configurado, permitir acceso (modo desarrollo)
        if (!supabaseUrl || !supabaseKey) {
          setState({
            isValid: true,
            hasWorkspaces: null,
            error: null,
            localUserId: null,
          })
          return
        }

        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()

        if (!session?.user) {
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

        // Verificar que el usuario existe en la BD local
        const userResponse = await fetch(`${apiUrl}/api/v1/auth/user`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        })

        if (userResponse.status === 404) {
          // Usuario no existe en BD local
          setState({
            isValid: false,
            hasWorkspaces: false,
            error: 'Usuario no encontrado en la base de datos. Por favor, contacta al administrador.',
            localUserId: null,
          })
          return
        }

        if (!userResponse.ok) {
          // Intentar obtener el mensaje de error del backend
          let errorMessage = `Error verificando usuario: ${userResponse.statusText}`
          try {
            const errorData = await userResponse.json()
            errorMessage = errorData.detail || errorData.message || errorMessage
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
        const hasWorkspaces = Array.isArray(workspaces) && workspaces.length > 0

        setState({
          isValid: true,
          hasWorkspaces,
          error: null,
          localUserId,
        })
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
