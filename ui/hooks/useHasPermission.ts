'use client'

import { useMemo } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from './useUserRole'

/**
 * Verifica permisos usando rol del workspace (GET /users/me) — sin round-trip extra al backend.
 * El rol ya viene sincronizado desde margay-workspace vía sync_workspace_access.
 */
export function useHasPermission(permissionName: string): { hasPermission: boolean; loading: boolean } {
  const { platformRoles, tenantRoles, loading } = useWorkspace()
  const { role, loading: roleLoading } = useUserRole()

  const hasPermission = useMemo(() => {
    if (platformRoles.includes('superadmin')) return true
    if (tenantRoles.includes('tenant_admin')) return true
    if (role === 'owner' || role === 'admin') return true
    return checkPermissionByRole(role, permissionName)
  }, [role, platformRoles, tenantRoles, permissionName])

  return { hasPermission, loading: loading || roleLoading }
}

function checkPermissionByRole(role: string | null, permissionName: string): boolean {
  if (!role) return false

  if (role === 'superadmin') return true

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
    viewer: ['documents.view', 'documents.export', 'workspaces.view'],
  }

  return (rolePermissions[role] || []).includes(permissionName)
}

export function useCanEditWorkspace() {
  return useHasPermission('workspaces.edit')
}

export function useCanManageUsers() {
  return useHasPermission('workspaces.manage_users')
}

export function useCanApproveDocuments() {
  return useHasPermission('documents.approve')
}

export function useCanRejectDocuments() {
  return useHasPermission('documents.reject')
}
