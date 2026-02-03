'use client'

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { getUserWorkspaces, WorkspaceResponse } from '@/lib/api'
import { useUserId } from '@/hooks/useUserId'

interface WorkspaceContextType {
  workspaces: WorkspaceResponse[]
  selectedWorkspace: WorkspaceResponse | null
  selectedWorkspaceId: string | null
  setSelectedWorkspaceId: (id: string | null) => void
  loading: boolean
  refreshWorkspaces: () => Promise<void>
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const userId = useUserId()

  const refreshWorkspaces = useCallback(async (overrideUserId?: string | null) => {
    try {
      setLoading(true)
      
      // Usar el userId proporcionado o el del hook
      const userIdToUse = overrideUserId !== undefined ? overrideUserId : userId
      
      // Si hay un usuario autenticado, obtener solo sus workspaces
      if (userIdToUse) {
        console.log('[WorkspaceContext] Refrescando workspaces para user_id:', userIdToUse)
        const data = await getUserWorkspaces(userIdToUse)
        console.log('[WorkspaceContext] Workspaces obtenidos:', data.length, data.map(ws => ws.name))
        setWorkspaces(data)
        
        // Si no hay workspace seleccionado pero hay workspaces disponibles, seleccionar el primero
        setSelectedWorkspaceId(prev => {
          if (!prev && data.length > 0) {
            return data[0].id
          }
          // Si el workspace seleccionado ya no existe, seleccionar el primero disponible
          if (prev && !data.find(ws => ws.id === prev) && data.length > 0) {
            return data[0].id
          }
          return prev
        })
      } else {
        // Si no hay usuario, no hay workspaces
        console.log('[WorkspaceContext] No hay userId, limpiando workspaces')
        setWorkspaces([])
        setSelectedWorkspaceId(null)
      }
    } catch (err) {
      console.error('[WorkspaceContext] Error cargando workspaces:', err)
      setWorkspaces([])
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    refreshWorkspaces()
  }, [refreshWorkspaces])

  // También escuchar cambios directos en localStorage para refrescar inmediatamente
  useEffect(() => {
    const handleStorageChange = (e: Event) => {
      const customEvent = e as CustomEvent
      if (customEvent.detail?.key === 'local_user_id' && customEvent.detail?.value) {
        console.log('[WorkspaceContext] Detectado cambio en local_user_id, refrescando workspaces:', customEvent.detail.value)
        // Refrescar con el nuevo userId inmediatamente
        refreshWorkspaces(customEvent.detail.value)
      }
    }

    window.addEventListener('localStorageChange', handleStorageChange as EventListener)

    return () => {
      window.removeEventListener('localStorageChange', handleStorageChange as EventListener)
    }
  }, [refreshWorkspaces]) // Incluir refreshWorkspaces en las dependencias para tener la versión actualizada

  const selectedWorkspace = workspaces.find(ws => ws.id === selectedWorkspaceId) || null

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        selectedWorkspace,
        selectedWorkspaceId,
        setSelectedWorkspaceId,
        loading,
        refreshWorkspaces,
      }}
    >
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


