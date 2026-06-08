'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import { useUserValidation } from '@/hooks/useUserValidation'
import { createClient } from '@/lib/supabase/client'
import { Card, CardBody, Badge, Button } from '@/shared/ui/components'

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
      <div className="flex min-h-[70vh] items-center justify-center p-6">
        <Card className="w-full max-w-md border-danger-bd">
          <CardBody className="space-y-3">
            <Badge variant="danger">Sin acceso</Badge>
            <h2 className="text-h2 text-ink-900">Acceso no autorizado</h2>
            <p className="text-body text-ink-700">
              {userValidation.error || 'Tu usuario no está registrado en el sistema.'}
            </p>
            <p className="text-sm text-ink-500">
              Si creés que esto es un error, contactá al administrador del sistema.
            </p>
            <Button
              variant="secondary"
              className="w-full"
              onClick={async () => {
                const supabase = createClient()
                await supabase.auth.signOut()
                router.push('/login')
              }}
            >
              Cerrar sesión
            </Button>
          </CardBody>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-6">
      <div className="text-center">
        <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-[3px] border-ink-200 border-t-accent" />
        <p className="text-sm text-ink-600">
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
