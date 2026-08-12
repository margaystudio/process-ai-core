'use client'

import { useEffect, useState } from 'react'
import { getMyCapabilities, type FolderCapabilities, type MyCapabilities } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

const NO_ACCESS: FolderCapabilities = { view: false, create: false, approve: false }
const UNSCOPED_ACCESS: FolderCapabilities = { view: true, create: true, approve: true }

/**
 * Acceso EFECTIVO por carpeta (`capabilities.folders`, de
 * GET /api/v1/users/me/capabilities): herencia entre carpetas y bypass de
 * owner/admin/superadmin ya resueltos por el backend. Es la primera vez que
 * el front puede saber esto ANTES de intentar la acción — antes se mostraban
 * botones de crear/aprobar en carpetas donde el backend terminaba devolviendo 403.
 *
 * Fail-closed mientras carga o si la carpeta no aparece en el mapa (evita
 * mostrar acciones que el backend va a rechazar). Un `folderId` vacío/`null`
 * (documento o carpeta destino todavía sin definir) NO restringe: la decisión
 * queda en manos del permiso general (`useHasPermission`), no de esta carpeta.
 */
export function useFolderAccess(): {
  canView: (folderId: string | null | undefined) => boolean
  canCreate: (folderId: string | null | undefined) => boolean
  canApprove: (folderId: string | null | undefined) => boolean
  loading: boolean
} {
  const { selectedWorkspaceId, activeTenantId } = useWorkspace()
  const [capabilities, setCapabilities] = useState<MyCapabilities | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getMyCapabilities()
      .then((data) => {
        if (!cancelled) setCapabilities(data)
      })
      .catch(() => {
        if (!cancelled) setCapabilities(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedWorkspaceId, activeTenantId])

  function access(folderId: string | null | undefined): FolderCapabilities {
    if (!folderId) return UNSCOPED_ACCESS
    if (!capabilities) return NO_ACCESS
    return capabilities.folders[folderId] ?? NO_ACCESS
  }

  return {
    canView: (folderId) => access(folderId).view,
    canCreate: (folderId) => access(folderId).create,
    canApprove: (folderId) => access(folderId).approve,
    loading,
  }
}
