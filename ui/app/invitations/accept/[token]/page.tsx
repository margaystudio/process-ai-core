'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { acceptInvitationByToken } from '@/lib/api'
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)

  const token = params?.token as string

  useEffect(() => {
    // Verificar si el usuario está autenticado
    if (!userId) {
      // Redirigir a login con redirect
      router.push(`/login?redirect=/invitations/accept/${token}`)
      return
    }

    // Si hay token y usuario, intentar aceptar automáticamente
    if (token && userId) {
      handleAccept()
    }
  }, [token, userId])

  const handleAccept = async () => {
    if (!token || !userId) {
      setError('Token o usuario no válido')
      return
    }

    await withLoading(async () => {
      try {
        setLoading(true)
        setError(null)

        const result = await acceptInvitationByToken(token, userId)
        setWorkspaceId(result.workspace_id)
        setSuccess(true)

        // Refrescar workspaces
        await refreshWorkspaces()

        // Redirigir al workspace después de 2 segundos
        setTimeout(() => {
          router.push(`/workspace`)
        }, 2000)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al aceptar invitación')
      } finally {
        setLoading(false)
      }
    })
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
              Has sido agregado exitosamente al workspace. Redirigiendo...
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
            Has sido invitado a unirte a un workspace. ¿Deseas aceptar la invitación?
          </p>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex justify-center space-x-4">
            <button
              onClick={handleAccept}
              disabled={loading || !userId}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md disabled:opacity-50"
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
      </div>
    </div>
  )
}


