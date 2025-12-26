'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { syncUser } from '@/lib/api'

type AuthMethod = 'password' | 'otp' | 'oauth'

export default function LoginPage() {
  const router = useRouter()
  const [supabaseConfigured, setSupabaseConfigured] = useState(false)
  
  const [authMethod, setAuthMethod] = useState<AuthMethod>('password')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    // Verificar si Supabase está configurado
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    setSupabaseConfigured(!!(url && key))
    
    if (!url || !key) {
      setError('Supabase no está configurado. Por favor, configura NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY en .env.local')
    }
  }, [])

  const getSupabaseClient = () => {
    try {
      return createClient()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creando cliente de Supabase')
      return null
    }
  }
  
  // Email + Password
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  
  // OTP
  const [otpEmail, setOtpEmail] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [otpSent, setOtpSent] = useState(false)

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setMessage(null)

    const supabase = getSupabaseClient()
    if (!supabase) {
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
        // Sincronizar usuario con backend
        await syncUserToBackend(data.user)
        router.push('/workspace')
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
    setMessage(null)

    const supabase = getSupabaseClient()
    if (!supabase) {
      setLoading(false)
      return
    }

    try {
      const { error } = await supabase.auth.signInWithOtp({
        email: otpEmail,
        options: {
          emailRedirectTo: `${window.location.origin}/auth/callback`,
        },
      })

      if (error) throw error

      setOtpSent(true)
      setMessage('Código enviado a tu email. Revisa tu bandeja de entrada.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al enviar código')
    } finally {
      setLoading(false)
    }
  }

  const handleOtpVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setMessage(null)

    const supabase = getSupabaseClient()
    if (!supabase) {
      setLoading(false)
      return
    }

    try {
      const { data, error } = await supabase.auth.verifyOtp({
        email: otpEmail,
        token: otpCode,
        type: 'email',
      })

      if (error) throw error

      if (data.user) {
        // Sincronizar usuario con backend
        await syncUserToBackend(data.user)
        router.push('/workspace')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Código inválido')
    } finally {
      setLoading(false)
    }
  }

  const handleOAuthLogin = async (provider: 'google' | 'facebook') => {
    setLoading(true)
    setError(null)

    const supabase = getSupabaseClient()
    if (!supabase) {
      setLoading(false)
      return
    }

    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      })

      if (error) throw error
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión')
      setLoading(false)
    }
  }

  const syncUserToBackend = async (user: any) => {
    try {
      // Obtener metadata del usuario
      const metadata = user.user_metadata || {}
      const appMetadata = user.app_metadata || {}
      
      // Determinar proveedor de autenticación
      const providers = appMetadata.providers || []
      const authProvider = providers.length > 0 ? providers[0] : 'supabase'

      const syncResponse = await syncUser({
        supabase_user_id: user.id,
        email: user.email || '',
        name: metadata.name || metadata.full_name || user.email?.split('@')[0] || 'Usuario',
        auth_provider: authProvider,
        metadata: {
          avatar_url: metadata.avatar_url,
          ...metadata,
        },
      })
      
      // Guardar el userId local para uso en el frontend
      if (syncResponse.user_id) {
        localStorage.setItem('local_user_id', syncResponse.user_id)
      }
    } catch (err) {
      console.error('Error sincronizando usuario:', err)
      // No lanzar error, el usuario ya está autenticado en Supabase
    }
  }

  if (!supabaseConfigured) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-yellow-900 mb-2">
              Supabase no configurado
            </h2>
            <p className="text-yellow-800 mb-4">
              Para usar la autenticación, necesitas configurar Supabase:
            </p>
            <ol className="list-decimal list-inside text-yellow-800 space-y-2 text-sm">
              <li>Crea un proyecto en <a href="https://supabase.com" target="_blank" rel="noopener noreferrer" className="underline">supabase.com</a></li>
              <li>Obtén tu URL y anon key desde el dashboard</li>
              <li>Agrega las variables a <code className="bg-yellow-100 px-1 rounded">ui/.env.local</code>:
                <pre className="mt-2 bg-yellow-100 p-2 rounded text-xs overflow-x-auto">
{`NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=tu-anon-key`}
                </pre>
              </li>
              <li>Reinicia el servidor de desarrollo</li>
            </ol>
            <p className="mt-4 text-xs text-yellow-700">
              Ver <code className="bg-yellow-100 px-1 rounded">docs/AUTH_SETUP.md</code> para más detalles.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Iniciar Sesión
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Elige un método de autenticación
          </p>
        </div>

        {/* Selector de método */}
        <div className="flex gap-2 justify-center">
          <button
            onClick={() => {
              setAuthMethod('password')
              setError(null)
              setMessage(null)
            }}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              authMethod === 'password'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Email + Password
          </button>
          <button
            onClick={() => {
              setAuthMethod('otp')
              setError(null)
              setMessage(null)
            }}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              authMethod === 'otp'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Magic Link / OTP
          </button>
          <button
            onClick={() => {
              setAuthMethod('oauth')
              setError(null)
              setMessage(null)
            }}
            className={`px-4 py-2 rounded-md text-sm font-medium ${
              authMethod === 'oauth'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            OAuth
          </button>
        </div>

        {/* Mensajes */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}
        {message && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
            {message}
          </div>
        )}

        {/* Formulario Email + Password */}
        {authMethod === 'password' && (
          <form onSubmit={handlePasswordLogin} className="mt-8 space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="tu@email.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="••••••••"
              />
            </div>
            <div>
              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
              </button>
            </div>
          </form>
        )}

        {/* Formulario OTP / Magic Link */}
        {authMethod === 'otp' && (
          <div className="mt-8 space-y-6">
            {!otpSent ? (
              <form onSubmit={handleOtpSend}>
                <div>
                  <label htmlFor="otp-email" className="block text-sm font-medium text-gray-700">
                    Email
                  </label>
                  <input
                    id="otp-email"
                    name="otp-email"
                    type="email"
                    required
                    value={otpEmail}
                    onChange={(e) => setOtpEmail(e.target.value)}
                    className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    placeholder="tu@email.com"
                  />
                </div>
                <div className="mt-4">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    {loading ? 'Enviando...' : 'Enviar Código / Magic Link'}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleOtpVerify}>
                <div>
                  <label htmlFor="otp-code" className="block text-sm font-medium text-gray-700">
                    Código OTP
                  </label>
                  <input
                    id="otp-code"
                    name="otp-code"
                    type="text"
                    required
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Ingresa el código"
                  />
                  <p className="mt-2 text-sm text-gray-500">
                    O haz click en el link que recibiste por email
                  </p>
                </div>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setOtpSent(false)
                      setOtpCode('')
                      setMessage(null)
                    }}
                    className="flex-1 py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    Volver
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    {loading ? 'Verificando...' : 'Verificar'}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* OAuth */}
        {authMethod === 'oauth' && (
          <div className="mt-8 space-y-4">
            <button
              onClick={() => handleOAuthLogin('google')}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
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
            {/* Facebook puede agregarse más adelante */}
          </div>
        )}
      </div>
    </div>
  )
}

