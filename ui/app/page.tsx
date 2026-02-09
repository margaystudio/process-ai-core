'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import { useUserValidation } from '@/hooks/useUserValidation'
import { createClient } from '@/lib/supabase/client'
import { getPendingInvitationsByEmail } from '@/lib/api'

export default function Home() {
  const router = useRouter()
  const { selectedWorkspaceId, loading: workspaceLoading } = useWorkspace()
  const { role, loading: roleLoading } = useUserRole()
  const userValidation = useUserValidation()
  const [authLoading, setAuthLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [checkingInvitations, setCheckingInvitations] = useState(false)

  // Verificar autenticación primero
  useEffect(() => {
    let isMounted = true
    
    async function checkAuth() {
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

        // Si Supabase no está configurado, permitir acceso (modo desarrollo)
        if (!supabaseUrl || !supabaseKey) {
          console.log('Supabase no configurado, permitiendo acceso')
          if (isMounted) {
            setIsAuthenticated(true)
            setAuthLoading(false)
          }
          return
        }

        console.log('Verificando sesión de Supabase...')
        const supabase = createClient()
        
        // Agregar timeout para evitar que se cuelgue
        const timeoutId = setTimeout(() => {
          console.error('Timeout verificando autenticación (5 segundos)')
          if (isMounted) {
            setAuthLoading(false)
            router.push('/login')
          }
        }, 5000)
        
        try {
          const { data: { session }, error } = await supabase.auth.getSession()
          clearTimeout(timeoutId)
          
          if (error) {
            console.error('Error obteniendo sesión:', error)
            if (isMounted) {
              router.push('/login')
            }
            return
          }
          
          console.log('Sesión obtenida:', session ? 'Sí' : 'No')
          
          if (!isMounted) {
            console.log('Componente desmontado, cancelando')
            return
          }
          
          if (session?.user) {
            console.log('Usuario autenticado, estableciendo estado...')
            setIsAuthenticated(true)
            console.log('Estado de autenticación establecido')
          } else {
            console.log('No hay usuario en la sesión, redirigiendo a login')
            // No autenticado, redirigir a login
            router.push('/login')
            return
          }
        } catch (sessionError) {
          clearTimeout(timeoutId)
          throw sessionError
        }
      } catch (err) {
        console.error('Error verificando autenticación:', err)
        // Si hay error, redirigir a login por seguridad
        if (isMounted) {
          router.push('/login')
        }
      } finally {
        if (isMounted) {
          setAuthLoading(false)
        }
      }
    }

    checkAuth()
    
    return () => {
      isMounted = false
    }
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
      console.log('Usuario no válido, mostrando error')
      // El error se mostrará en el render
      return
    }

    console.log('Usuario válido, verificando workspaces...')
    
    // Si el usuario no tiene workspaces, verificar si hay invitaciones pendientes
    if (userValidation.hasWorkspaces === false) {
      console.log('Usuario no tiene workspaces, verificando invitaciones...')
      // Solo verificar una vez
      if (checkingInvitations) {
        return
      }
      
      // Verificar si hay invitaciones pendientes
      async function checkPendingInvitations() {
        setCheckingInvitations(true)
        try {
          const supabase = createClient()
          const { data: { session } } = await supabase.auth.getSession()
          
          if (!session?.user?.email) {
            console.log('No hay email en la sesión, redirigiendo a onboarding')
            router.push('/onboarding')
            return
          }
          
          console.log('Verificando invitaciones pendientes para:', session.user.email)
          const invitations = await getPendingInvitationsByEmail(session.user.email)
          console.log('Invitaciones encontradas:', invitations.length)
          
          if (invitations.length > 0) {
            // Hay invitaciones pendientes, redirigir a la primera
            const invitation = invitations[0]
            
            // Intentar usar el token directamente si está disponible
            let token = invitation.token
            
            // Si no está disponible, extraerlo de la URL
            if (!token && invitation.invitation_url) {
              const urlParts = invitation.invitation_url.split('/invitations/accept/')
              if (urlParts.length > 1) {
                token = urlParts[1].split('?')[0].split('#')[0] // Remover query params y hash
              }
            }
            
            console.log('Token de invitación:', token)
            
            if (token) {
              router.push(`/invitations/accept/${token}`)
              return
            }
            
            // Si no se pudo obtener el token, redirigir a onboarding
            console.warn('No se pudo obtener el token de la invitación, redirigiendo a onboarding')
            router.push('/onboarding')
            return
          }
          
          // No hay invitaciones pendientes
          // Verificar si el usuario es superadmin antes de redirigir a onboarding
          const isSuperadmin = workspaces.some(ws => ws.workspace_type === 'system')
          
          if (isSuperadmin) {
            console.log('Usuario es superadmin, redirigiendo a /clients')
            router.push('/clients')
          } else {
            console.log('No hay invitaciones pendientes, redirigiendo a onboarding')
            router.push('/onboarding')
          }
        } catch (err) {
          console.error('Error verificando invitaciones pendientes:', err)
          // Si hay error, verificar si es superadmin antes de redirigir
          const isSuperadmin = workspaces.some(ws => ws.workspace_type === 'system')
          if (isSuperadmin) {
            router.push('/clients')
          } else {
            router.push('/onboarding')
          }
        } finally {
          setCheckingInvitations(false)
        }
      }
      
      checkPendingInvitations()
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
  }, [authLoading, isAuthenticated, userValidation, workspaceLoading, selectedWorkspaceId, roleLoading, role, router, checkingInvitations])

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
          {authLoading
            ? 'Verificando autenticación...'
            : userValidation.isValid === null
            ? 'Validando usuario...'
            : checkingInvitations
            ? 'Verificando invitaciones...'
            : 'Determinando tu rol...'}
        </p>
        {authLoading && (
          <p className="text-sm text-gray-500 mt-2">
            Si esto tarda mucho, verifica la consola del navegador
          </p>
        )}
      </div>
    </div>
  )
}
