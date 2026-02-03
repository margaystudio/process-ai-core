'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { acceptInvitationByToken, getInvitationByToken } from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useUserId } from '@/hooks/useUserId'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { createClient } from '@/lib/supabase/client'

export default function AcceptInvitationPage() {
  const router = useRouter()
  const params = useParams()
  const { withLoading } = useLoading()
  const userId = useUserId()
  const { refreshWorkspaces } = useWorkspace()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [invitation, setInvitation] = useState<any>(null)
  const [showAuth, setShowAuth] = useState(false)
  const [emailMatches, setEmailMatches] = useState<boolean | null>(null) // null = no verificado, true = coincide, false = no coincide

  const token = params?.token as string

  // Estados para registro/login
  const [authMethod, setAuthMethod] = useState<'password' | 'otp' | 'oauth'>('password')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [otpCode, setOtpCode] = useState('')
  const [emailConfirmationRequired, setEmailConfirmationRequired] = useState(false)
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [passwordResetSent, setPasswordResetSent] = useState(false)
  const acceptingRef = useRef(false) // Prevenir múltiples intentos con ref

  // Helper para guardar user_id y notificar al hook useUserId
  const saveUserId = (userId: string) => {
    localStorage.setItem('local_user_id', userId)
    // Disparar evento personalizado para que useUserId lo detecte
    window.dispatchEvent(new CustomEvent('localStorageChange', {
      detail: { key: 'local_user_id', value: userId }
    }))
    console.log('User ID guardado en localStorage y evento disparado:', userId)
  }

  // Helper para refrescar workspaces con retry y verificación
  const refreshWorkspacesWithRetry = async (userId: string | null | undefined): Promise<boolean> => {
    const delays = [200, 600, 1200] // ms
    
    const attemptRefresh = async (attempt = 1): Promise<boolean> => {
      try {
        console.log(`[refreshWorkspacesWithRetry] Intento ${attempt}: Refrescando workspaces para user_id: ${userId}`)
        await refreshWorkspaces(userId || undefined)
        
        // Verificar que se cargaron workspaces consultando directamente la API
        const { getUserWorkspaces } = await import('@/lib/api')
        if (!userId) {
          console.warn('[refreshWorkspacesWithRetry] No hay userId, no se puede verificar')
          return false
        }
        
        const workspaces = await getUserWorkspaces(userId)
        console.log(`[refreshWorkspacesWithRetry] Workspaces obtenidos después de refresh: ${workspaces.length}`, workspaces.map(ws => ws.name))
        
        if (workspaces.length > 0) {
          console.log('✅ [refreshWorkspacesWithRetry] Workspaces refrescados exitosamente')
          return true
        } else {
          console.warn(`[refreshWorkspacesWithRetry] No se encontraron workspaces (intento ${attempt})`)
          if (attempt < 3) {
            const delay = delays[attempt - 1] || 200
            console.log(`[refreshWorkspacesWithRetry] Reintentando en ${delay}ms...`)
            await new Promise(resolve => setTimeout(resolve, delay))
            return attemptRefresh(attempt + 1)
          } else {
            console.error('[refreshWorkspacesWithRetry] No se encontraron workspaces después de 3 intentos')
            return false
          }
        }
      } catch (err) {
        console.warn(`[refreshWorkspacesWithRetry] Error refrescando workspaces (intento ${attempt}):`, err)
        if (attempt < 3) {
          const delay = delays[attempt - 1] || 200
          console.log(`[refreshWorkspacesWithRetry] Reintentando en ${delay}ms...`)
          await new Promise(resolve => setTimeout(resolve, delay))
          return attemptRefresh(attempt + 1)
        } else {
          console.error('[refreshWorkspacesWithRetry] No se pudieron refrescar workspaces después de 3 intentos')
          return false
        }
      }
    }
    
    return attemptRefresh()
  }

  useEffect(() => {
    // Verificar si hay userId en la URL (viene del callback de OAuth/Magic Link)
    const urlParams = new URLSearchParams(window.location.search)
    const userIdFromUrl = urlParams.get('user_id')
    if (userIdFromUrl) {
      // Usar la función helper para guardar y notificar
      if (typeof window !== 'undefined') {
        localStorage.setItem('local_user_id', userIdFromUrl)
        window.dispatchEvent(new CustomEvent('localStorageChange', {
          detail: { key: 'local_user_id', value: userIdFromUrl }
        }))
      }
      // Limpiar la URL pero mantener el pathname completo
      const cleanUrl = window.location.pathname
      window.history.replaceState({}, '', cleanUrl)
    }
    
    if (token) {
      loadInvitation()
    }
  }, [token])

  const loadInvitation = async () => {
    try {
      setLoading(true)
      setError(null)
      const invitationData = await getInvitationByToken(token)
      setInvitation(invitationData)
      setEmail(invitationData.email) // Pre-llenar email
      setName(invitationData.email.split('@')[0]) // Pre-llenar nombre con parte antes del @
      
      // Verificar si hay usuario autenticado
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      
      if (session?.user) {
        // Hay usuario autenticado, verificar email
        if (session.user.email === invitationData.email) {
          // Email coincide, esperar a que userId esté disponible y aceptar
          setShowAuth(false)
          setEmailMatches(true)
          // El useEffect se encargará de aceptar cuando userId esté disponible
        } else {
          setError(`Esta invitación es para ${invitationData.email}, pero estás autenticado como ${session.user.email}. Por favor, cierra sesión e inicia sesión con el email correcto.`)
          setShowAuth(false)
          setEmailMatches(false) // Email NO coincide - BLOQUEAR aceptación
        }
      } else {
        // Usuario no autenticado, mostrar opciones de registro/login
        setShowAuth(true)
        setEmailMatches(null) // Aún no verificado
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error cargando invitación')
      setShowAuth(false)
    } finally {
      setLoading(false)
    }
  }

  // Verificar autenticación y aceptar cuando userId esté disponible
  useEffect(() => {
    // Prevenir ejecución si ya estamos procesando o ya fue exitoso
    if (acceptingRef.current || success || !invitation || showAuth || loading) {
      return
    }
    
    // NO aceptar si el email no coincide
    if (emailMatches === false) {
      return
    }
    
    async function checkAndAccept() {
      // Verificar nuevamente antes de ejecutar
      if (acceptingRef.current || success) {
        return
      }
      
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      
      // Validar nuevamente que el email coincide antes de aceptar
      if (session?.user?.email && session.user.email.toLowerCase() === invitation.email.toLowerCase()) {
        // Marcar que estamos aceptando para evitar múltiples intentos
        acceptingRef.current = true
        
        // Email coincide, verificar si tenemos userId
        const localUserId = localStorage.getItem('local_user_id') || userId
        
        // Obtener token de autenticación
        const authToken = session?.access_token || null
        
        // Intentar aceptar la invitación (el backend creará el usuario si no existe)
        try {
          await withLoading(async () => {
            const result = await acceptInvitationByToken(token, localUserId || null, authToken)
            
            // Guardar el user_id retornado (siempre, por si acaso cambió o se creó)
            const finalUserId = result.user_id || localUserId
            if (finalUserId) {
              saveUserId(finalUserId)
            }
            
            setSuccess(true)
            
            // ETAPA C: Refrescar workspaces con retry antes de navegar
            // Asegurar que los workspaces estén cargados antes de navegar
            console.log('Refrescando workspaces con retry antes de navegar...')
            const refreshSuccess = await refreshWorkspacesWithRetry(finalUserId)
            
            if (refreshSuccess) {
              console.log('Navegando a /workspace con workspaces cargados')
              router.push(`/workspace`)
            } else {
              // Si falla, navegar de todas formas pero mostrar mensaje
              console.warn('Navegando a /workspace sin workspaces (puede requerir refresh manual)')
              router.push(`/workspace`)
            }
          })
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
          acceptingRef.current = false // Permitir reintentar si falla
        }
      }
    }
    
    // Ejecutar solo una vez cuando las condiciones se cumplan
    checkAndAccept()
    
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invitation, emailMatches, showAuth, loading]) // Dependencias mínimas para evitar loops

  const handleSignOut = async () => {
    try {
      const supabase = createClient()
      await supabase.auth.signOut()
      localStorage.removeItem('local_user_id')
      // Recargar la página para mostrar el formulario de login/registro
      window.location.reload()
    } catch (err) {
      console.error('Error cerrando sesión:', err)
      setError('Error al cerrar sesión. Por favor, intenta nuevamente.')
    }
  }

  const handleAccept = async () => {
    if (!token) {
      setError('Token de invitación no válido')
      return
    }

    // VALIDACIÓN CRÍTICA: Verificar que el email del usuario autenticado coincida con el email de la invitación
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()
    
    if (!session?.user?.email) {
      setError('No estás autenticado. Por favor, inicia sesión primero.')
      return
    }
    
    if (session.user.email.toLowerCase() !== invitation.email.toLowerCase()) {
      setError(`Esta invitación es para ${invitation.email}, pero estás autenticado como ${session.user.email}. Solo el usuario invitado puede aceptar esta invitación.`)
      setEmailMatches(false)
      return
    }

    // Obtener token de autenticación
    const authToken = session.access_token || null

    await withLoading(async () => {
      try {
        setLoading(true)
        setError(null)

        // El backend creará el usuario automáticamente si no existe
        const result = await acceptInvitationByToken(token, userId || null, authToken)
        
        // Guardar el user_id retornado (siempre)
        const finalUserId = result.user_id || userId
        if (finalUserId) {
          saveUserId(finalUserId)
        }
        
        setWorkspaceId(result.workspace_id)
        setSuccess(true)

        // Refrescar workspaces con retry antes de navegar
        const refreshSuccess = await refreshWorkspacesWithRetry(finalUserId)
        
        if (refreshSuccess) {
          console.log('Navegando a /workspace con workspaces cargados')
          router.push(`/workspace`)
        } else {
          console.warn('Navegando a /workspace sin workspaces (puede requerir refresh manual)')
          router.push(`/workspace`)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
      } finally {
        setLoading(false)
      }
    })
  }

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const supabase = createClient()
    if (!supabase) {
      setError('Error creando cliente de Supabase')
      setLoading(false)
      return
    }

    try {
      // Intentar registrar usuario en Supabase
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            name: name || email.split('@')[0],
          },
          emailRedirectTo: `${window.location.origin}/auth/callback?next=/invitations/accept/${token}`,
        },
      })

      // Si el error indica que el usuario ya existe, intentar iniciar sesión automáticamente
      if (error) {
        if (error.message.includes('already registered') || error.message.includes('User already registered')) {
          // Usuario ya existe, intentar iniciar sesión automáticamente
          const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
            email,
            password,
          })
          
          if (loginError) {
            setError('Este email ya está registrado. Por favor, ingresa tu contraseña correcta o usa "Recuperar contraseña".')
            setLoading(false)
            return
          }
          
          // Login exitoso, aceptar invitación directamente (el backend creará el usuario si no existe)
          if (loginData.user) {
            const { data: { session: loginSession } } = await supabase.auth.getSession()
            const authToken = loginSession?.access_token || null
            
            try {
              await withLoading(async () => {
                // NO llamar a syncUser - el backend creará el usuario automáticamente
                const result = await acceptInvitationByToken(token, null, authToken)
                
                // Guardar el user_id retornado (siempre)
                const finalUserId = result.user_id
                if (finalUserId) {
                  saveUserId(finalUserId)
                }
                
                setSuccess(true)
                
                // Refrescar workspaces con retry antes de navegar
                const refreshSuccess = await refreshWorkspacesWithRetry(finalUserId)
                
                if (refreshSuccess) {
                  router.push(`/workspace`)
                } else {
                  router.push(`/workspace`)
                }
              })
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
              setLoading(false)
            }
            return
          }
        } else {
          throw error
        }
      }

      // Si el registro fue exitoso pero no hay sesión (email no confirmado)
      if (data.user && !data.session) {
        setEmailConfirmationRequired(true)
        setError('⚠️ Se envió un email de confirmación. En desarrollo, los emails pueden no llegar. Te recomendamos usar Google o Magic Link para continuar inmediatamente.')
        setLoading(false)
        return
      }

      // Si hay sesión, aceptar invitación directamente
      if (data.session) {
        const authToken = data.session.access_token
        
        try {
          await withLoading(async () => {
            // NO llamar a syncUser - el backend creará el usuario automáticamente
            const result = await acceptInvitationByToken(token, null, authToken)
            
            // Guardar el user_id retornado (siempre)
            const finalUserId = result.user_id
            if (finalUserId) {
              saveUserId(finalUserId)
            }
            
            setSuccess(true)
            
            // Refrescar workspaces con retry antes de navegar
            const refreshSuccess = await refreshWorkspacesWithRetry(finalUserId)
            
            if (refreshSuccess) {
              router.push(`/workspace`)
            } else {
              router.push(`/workspace`)
            }
          })
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
          setLoading(false)
        }
        return
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al registrarse')
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const supabase = createClient()
    if (!supabase) {
      setError('Error creando cliente de Supabase')
      setLoading(false)
      return
    }

    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      })

      if (error) throw error

      if (data.user) {
        // NO llamar a syncUser - el backend creará el usuario automáticamente cuando se acepte la invitación
        const { data: { session } } = await supabase.auth.getSession()
        const authToken = session?.access_token || null
        
        const localUserId = localStorage.getItem('local_user_id')
        try {
          await withLoading(async () => {
            // El backend creará el usuario si no existe
            const result = await acceptInvitationByToken(token, localUserId || null, authToken)
            
            // Guardar el user_id retornado (siempre)
            const finalUserId = result.user_id || localUserId
            if (finalUserId) {
              saveUserId(finalUserId)
            }
            
            setSuccess(true)
            
            // Refrescar workspaces con retry antes de navegar
            const refreshSuccess = await refreshWorkspacesWithRetry(finalUserId)
            
            if (refreshSuccess) {
              router.push(`/workspace`)
            } else {
              router.push(`/workspace`)
            }
          })
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
          setLoading(false)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  const handleOtpSend = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const supabase = createClient()
    if (!supabase) {
      setLoading(false)
      return
    }

    try {
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback?next=/invitations/accept/${token}`,
        },
      })

      if (error) {
        // Manejar error de rate limit específicamente
        if (error.message.toLowerCase().includes('rate limit') || error.message.toLowerCase().includes('too many')) {
          setError(
            'Se ha alcanzado el límite de envíos de email. Por favor, espera unos minutos o usa Google OAuth para continuar inmediatamente.'
          )
        } else {
          throw error
        }
        setLoading(false)
        return
      }

      setOtpSent(true)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Error al enviar código'
      // Verificar si es un error de rate limit en el catch también
      if (errorMessage.toLowerCase().includes('rate limit') || errorMessage.toLowerCase().includes('too many')) {
        setError(
          'Se ha alcanzado el límite de envíos de email. Por favor, espera unos minutos o usa Google OAuth para continuar inmediatamente.'
        )
      } else {
        setError(errorMessage)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const supabase = createClient()
    if (!supabase) {
      setError('Error creando cliente de Supabase')
      setLoading(false)
      return
    }

    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/invitations/accept/${token}`,
      })

      if (error) {
        // Manejar error de rate limit específicamente
        if (error.message.toLowerCase().includes('rate limit') || error.message.toLowerCase().includes('too many')) {
          setError(
            'Se ha alcanzado el límite de envíos de email. Por favor, espera unos minutos o usa Google OAuth para continuar inmediatamente.'
          )
          setLoading(false)
          return
        }
        throw error
      }

      setPasswordResetSent(true)
      setError(null)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Error al enviar email de recuperación'
      // Verificar si es un error de rate limit en el catch también
      if (errorMessage.toLowerCase().includes('rate limit') || errorMessage.toLowerCase().includes('too many')) {
        setError(
          'Se ha alcanzado el límite de envíos de email. Por favor, espera unos minutos o usa Google OAuth para continuar inmediatamente.'
        )
      } else {
        setError(errorMessage)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleOAuthLogin = async (provider: 'google' | 'facebook' = 'google') => {
    setLoading(true)
    setError(null)
    setEmailConfirmationRequired(false)

    const supabase = createClient()
    if (!supabase) {
      setError('Error creando cliente de Supabase')
      setLoading(false)
      return
    }

    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: `${window.location.origin}/auth/callback?next=/invitations/accept/${token}`,
          queryParams: {
            email: email, // Pre-llenar el email de la invitación
          },
        },
      })

      if (error) throw error
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión con OAuth')
      setLoading(false)
    }
  }

  const handleOtpVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    const supabase = createClient()
    if (!supabase) {
      setLoading(false)
      return
    }

    try {
      const { data, error } = await supabase.auth.verifyOtp({
        email,
        token: otpCode,
        type: 'email',
      })

      if (error) throw error

      if (data.user) {
        // NO llamar a syncUser - el backend creará el usuario automáticamente cuando se acepte la invitación
        const { data: { session } } = await supabase.auth.getSession()
        const authToken = session?.access_token || null
        
        const localUserId = localStorage.getItem('local_user_id')
        try {
          await withLoading(async () => {
            // El backend creará el usuario si no existe
            const result = await acceptInvitationByToken(token, localUserId || null, authToken)
            
            // Guardar el user_id retornado (siempre)
            const finalUserId = result.user_id || localUserId
            if (finalUserId) {
              saveUserId(finalUserId)
            }
            
            setSuccess(true)
            
            // Refrescar workspaces con retry antes de navegar
            const refreshSuccess = await refreshWorkspacesWithRetry(finalUserId)
            
            if (refreshSuccess) {
              router.push(`/workspace`)
            } else {
              router.push(`/workspace`)
            }
          })
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
          setLoading(false)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error verificando código')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-extrabold text-gray-900">Token Inválido</h2>
            <p className="mt-2 text-sm text-gray-600">
              El token de invitación no es válido o ha expirado.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (loading && !invitation) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Cargando invitación...</p>
        </div>
      </div>
    )
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
              <svg
                className="h-6 w-6 text-green-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">¡Invitación Aceptada!</h2>
            <p className="mt-2 text-sm text-gray-600">
              Has sido agregado exitosamente al espacio de trabajo. Redirigiendo...
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (!invitation) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <h2 className="text-3xl font-extrabold text-gray-900">Error</h2>
            <p className="mt-2 text-sm text-gray-600">
              {error || 'No se pudo cargar la invitación'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900">Aceptar Invitación</h2>
          <p className="mt-2 text-sm text-gray-600">
            Has sido invitado a unirte a un espacio de trabajo como <strong>{invitation.role_name}</strong>
          </p>
          {invitation.message && (
            <p className="mt-2 text-sm text-gray-500 italic">"{invitation.message}"</p>
          )}
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        {showAuth && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="mb-4 flex space-x-2">
              <button
                onClick={() => {
                  setAuthMethod('password')
                  setEmailConfirmationRequired(false)
                  setError(null)
                }}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                  authMethod === 'password'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Email + Contraseña
              </button>
              <button
                onClick={() => {
                  setAuthMethod('otp')
                  setEmailConfirmationRequired(false)
                  setError(null)
                }}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                  authMethod === 'otp'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Magic Link
              </button>
              <button
                onClick={() => {
                  setAuthMethod('oauth')
                  setEmailConfirmationRequired(false)
                  setError(null)
                }}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium ${
                  authMethod === 'oauth'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Google
              </button>
            </div>

            {authMethod === 'oauth' ? (
              <div className="space-y-4">
                <p className="text-sm text-gray-600 text-center">
                  Inicia sesión con Google usando el email de la invitación: <strong>{email}</strong>
                </p>
                <button
                  onClick={() => handleOAuthLogin('google')}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-3 bg-white border-2 border-gray-300 hover:border-gray-400 text-gray-700 font-medium py-3 px-4 rounded-md disabled:opacity-50 transition-colors"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                  Continuar con Google
                </button>
                {emailConfirmationRequired && (
                  <p className="text-xs text-gray-500 text-center mt-2">
                    💡 OAuth evita la necesidad de confirmar el email
                  </p>
                )}
              </div>
            ) : authMethod === 'password' ? (
              <>
                <form onSubmit={handleRegister} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Nombre
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      disabled
                      className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                    />
                    <p className="mt-1 text-xs text-gray-500">Este email está asociado a la invitación</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Contraseña
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      minLength={6}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  {emailConfirmationRequired && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                      <p className="text-sm text-yellow-800 mb-2">
                        ⚠️ <strong>Email de confirmación requerido</strong>
                      </p>
                      <p className="text-sm text-yellow-700 mb-2">
                        Se intentó enviar un email de confirmación a <strong>{email}</strong>. 
                        <strong className="block mt-1">En desarrollo, los emails pueden no llegar si no hay un proveedor de email configurado en Supabase.</strong>
                      </p>
                      <div className="bg-white rounded p-2 mt-2 mb-2">
                        <p className="text-xs text-yellow-800 font-semibold mb-1">💡 Recomendación para desarrollo:</p>
                        <p className="text-xs text-yellow-700">
                          Usa <button type="button" onClick={() => { setAuthMethod('oauth'); setEmailConfirmationRequired(false); setError(null); }} className="underline font-semibold text-yellow-800">Google</button> o <button type="button" onClick={() => { setAuthMethod('otp'); setEmailConfirmationRequired(false); setError(null); }} className="underline font-semibold text-yellow-800">Magic Link</button> para continuar sin confirmación de email.
                        </p>
                      </div>
                      <p className="text-xs text-yellow-600 mt-2 pt-2 border-t border-yellow-200">
                        Si prefieres usar email/contraseña, verifica tu bandeja de entrada y spam. Una vez confirmado, vuelve a esta página y la invitación se aceptará automáticamente.
                      </p>
                    </div>
                  )}
                  <div className="space-y-3">
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-md disabled:opacity-50"
                    >
                      {loading ? 'Procesando...' : 'Continuar'}
                    </button>
                    <p className="text-xs text-gray-500 text-center">
                      Si ya tienes una cuenta con este email, se iniciará sesión automáticamente. Si no, se creará una nueva cuenta.
                    </p>
                    <div className="text-center">
                      <button
                        type="button"
                        onClick={handleLogin}
                        disabled={loading}
                        className="text-sm text-blue-600 hover:text-blue-800 underline"
                      >
                        Ya tengo cuenta y quiero iniciar sesión
                      </button>
                    </div>
                  </div>
                  <div className="text-center">
                    <button
                      type="button"
                      onClick={() => setShowForgotPassword(true)}
                      className="text-sm text-blue-600 hover:text-blue-800 underline"
                    >
                      ¿Olvidaste tu contraseña?
                    </button>
                  </div>
                  {showForgotPassword && (
                    <div className="space-y-4 mt-4">
                      <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                        <p className="text-sm text-blue-800 mb-2">
                          🔐 <strong>Recuperar contraseña</strong>
                        </p>
                        {passwordResetSent ? (
                          <div>
                            <p className="text-sm text-blue-700 mb-2">
                              Se intentó enviar un email a <strong>{email}</strong> con instrucciones para restablecer tu contraseña.
                            </p>
                            <div className="bg-yellow-50 border border-yellow-200 rounded p-2 mt-2 mb-2">
                              <p className="text-xs text-yellow-800 font-semibold mb-1">⚠️ En desarrollo:</p>
                              <p className="text-xs text-yellow-700 mb-2">
                                Los emails pueden no llegar si no hay un proveedor de email configurado en Supabase.
                              </p>
                              <p className="text-xs text-yellow-700">
                                💡 <strong>Alternativa:</strong> Usa <button type="button" onClick={() => { setAuthMethod('oauth'); setShowForgotPassword(false); setPasswordResetSent(false); setError(null); }} className="underline font-semibold text-yellow-800">Google</button> o <button type="button" onClick={() => { setAuthMethod('otp'); setShowForgotPassword(false); setPasswordResetSent(false); setError(null); }} className="underline font-semibold text-yellow-800">Magic Link</button> para iniciar sesión sin contraseña.
                              </p>
                            </div>
                            <p className="text-xs text-blue-600 mb-2">
                              Si configuraste un proveedor de email en Supabase, revisa tu bandeja de entrada y spam.
                            </p>
                            <button
                              type="button"
                              onClick={() => {
                                setShowForgotPassword(false)
                                setPasswordResetSent(false)
                              }}
                              className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline"
                            >
                              Volver al inicio de sesión
                            </button>
                          </div>
                        ) : (
                          <form onSubmit={handleForgotPassword} className="space-y-3">
                            <p className="text-sm text-blue-700">
                              Ingresá tu email y te enviaremos un link para restablecer tu contraseña.
                            </p>
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-1">
                                Email
                              </label>
                              <input
                                type="email"
                                value={email}
                                disabled
                                className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                              />
                              <p className="mt-1 text-xs text-gray-500">Este email está asociado a la invitación</p>
                            </div>
                            <div className="flex space-x-3">
                              <button
                                type="submit"
                                disabled={loading}
                                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50"
                              >
                                {loading ? 'Enviando...' : 'Enviar link de recuperación'}
                              </button>
                              <button
                                type="button"
                                onClick={() => setShowForgotPassword(false)}
                                disabled={loading}
                                className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded-md disabled:opacity-50"
                              >
                                Cancelar
                              </button>
                            </div>
                          </form>
                        )}
                      </div>
                    </div>
                  )}
                </form>
              </>
            ) : (
              <>
                {!otpSent ? (
                  <form onSubmit={handleOtpSend} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Email
                      </label>
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        disabled
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-500"
                      />
                      <p className="mt-1 text-xs text-gray-500">Este email está asociado a la invitación</p>
                    </div>
                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50"
                    >
                      {loading ? 'Enviando...' : 'Enviar Magic Link'}
                    </button>
                  </form>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-gray-600">
                      Revisa tu email y haz clic en el link que te enviamos. Serás redirigido automáticamente para aceptar la invitación.
                    </p>
                    <button
                      onClick={() => setOtpSent(false)}
                      className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-4 rounded-md"
                    >
                      Volver
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {!showAuth && emailMatches !== false && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="text-center mb-4">
              <p className="text-lg font-medium text-gray-900">
                Ya estás autenticado como <span className="font-semibold">{invitation.email}</span>.
              </p>
              <p className="text-sm text-gray-600">
                Haz clic en el botón para aceptar la invitación.
                {!userId && (
                  <span className="block mt-2 text-xs text-gray-500">
                    (Tu cuenta se creará automáticamente al aceptar)
                  </span>
                )}
              </p>
            </div>
            <div className="flex justify-center space-x-4">
              <button
                onClick={handleAccept}
                disabled={loading || emailMatches === false}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Aceptando...' : 'Aceptar Invitación'}
              </button>
              <button
                onClick={() => router.push('/workspace')}
                disabled={loading}
                className="bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium py-2 px-6 rounded-md disabled:opacity-50"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
        
        {/* Mostrar mensaje si el email no coincide */}
        {userId && !showAuth && emailMatches === false && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 mb-4">
                <svg
                  className="h-6 w-6 text-red-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Email no coincide
              </h3>
              <p className="text-sm text-gray-600 mb-4">
                Esta invitación es para <strong>{invitation.email}</strong>, pero estás autenticado con otro email.
              </p>
              <p className="text-sm text-gray-600 mb-4">
                Solo el usuario invitado puede aceptar esta invitación. Por favor, cierra sesión e inicia sesión con el email correcto.
              </p>
              <button
                onClick={handleSignOut}
                className="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-6 rounded-md"
              >
                Cerrar sesión
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
