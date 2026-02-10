'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { acceptInvitationByToken, getInvitationByToken, checkEmailExists, updateUserProfile } from '@/lib/api'
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

// updateUserProfile se importa desde @/lib/api

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

/**
 * Modal para usuario existente: Login con Password o Google
 */
function AuthModalExistingUser({ isOpen, onClose, email, token, onAuthSuccess, onAuthError }: AuthModalProps) {
  const [authLoading, setAuthLoading] = useState(false)
  const [password, setPassword] = useState('')
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [resetEmailSent, setResetEmailSent] = useState(false)

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

  const handleForgotPassword = async () => {
    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/invitations/accept/${token}`,
      })

      if (error) throw error

      setResetEmailSent(true)
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error enviando email de recuperación')
    } finally {
      setAuthLoading(false)
    }
  }

  if (!isOpen) return null

  if (resetEmailSent) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Email enviado</h2>
          <p className="text-sm text-gray-600 mb-6">
            Te enviamos un correo para restablecer tu contraseña. Revisá tu bandeja de entrada.
          </p>
          <button
            onClick={() => {
              setResetEmailSent(false)
              setShowForgotPassword(false)
            }}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
          >
            Entendido
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Confirmá tu acceso</h2>
        <p className="text-sm text-gray-600 mb-4">
          Detectamos que ya tenés una cuenta con este email.
        </p>
        
        {/* Email read-only */}
        <div className="mb-4 p-2 bg-gray-50 rounded-md text-sm text-gray-700">
          {email}
        </div>

        <div className="space-y-3">
          <form onSubmit={handlePassword} className="space-y-3">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Contraseña"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              required
              autoFocus
            />
            <button
              type="submit"
              disabled={authLoading || !password}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {authLoading ? 'Ingresando...' : 'Ingresar'}
            </button>
          </form>

          <div className="text-center">
            <button
              onClick={() => setShowForgotPassword(true)}
              className="text-sm text-blue-600 hover:text-blue-700 hover:underline"
            >
              Olvidé mi contraseña
            </button>
          </div>

          {showForgotPassword && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-800 mb-2">
                Te enviaremos un correo para restablecer tu contraseña.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleForgotPassword}
                  disabled={authLoading}
                  className="flex-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Enviar email
                </button>
                <button
                  onClick={() => setShowForgotPassword(false)}
                  className="px-3 py-1.5 border border-gray-300 text-sm rounded-md hover:bg-gray-50"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-gray-500">O continuá con</span>
            </div>
          </div>

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
          Cancelar
        </button>
      </div>
    </div>
  )
}

/**
 * Modal para usuario nuevo: Nombre, Apellido, contraseña (colapsada) y Google.
 */
function AuthModalNewUser({ isOpen, onClose, email, token, onAuthSuccess, onAuthError }: AuthModalProps) {
  const [authLoading, setAuthLoading] = useState(false)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPasswordSection, setShowPasswordSection] = useState(false)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)
  const passwordInputRef = useRef<HTMLInputElement>(null)

  // Habilitar el botón cuando las contraseñas coinciden; nombre/apellido se validan al enviar.
  const passwordOk = password.length > 0 && password === confirmPassword
  const canSubmitPassword = passwordOk

  const handleGoogle = async () => {
    if (!firstName.trim() || !lastName.trim()) {
      onAuthError('Por favor, completá tu nombre y apellido')
      return
    }

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
      
      localStorage.setItem('pending_profile_update', JSON.stringify({ firstName, lastName }))
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error iniciando sesión con Google')
      setAuthLoading(false)
    }
  }

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!firstName.trim() || !lastName.trim()) {
      onAuthError('Por favor, completá tu nombre y apellido')
      return
    }
    
    if (password !== confirmPassword) {
      onAuthError('Las contraseñas no coinciden')
      return
    }

    setAuthLoading(true)
    try {
      const supabase = createClient()
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${window.location.origin}/invitations/accept/${token}`,
          // IMPORTANTE: No requerir confirmación de email
          // Esto se configura en Supabase Dashboard → Authentication → Settings
          // "Enable email confirmations" debe estar DESHABILITADO
        },
      })

      if (error) {
        // Si el usuario ya existe en Supabase, intentar login
        if (error.message.toLowerCase().includes('user already registered') || 
            error.message.toLowerCase().includes('already registered') ||
            error.message.toLowerCase().includes('email already exists')) {
          // Intentar login con la contraseña proporcionada
          const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
            email,
            password,
          })
          
          if (loginError) {
            throw new Error('Este email ya está registrado. Por favor, ingresá con tu contraseña.')
          }
          
          if (loginData.session) {
            // Actualizar perfil con nombre y apellido
            const fullName = `${firstName} ${lastName}`.trim()
            await updateUserProfileAfterAuth(loginData.session, fullName)
            onAuthSuccess()
            return
          }
        }
        throw error
      }

      if (!data.session) {
        // Si no hay sesión, significa que Supabase requiere confirmación de email
        // Esto NO debería pasar si la confirmación está deshabilitada
        throw new Error('Error: La confirmación de email está habilitada. Por favor, deshabilitála en Supabase Dashboard → Authentication → Settings')
      }

      // Sesión creada inmediatamente (confirmación deshabilitada)
      // Actualizar perfil con nombre y apellido
      const fullName = `${firstName} ${lastName}`.trim()
      await updateUserProfileAfterAuth(data.session, fullName)
      onAuthSuccess()
    } catch (err) {
      onAuthError(err instanceof Error ? err.message : 'Error creando cuenta')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleExpandPassword = () => {
    setShowPasswordSection(true)
    setTimeout(() => passwordInputRef.current?.focus(), 0)
  }

  const handleCloseCancelConfirm = () => setShowCancelConfirm(false)
  const handleConfirmCancel = () => {
    setShowCancelConfirm(false)
    onClose()
  }

  const updateUserProfileAfterAuth = async (session: any, fullName: string) => {
    try {
      // Sincronizar usuario con backend primero
      const { syncUser } = await import('@/lib/api')
      const metadata = session.user.user_metadata || {}
      const appMetadata = session.user.app_metadata || {}
      const providers = appMetadata.providers || []
      const authProvider = providers.length > 0 ? providers[0] : 'supabase'

      const syncResponse = await syncUser({
        supabase_user_id: session.user.id,
        email: session.user.email || email,
        name: fullName, // Usar el nombre completo proporcionado
        auth_provider: authProvider,
        metadata: {
          avatar_url: metadata.avatar_url,
          ...metadata,
        },
      })

      // Actualizar perfil en backend
      if (syncResponse.user_id) {
        await updateUserProfile(syncResponse.user_id, firstName, lastName, session.access_token)
      }
    } catch (err) {
      console.warn('Error actualizando perfil:', err)
      // No fallar el flujo si la actualización de perfil falla
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Completá tu perfil para continuar</h2>
        <p className="text-sm text-gray-600 mb-6">
          Necesitamos algunos datos para crear tu cuenta.
        </p>

        <div className="space-y-4">
          {/* Nombre y Apellido */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="invite-firstName" className="block text-sm font-medium text-gray-700 mb-1">
                Nombre
              </label>
              <input
                id="invite-firstName"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Tu nombre"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
                autoFocus
                aria-required="true"
              />
            </div>
            <div>
              <label htmlFor="invite-lastName" className="block text-sm font-medium text-gray-700 mb-1">
                Apellido
              </label>
              <input
                id="invite-lastName"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Tu apellido"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
                aria-required="true"
              />
            </div>
          </div>

          {/* Google - CTA principal (estilo estándar: fondo claro, borde) */}
          <button
            type="button"
            onClick={handleGoogle}
            disabled={authLoading}
            className="w-full px-4 py-3 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center gap-2 text-gray-800 shadow-sm"
            aria-label="Continuar con Google"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden>
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continuar con Google
          </button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-gray-500">O</span>
            </div>
          </div>

          {/* Contraseña: colapsada por defecto */}
          {!showPasswordSection ? (
            <div>
              <button
                type="button"
                onClick={handleExpandPassword}
                className="text-sm text-blue-600 hover:text-blue-700 hover:underline font-medium"
                aria-expanded="false"
                aria-controls="invite-password-section"
              >
                Crear contraseña
              </button>
            </div>
          ) : (
            <div id="invite-password-section" role="region" aria-label="Crear contraseña">
              <form onSubmit={handleCreateAccount} className="space-y-3">
                <input
                  ref={passwordInputRef}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Crear contraseña"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  autoComplete="new-password"
                />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirmar contraseña"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  autoComplete="new-password"
                />
                <button
                  type="submit"
                  disabled={authLoading || !canSubmitPassword}
                  className={`w-full px-4 py-2 rounded-md font-medium disabled:opacity-50 disabled:cursor-not-allowed ${
                    canSubmitPassword
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {authLoading ? 'Creando cuenta...' : 'Crear cuenta y entrar'}
                </button>
              </form>
            </div>
          )}
        </div>

        <p className="mt-4 text-xs text-gray-500">
          Podés cambiar estos datos más adelante desde tu perfil.
        </p>

        <button
          type="button"
          onClick={() => setShowCancelConfirm(true)}
          className="mt-3 text-sm text-gray-500 hover:text-gray-700"
        >
          Cancelar
        </button>
      </div>

      {/* Confirmación al cancelar */}
      {showCancelConfirm && (
        <div className="absolute inset-0 flex items-center justify-center z-[60] bg-black/30" role="dialog" aria-modal="true" aria-labelledby="cancel-dialog-title">
          <div className="bg-white rounded-lg p-6 max-w-sm w-full mx-4 shadow-xl">
            <h3 id="cancel-dialog-title" className="text-lg font-semibold text-gray-900 mb-2">
              ¿Salir del registro?
            </h3>
            <p className="text-sm text-gray-600 mb-6">
              Podés aceptar la invitación más tarde desde el enlace del email.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleConfirmCancel}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 font-medium text-gray-700"
              >
                Salir
              </button>
              <button
                type="button"
                onClick={handleCloseCancelConfirm}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
              >
                Volver
              </button>
            </div>
          </div>
        </div>
      )}
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
        
        // Verificar si la invitación está expirada o ya aceptada
        if (data.status === 'accepted') {
          setError('Esta invitación ya fue aceptada')
        } else if (data.status === 'expired') {
          setError('Esta invitación ha expirado. Por favor, solicitá una nueva invitación.')
        }
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

        // Si hay un perfil pendiente de actualizar (desde OAuth), actualizarlo
        const pendingProfile = localStorage.getItem('pending_profile_update')
        if (pendingProfile && session) {
          try {
            const { firstName, lastName } = JSON.parse(pendingProfile)
            const fullName = `${firstName} ${lastName}`.trim()
            
            // Sincronizar usuario con backend
            const { syncUser } = await import('@/lib/api')
            const metadata = session.user.user_metadata || {}
            const appMetadata = session.user.app_metadata || {}
            const providers = appMetadata.providers || []
            const authProvider = providers.length > 0 ? providers[0] : 'supabase'

            const syncResponse = await syncUser({
              supabase_user_id: session.user.id,
              email: session.user.email || invitation.email,
              name: fullName,
              auth_provider: authProvider,
              metadata: {
                avatar_url: metadata.avatar_url,
                ...metadata,
              },
            })

            // Actualizar perfil en backend
            if (syncResponse.user_id && authToken) {
              await updateUserProfile(syncResponse.user_id, firstName, lastName, authToken)
            }
            
            localStorage.removeItem('pending_profile_update')
          } catch (err) {
            console.warn('Error actualizando perfil pendiente:', err)
          }
        }

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

  // Verificar autenticación cuando se carga la invitación
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
      }
    }

    checkAuth()
    
    // Escuchar cambios en la sesión de Supabase
    const supabase = createClient()
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user && invitation) {
        const userEmail = session.user.email
        if (userEmail?.toLowerCase() === invitation.email.toLowerCase()) {
          setIsAuthenticated(true)
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

    // Verificar si el email existe en nuestra DB local
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
      localStorage.removeItem('pending_profile_update')
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
      owner: 'Dueño',
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

          <div className="space-y-3">
            <button
              onClick={isAuthenticated ? handleAcceptInvitation : handleAcceptClick}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
            >
              Aceptar invitación
            </button>
            {isAuthenticated && (
              <button
                onClick={handleSignOut}
                className="w-full text-sm text-gray-500 hover:text-gray-700 hover:underline"
              >
                ¿No sos esta persona? Cerrar sesión
              </button>
            )}
          </div>
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
