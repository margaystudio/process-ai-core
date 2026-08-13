'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react'
import {
  getCurrentUser,
  invalidateCurrentUserCache,
  invalidateMyCapabilitiesCache,
  CurrentUserResponse,
  WorkspaceResponse,
} from '@/lib/api'
import { getActiveTenantId, setActiveTenantId as persistActiveTenantId } from '@/lib/api-auth'

interface WorkspaceContextType {
  workspaces: WorkspaceResponse[]
  selectedWorkspace: WorkspaceResponse | null
  selectedWorkspaceId: string | null
  activeTenantId: string | null
  platformRoles: string[]
  tenantRoles: string[]
  currentUser: { id: string; email: string; name: string | null } | null
  /** Para el switcher de módulos del chrome. TODO(arquitectura): siempre undefined
   *  hasta que el backend lo exponga — ver lib/modules.ts. */
  modules: CurrentUserResponse['modules']
  setActiveTenantId: (tenantId: string) => Promise<void>
  loading: boolean
  refreshWorkspaces: () => Promise<void>
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null)
  const [activeTenantId, setActiveTenantIdState] = useState<string | null>(null)
  const [platformRoles, setPlatformRoles] = useState<string[]>([])
  const [tenantRoles, setTenantRoles] = useState<string[]>([])
  const [currentUser, setCurrentUser] = useState<{ id: string; email: string; name: string | null } | null>(null)
  const [modules, setModules] = useState<CurrentUserResponse['modules']>(undefined)
  const [loading, setLoading] = useState(true)

  const applyCurrentUser = useCallback((data: Awaited<ReturnType<typeof getCurrentUser>>) => {
    const storedTenantId = getActiveTenantId()
    const validTenantIds = new Set(data.workspaces.map((ws) => ws.tenant_id))
    const tenantId =
      storedTenantId && validTenantIds.has(storedTenantId)
        ? storedTenantId
        : data.active_tenant.id

    persistActiveTenantId(tenantId)
    setActiveTenantIdState(tenantId)
    setPlatformRoles(data.platform_roles)
    setTenantRoles(data.tenant_roles)
    setCurrentUser(data.user)
    setWorkspaces(data.workspaces)
    setModules(data.modules)

    const activeWs =
      data.workspaces.find((ws) => ws.tenant_id === tenantId) ??
      data.workspaces.find((ws) => ws.is_active) ??
      data.workspaces[0] ??
      null
    setSelectedWorkspaceId(activeWs?.id ?? null)

    localStorage.setItem('local_user_id', data.user.id)
    window.dispatchEvent(
      new CustomEvent('localStorageChange', { detail: { key: 'local_user_id', value: data.user.id } })
    )
  }, [])

  const refreshWorkspaces = useCallback(async () => {
    try {
      setLoading(true)
      invalidateCurrentUserCache()
      // Las capabilities (permisos + mapa de carpetas) son por tenant activo: si no
      // se invalidan acá, un cambio de tenant puede servir hasta 5s de datos del
      // tenant anterior desde la cache de `getMyCapabilities` (fuga de estado en el
      // cliente; el backend igual autoriza cada request por su cuenta).
      invalidateMyCapabilitiesCache()
      const data = await getCurrentUser({ force: true })
      applyCurrentUser(data)
    } catch (err) {
      console.error('[WorkspaceContext] Error cargando workspaces:', err)
      setWorkspaces([])
      setSelectedWorkspaceId(null)
      setCurrentUser(null)
    } finally {
      setLoading(false)
    }
  }, [applyCurrentUser])

  const setActiveTenantId = useCallback(
    async (tenantId: string) => {
      persistActiveTenantId(tenantId)
      setActiveTenantIdState(tenantId)
      // Actualizar workspace local de inmediato para que la UI (carpetas, docs) recargue
      const ws = workspaces.find((w) => w.tenant_id === tenantId)
      if (ws) setSelectedWorkspaceId(ws.id)
      await refreshWorkspaces()
    },
    [workspaces, refreshWorkspaces]
  )

  useEffect(() => {
    refreshWorkspaces()
  }, [refreshWorkspaces])

  const selectedWorkspace = workspaces.find((ws) => ws.id === selectedWorkspaceId) || null

  // useMemo: sin esto el value es un objeto nuevo en cada render del provider
  // y TODOS los consumidores del contexto re-renderizan aunque nada cambie.
  const value = useMemo(
    () => ({
      workspaces,
      selectedWorkspace,
      selectedWorkspaceId,
      activeTenantId,
      platformRoles,
      tenantRoles,
      currentUser,
      modules,
      setActiveTenantId,
      loading,
      refreshWorkspaces,
    }),
    [
      workspaces,
      selectedWorkspace,
      selectedWorkspaceId,
      activeTenantId,
      platformRoles,
      tenantRoles,
      currentUser,
      modules,
      setActiveTenantId,
      loading,
      refreshWorkspaces,
    ]
  )

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (context === undefined) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider')
  }
  return context
}
