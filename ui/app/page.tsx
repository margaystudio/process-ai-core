'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useHasPermission } from '@/hooks/useHasPermission'
import { useUserValidation } from '@/hooks/useUserValidation'
import { createClient } from '@/lib/supabase/client'
import { redirectToHubLogin } from '@/lib/hub-login'
import { clearLocalAuthState } from '@/lib/clear-auth-state'
import { Card, CardBody, Badge, Button } from '@/shared/ui/components'
import { PageListSkeleton } from '@/components/layout/ListSkeleton'

export default function Home() {
  const router = useRouter()
  const { selectedWorkspaceId, loading: workspaceLoading } = useWorkspace()
  const { hasPermission: canApprove, loading: approveLoading } = useHasPermission('documents.approve')
  const { hasPermission: canEdit, loading: editLoading } = useHasPermission('documents.edit')
  const { hasPermission: canView, loading: viewLoading } = useHasPermission('documents.view')
  const permissionsLoading = approveLoading || editLoading || viewLoading
  const userValidation = useUserValidation()

  // El middleware ya validó la sesión SSO. Acá solo enrutamos según permisos/workspace.
  useEffect(() => {
    if (userValidation.isValid === null) return
    if (userValidation.isValid === false) return

    if (workspaceLoading) return
    if (!selectedWorkspaceId) {
      router.push('/workspace')
      return
    }

    if (permissionsLoading) return

    if (canApprove) {
      router.push('/dashboard/approval-queue')
    } else if (canEdit) {
      router.push('/workspace')
    } else if (canView) {
      // Sin documents.edit ni documents.approve: es alguien de solo lectura —
      // el pistero de estación, con el teléfono en una mano. Su pantalla
      // principal es la caja de preguntar a Tyto, no la Biblioteca.
      router.push('/consultar')
    } else {
      router.push('/workspace')
    }
  }, [
    userValidation,
    workspaceLoading,
    selectedWorkspaceId,
    permissionsLoading,
    canApprove,
    canEdit,
    canView,
    router,
  ])

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

  // '/' nunca es un destino final: siempre redirige según permisos (ver efecto arriba).
  // Antes esto era un spinner a pantalla completa — con el shell ya armado (ChromeShell
  // pinta topbar/sidebar al instante, con sus propios skeletons donde falte dato), lo que
  // corresponde acá es el skeleton del contenido, no un spinner: el destino más frecuente
  // es la Biblioteca, así que se usa su misma forma para que la transición no "cambie de
  // idioma visual" a mitad de la carga.
  return <PageListSkeleton />
}
