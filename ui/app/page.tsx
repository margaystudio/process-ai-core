'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import { useUserValidation } from '@/hooks/useUserValidation'
import { createClient } from '@/lib/supabase/client'
import { redirectToHubLogin } from '@/lib/hub-login'
import { clearLocalAuthState } from '@/lib/clear-auth-state'
import { Card, CardBody, Badge, Button } from '@/shared/ui/components'

export default function Home() {
  const router = useRouter()
  const { selectedWorkspaceId, loading: workspaceLoading } = useWorkspace()
  const { role, loading: roleLoading } = useUserRole()
  const userValidation = useUserValidation()

  // El middleware ya validó la sesión SSO. Acá solo enrutamos según rol/workspace.
  useEffect(() => {
    if (userValidation.isValid === null) return
    if (userValidation.isValid === false) return

    if (workspaceLoading) return
    if (!selectedWorkspaceId) {
      router.push('/workspace')
      return
    }

    if (roleLoading) return

    if (role === 'owner' || role === 'admin' || role === 'approver') {
      router.push('/dashboard/approval-queue')
    } else if (role === 'creator') {
      router.push('/dashboard/to-review')
    } else if (role === 'viewer') {
      router.push('/dashboard/view')
    } else {
      router.push('/workspace')
    }
  }, [userValidation, workspaceLoading, selectedWorkspaceId, roleLoading, role, router])

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
                clearLocalAuthState()
                redirectToHubLogin(false)
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
          {userValidation.isValid === null
            ? 'Cargando tu perfil...'
            : roleLoading
            ? 'Determinando tu rol...'
            : 'Redirigiendo...'}
        </p>
      </div>
    </div>
  )
}
