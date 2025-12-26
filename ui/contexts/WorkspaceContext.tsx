'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
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

  const refreshWorkspaces = async () => {
    try {
      setLoading(true)
      
      // Si hay un usuario autenticado, obtener solo sus workspaces
      if (userId) {
        const data = await getUserWorkspaces(userId)
        setWorkspaces(data)
        
        // Si no hay workspace seleccionado pero hay workspaces disponibles, seleccionar el primero
        if (!selectedWorkspaceId && data.length > 0) {
          setSelectedWorkspaceId(data[0].id)
        }
        
        // Si el workspace seleccionado ya no existe, seleccionar el primero disponible
        if (selectedWorkspaceId && !data.find(ws => ws.id === selectedWorkspaceId) && data.length > 0) {
          setSelectedWorkspaceId(data[0].id)
        }
      } else {
        // Si no hay usuario, no hay workspaces
        setWorkspaces([])
        setSelectedWorkspaceId(null)
      }
    } catch (err) {
      console.error('Error cargando workspaces:', err)
      setWorkspaces([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshWorkspaces()
  }, [userId])

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


