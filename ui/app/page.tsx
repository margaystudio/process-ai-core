'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import { useUserValidation } from '@/hooks/useUserValidation'
import { createClient } from '@/lib/supabase/client'

export default function Home() {
  const router = useRouter()
  const { selectedWorkspaceId, loading: workspaceLoading } = useWorkspace()
  const { role, loading: roleLoading } = useUserRole()
  const userValidation = useUserValidation()
  const [authLoading, setAuthLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  // Verificar autenticación primero
  useEffect(() => {
    async function checkAuth() {
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

        // Si Supabase no está configurado, permitir acceso (modo desarrollo)
        if (!supabaseUrl || !supabaseKey) {
          setIsAuthenticated(true)
          setAuthLoading(false)
          return
        }

        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()
        
        if (session?.user) {
          setIsAuthenticated(true)
        } else {
          // No autenticado, redirigir a login
          router.push('/login')
          return
        }
      } catch (err) {
        console.error('Error verificando autenticación:', err)
        // Si hay error, redirigir a login por seguridad
        router.push('/login')
        return
      } finally {
        setAuthLoading(false)
      }
    }

    checkAuth()
  }, [router])

  // Verificar validación del usuario y redirigir según el estado
  useEffect(() => {
    // Esperar a que termine la verificación de autenticación
    if (authLoading) {
      return
    }

    // Si no está autenticado, el efecto anterior ya redirigió a login
    if (!isAuthenticated) {
      return
    }

    // Esperar a que termine la validación del usuario
    if (userValidation.isValid === null) {
      return
    }

    // Si el usuario no es válido (no existe en BD local), mostrar error
    if (userValidation.isValid === false) {
      // El error se mostrará en el render
      return
    }

    // Si el usuario no tiene workspaces, redirigir a onboarding
    if (userValidation.hasWorkspaces === false) {
      router.push('/onboarding')
      return
    }

    // Esperar a que se carguen los workspaces
    if (workspaceLoading) {
      return
    }

    // Si no hay workspace seleccionado, redirigir a la página de workspaces
    if (!selectedWorkspaceId) {
      router.push('/workspace')
      return
    }

    // Esperar a que se cargue el rol
    if (roleLoading) {
      return
    }

    // Redirigir según el rol
    if (role === 'owner' || role === 'admin' || role === 'approver') {
      router.push('/dashboard/approval-queue')
    } else if (role === 'creator') {
      router.push('/dashboard/to-review')
    } else if (role === 'viewer') {
      router.push('/dashboard/view')
    } else {
      // Si no tiene rol o es null, redirigir a workspace
      router.push('/workspace')
    }
  }, [authLoading, isAuthenticated, userValidation, workspaceLoading, selectedWorkspaceId, roleLoading, role, router])

  // Mostrar error si el usuario no es válido
  if (userValidation.isValid === false) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-red-900 mb-2">
              Acceso no autorizado
            </h2>
            <p className="text-red-800 mb-4">
              {userValidation.error || 'Tu usuario no está registrado en el sistema.'}
            </p>
            <p className="text-sm text-red-700 mb-4">
              Si crees que esto es un error, por favor contacta al administrador del sistema.
            </p>
            <button
              onClick={async () => {
                const supabase = createClient()
                await supabase.auth.signOut()
                router.push('/login')
              }}
              className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Mostrar loading mientras se verifica autenticación o se determina el rol
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">
          {authLoading || userValidation.isValid === null
            ? 'Verificando autenticación...'
            : 'Determinando tu rol...'}
        </p>
      </div>
    </div>
  )
}
