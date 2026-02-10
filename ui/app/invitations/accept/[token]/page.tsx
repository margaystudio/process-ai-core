'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { acceptInvitationByToken, getInvitationByToken, checkEmailExists } from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useUserId } from '@/hooks/useUserId'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { createClient } from '@/lib/supabase/client'

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Verifica si el usuario está logueado en Supabase
 */
async function isUserLoggedIn(): Promise<boolean> {
  try {
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()
    return !!session?.user
  } catch {
    return false
  }
}

/**
 * Obtiene el email del usuario logueado
 */
async function getLoggedInUserEmail(): Promise<string | null> {
  try {
    const supabase = createClient()
    const { data: { session } } = await supabase.auth.getSession()
    return session?.user?.email || null
  } catch {
    return null
  }
}

/**
 * Verifica si un email existe en la base de datos
 */
async function doesEmailExist(email: string): Promise<boolean> {
  try {
    const result = await checkEmailExists(email)
    return result.exists
  } catch {
    return false
  }
}

/**
 * Acepta la invitación
 */
async function acceptInvitation(
  token: string,
  authToken: string | null,
  userId: string | null
): Promise<{ user_id: string; workspace_id: string }> {
  return await acceptInvitationByToken(token, userId, authToken)
}

// ============================================================================
// COMPONENTES DE MODAL
// ============================================================================

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  email: string
  token: string
  onAuthSuccess: () => void
  onAuthError: (error: string) => void
}

function AuthModalExistingUser({ isOpen, onClose, email, token, onAuthSuccess, onAuthError }: AuthModalProps) {
  const [authLoading, setAuthLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [password, setPassword] = useState('')

  const handleMagicLink = async () => {
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/invitations/accept/${token}`,
        },
      })

      if (error) throw error

      // Magic link enviado, esperar a que el usuario haga click
      // El flujo continuará automáticamente cuando se autentique
      onAuthSuccess()
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error enviando Magic Link')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleGoogle = async () => {
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/invitations/accept/${token}`,
        },
      })

      if (error) throw error
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error iniciando sesión con Google')
      setAuthLoading(false)
    }
  }

  const handlePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      })

      if (error) throw error

      onAuthSuccess()
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Contraseña incorrecta')
    } finally {
      setAuthLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Confirmá tu acceso</h2>
        <p className="text-sm text-gray-600 mb-6">
          Detectamos que ya tenés una cuenta con este email.
        </p>

        <div className="space-y-3">
          <button
            onClick={handleMagicLink}
            disabled={authLoading}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {authLoading ? 'Enviando...' : 'Enviar Magic Link'}
          </button>

          <button
            onClick={handleGoogle}
            disabled={authLoading}
            className="w-full px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continuar con Google
          </button>

          {showPassword ? (
            <form onSubmit={handlePassword} className="space-y-3">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Contraseña"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                required
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={authLoading}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  Ingresar
                </button>
                <button
                  type="button"
                  onClick={() => setShowPassword(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancelar
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowPassword(true)}
              className="w-full text-sm text-blue-600 hover:text-blue-700 hover:underline"
            >
              Usar contraseña
            </button>
          )}
        </div>

        <button
          onClick={onClose}
          className="mt-4 text-sm text-gray-500 hover:text-gray-700"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}

function AuthModalNewUser({ isOpen, onClose, email, token, onAuthSuccess, onAuthError }: AuthModalProps) {
  const [authLoading, setAuthLoading] = useState(false)
  const [magicLinkSent, setMagicLinkSent] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [password, setPassword] = useState('')

  const handleMagicLink = async () => {
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/invitations/accept/${token}`,
        },
      })

      if (error) throw error

      setMagicLinkSent(true)
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error enviando Magic Link')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleGoogle = async () => {
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/invitations/accept/${token}`,
        },
      })

      if (error) throw error
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error iniciando sesión con Google')
      setAuthLoading(false)
    }
  }

  const handleCreatePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/invitations/accept/${token}`,
        },
      })

      if (error) throw error

      if (data.session) {
        onAuthSuccess()
      } else {
        // Email de confirmación enviado
        setMagicLinkSent(true)
      }
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error creando cuenta')
    } finally {
      setAuthLoading(false)
    }
  }

  if (!isOpen) return null

  if (magicLinkSent) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Ingresá para continuar</h2>
          <p className="text-sm text-gray-600 mb-6">
            Te enviaremos un enlace de acceso por email o podés usar Google.
          </p>

          <div className="space-y-3">
            <button
              onClick={handleMagicLink}
              disabled={authLoading}
              className="w-full px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              Reenviar Magic Link
            </button>

            <button
              onClick={handleGoogle}
              disabled={authLoading}
              className="w-full px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continuar con Google
            </button>
          </div>

          <button
            onClick={onClose}
            className="mt-4 text-sm text-gray-500 hover:text-gray-700"
          >
            Cerrar
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Ingresá para continuar</h2>
        <p className="text-sm text-gray-600 mb-6">
          Te enviaremos un enlace de acceso por email o podés usar Google.
        </p>

        <div className="space-y-3">
          <button
            onClick={handleMagicLink}
            disabled={authLoading}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {authLoading ? 'Enviando...' : 'Enviar Magic Link'}
          </button>

          <button
            onClick={handleGoogle}
            disabled={authLoading}
            className="w-full px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continuar con Google
          </button>

          {showPassword ? (
            <form onSubmit={handleCreatePassword} className="space-y-3">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Crear contraseña"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                required
                minLength={6}
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={authLoading}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  Crear cuenta
                </button>
                <button
                  type="button"
                  onClick={() => setShowPassword(false)}
                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancelar
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowPassword(true)}
              className="w-full text-sm text-blue-600 hover:text-blue-700 hover:underline"
            >
              Crear contraseña ahora
            </button>
          )}
        </div>

        <button
          onClick={onClose}
          className="mt-4 text-sm text-gray-500 hover:text-gray-700"
        >
          Cerrar
        </button>
      </div>
    </div>
  )
}

// ============================================================================
// COMPONENTE PRINCIPAL
// ============================================================================

export default function AcceptInvitationPage() {
  const router = useRouter()
  const params = useParams()
  const { withLoading } = useLoading()
  const userId = useUserId()
  const { refreshWorkspaces } = useWorkspace()
  
  const token = params?.token as string

  // Estados principales
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [invitation, setInvitation] = useState<any>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [isExistingUser, setIsExistingUser] = useState(false)

  // Cargar información de la invitación
  useEffect(() => {
    async function loadInvitation() {
      if (!token) {
        setError('Token de invitación no válido')
        setLoading(false)
        return
      }

      try {
        const data = await getInvitationByToken(token)
        setInvitation(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando invitación')
      } finally {
        setLoading(false)
      }
    }

    loadInvitation()
  }, [token])

  // Helper para guardar user_id
  const saveUserId = (userId: string) => {
    localStorage.setItem('local_user_id', userId)
    window.dispatchEvent(new CustomEvent('localStorageChange', {
      detail: { key: 'local_user_id', value: userId }
    }))
  }

  // Helper para refrescar workspaces
  const refreshWorkspacesWithRetry = async (userId: string): Promise<boolean> => {
    const delays = [200, 600, 1200]
    
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        await refreshWorkspaces(userId)
        const { getUserWorkspaces } = await import('@/lib/api')
        const workspaces = await getUserWorkspaces(userId)
        if (workspaces.length > 0) return true
      } catch (err) {
        console.warn(`Error refrescando workspaces (intento ${attempt}):`, err)
      }
      if (attempt < 3) {
        await new Promise(resolve => setTimeout(resolve, delays[attempt - 1]))
      }
    }
    return false
  }

  // Aceptar invitación (usuario ya autenticado)
  const handleAcceptInvitation = async () => {
    if (!token || !invitation) return

    try {
      await withLoading(async () => {
        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()
        const authToken = session?.access_token || null

        const result = await acceptInvitation(token, authToken, userId)
        
        if (result.user_id) {
          saveUserId(result.user_id)
        }

        await refreshWorkspacesWithRetry(result.user_id)
        router.push('/workspace')
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
    }
  }

  // Verificar autenticación cuando se carga la invitación o cuando cambia el estado
  useEffect(() => {
    async function checkAuth() {
      if (!invitation) return

      const loggedIn = await isUserLoggedIn()
      setIsAuthenticated(loggedIn)

      if (loggedIn) {
        // Usuario logueado: verificar email pero NO aceptar automáticamente
        const userEmail = await getLoggedInUserEmail()
        if (userEmail?.toLowerCase() !== invitation.email.toLowerCase()) {
          setError(`Esta invitación es para ${invitation.email}, pero estás autenticado como ${userEmail}.`)
        }
        // No aceptar automáticamente - el usuario debe hacer click en "Aceptar invitación"
      }
    }

    checkAuth()
    
    // También escuchar cambios en la sesión de Supabase (solo para actualizar estado, NO aceptar automáticamente)
    const supabase = createClient()
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user && invitation) {
        const userEmail = session.user.email
        if (userEmail?.toLowerCase() === invitation.email.toLowerCase()) {
          setIsAuthenticated(true)
          // NO aceptar automáticamente - el usuario debe hacer click en "Aceptar invitación"
        }
      } else {
        setIsAuthenticated(false)
      }
    })

    return () => {
      subscription.unsubscribe()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invitation, loading])


  // Click en "Aceptar invitación" (usuario no autenticado)
  const handleAcceptClick = async () => {
    if (!invitation) return

    // Verificar si el email existe
    const emailExists = await doesEmailExist(invitation.email)
    setIsExistingUser(emailExists)
    setShowAuthModal(true)
  }

  // Callback cuando la autenticación es exitosa
  const handleAuthSuccess = async () => {
    setShowAuthModal(false)
    
    // Esperar un momento para que la sesión se establezca
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // Verificar autenticación y aceptar invitación
    const loggedIn = await isUserLoggedIn()
    if (loggedIn) {
      setIsAuthenticated(true)
      await handleAcceptInvitation()
    }
  }

  // Cerrar sesión
  const handleSignOut = async () => {
    try {
      const supabase = createClient()
      await supabase.auth.signOut()
      localStorage.removeItem('local_user_id')
      router.push('/login')
    } catch (err) {
      console.error('Error cerrando sesión:', err)
    }
  }

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando invitación...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error && !invitation) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="max-w-md w-full bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold text-red-900 mb-2">Error</h2>
          <p className="text-red-800 mb-4">{error}</p>
          <button
            onClick={() => router.push('/login')}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
          >
            Ir a inicio de sesión
          </button>
        </div>
      </div>
    )
  }

  if (!invitation) return null

  // Obtener nombre del rol en español
  const getRoleLabel = (roleName: string) => {
    const roles: Record<string, string> = {
      viewer: 'Visualizador',
      creator: 'Creador',
      approver: 'Aprobador',
      admin: 'Administrador',
    }
    return roles[roleName] || roleName
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full bg-white rounded-lg shadow-sm p-8">
        {/* Pantalla base */}
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Te invitaron a unirte a <span className="text-blue-600">{invitation.workspace_name || 'un espacio de trabajo'}</span>
          </h1>
          <p className="text-gray-600 mb-6">
            Rol: <span className="font-medium">{getRoleLabel(invitation.role_name)}</span>
          </p>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
              {error}
            </div>
          )}

          {!isAuthenticated ? (
            <div className="space-y-3">
              <button
                onClick={handleAcceptClick}
                className="w-full px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
              >
                Aceptar invitación
              </button>
              <button
                onClick={handleSignOut}
                className="w-full text-sm text-gray-500 hover:text-gray-700 hover:underline"
              >
                ¿No sos esta persona? Cerrar sesión
              </button>
            </div>
          ) : (
            <div className="text-sm text-gray-600">
              <p>Procesando invitación...</p>
            </div>
          )}
        </div>

        {/* Modales de autenticación */}
        {isExistingUser ? (
          <AuthModalExistingUser
            isOpen={showAuthModal}
            onClose={() => setShowAuthModal(false)}
            email={invitation.email}
            token={token}
            onAuthSuccess={handleAuthSuccess}
            onAuthError={setError}
          />
        ) : (
          <AuthModalNewUser
            isOpen={showAuthModal}
            onClose={() => setShowAuthModal(false)}
            email={invitation.email}
            token={token}
            onAuthSuccess={handleAuthSuccess}
            onAuthError={setError}
          />
        )}
      </div>
    </div>
  )
}
