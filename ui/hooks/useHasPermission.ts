'use client'

import { useState, useEffect } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from './useUserRole'
import { useUserId } from './useUserId'
import { checkPermission } from '@/lib/api'

/**
 * Hook para verificar si el usuario tiene un permiso específico.
 * 
 * Primero intenta verificar con el backend (más seguro).
 * Si falla, usa un mapeo de roles a permisos como fallback.
 * 
 * @param permissionName - Nombre del permiso (ej: "workspaces.edit", "documents.approve")
 * @returns { hasPermission: boolean, loading: boolean }
 */
export function useHasPermission(permissionName: string): { hasPermission: boolean; loading: boolean } {
  const { selectedWorkspaceId } = useWorkspace()
  const { role } = useUserRole()
  const userId = useUserId()
  const [hasPermission, setHasPermission] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function checkPerm() {
      if (!selectedWorkspaceId || !userId) {
        setHasPermission(false)
        setLoading(false)
        return
      }

      try {
        // Intentar verificar con el backend (más seguro)
        const result = await checkPermission(userId, selectedWorkspaceId, permissionName)
        setHasPermission(result.has_permission)
      } catch (err) {
        console.warn(`[useHasPermission] Error verificando permiso con backend, usando fallback:`, err)
        // Fallback: mapeo de roles a permisos basado en seed_permissions.py
        const hasPerm = checkPermissionByRole(role, permissionName)
        setHasPermission(hasPerm)
      } finally {
        setLoading(false)
      }
    }

    checkPerm()
  }, [selectedWorkspaceId, userId, role, permissionName])

  return { hasPermission, loading }
}

/**
 * Mapeo de roles a permisos (basado en tools/seed_permissions.py).
 * 
 * Este es un fallback si el backend no está disponible.
 * En producción, siempre se debe usar el backend.
 */
function checkPermissionByRole(role: string | null, permissionName: string): boolean {
  if (!role) return false

  // Owner y Admin tienen todos los permisos
  if (role === 'owner' || role === 'admin') {
    return true
  }

  // Superadmin tiene todos los permisos
  if (role === 'superadmin') {
    return true
  }

  // Mapeo específico por rol
  const rolePermissions: Record<string, string[]> = {
    approver: [
      'documents.view',
      'documents.export',
      'documents.approve',
      'documents.reject',
      'workspaces.view',
    ],
    creator: [
      'documents.create',
      'documents.view',
      'documents.edit',
      'documents.export',
      'workspaces.view',
      'workspaces.manage_folders',
    ],
    viewer: [
      'documents.view',
      'documents.export',
      'workspaces.view',
    ],
  }

  const permissions = rolePermissions[role] || []
  return permissions.includes(permissionName)
}

/**
 * Hook helper para verificar si el usuario puede editar el workspace.
 */
export function useCanEditWorkspace() {
  return useHasPermission('workspaces.edit')
}

/**
 * Hook helper para verificar si el usuario puede gestionar usuarios.
 */
export function useCanManageUsers() {
  return useHasPermission('workspaces.manage_users')
}

/**
 * Hook helper para verificar si el usuario puede aprobar documentos.
 */
export function useCanApproveDocuments() {
  return useHasPermission('documents.approve')
}

/**
 * Hook helper para verificar si el usuario puede rechazar documentos.
 */
export function useCanRejectDocuments() {
  return useHasPermission('documents.reject')
}
