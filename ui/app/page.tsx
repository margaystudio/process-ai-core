'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'

export default function Home() {
  const router = useRouter()
  const { selectedWorkspaceId } = useWorkspace()
  const { role, loading } = useUserRole()

  useEffect(() => {
    if (loading || !selectedWorkspaceId) {
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
      // Si no tiene rol o es null, mostrar mensaje
      // Por ahora, redirigir a workspace
      router.push('/workspace')
    }
  }, [role, loading, selectedWorkspaceId, router])

  // Mostrar loading mientras se determina el rol
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Determinando tu rol...</p>
      </div>
    </div>
  )
}
