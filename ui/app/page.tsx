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
    let isMounted = true
    
    async function checkAuth() {
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

        if (!supabaseUrl || !supabaseKey) {
          if (isMounted) {
            setIsAuthenticated(true)
            setAuthLoading(false)
          }
          return
        }

        const supabase = createClient()
        
        const timeoutId = setTimeout(() => {
          if (isMounted) {
            setAuthLoading(false)
            router.push('/login')
          }
        }, 6000)
        
        try {
          const { data: { session }, error } = await supabase.auth.getSession()
          clearTimeout(timeoutId)
          
          if (error || !session?.user) {
            if (isMounted) router.push('/login')
            return
          }
          
          if (isMounted) {
            setIsAuthenticated(true)
          }
        } catch (sessionError) {
          clearTimeout(timeoutId)
          throw sessionError
        }
      } catch (err) {
        console.error('Error verificando autenticación:', err)
        if (isMounted) router.push('/login')
      } finally {
        if (isMounted) setAuthLoading(false)
      }
    }

    checkAuth()
    
    return () => {
      isMounted = false
    }
  }, [router])

  // Redirigir según el estado del usuario y su rol
  useEffect(() => {
    if (authLoading || !isAuthenticated) return
    if (userValidation.isValid === null) return
    if (userValidation.isValid === false) return

    // Sin workspace asignado → ir al selector de workspaces
    if (workspaceLoading) return
    if (!selectedWorkspaceId) {
      router.push('/workspace')
      return
    }

    if (roleLoading) return

    // Redirigir según rol
    if (role === 'owner' || role === 'admin' || role === 'approver') {
      router.push('/dashboard/approval-queue')
    } else if (role === 'creator') {
      router.push('/dashboard/to-review')
    } else if (role === 'viewer') {
      router.push('/dashboard/view')
    } else {
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

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">
          {authLoading
            ? 'Verificando autenticación...'
            : userValidation.isValid === null
            ? 'Validando usuario...'
            : 'Determinando tu rol...'}
        </p>
      </div>
    </div>
  )
}
