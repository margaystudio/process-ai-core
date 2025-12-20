'use client'

import { useState, useEffect } from 'react'
import { listWorkspaces, WorkspaceResponse } from '@/lib/api'
import FolderTree from '@/components/processes/FolderTree'

export default function Home() {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>('')

  useEffect(() => {
    async function loadWorkspaces() {
      try {
        const data = await listWorkspaces()
        setWorkspaces(data)
        if (data.length > 0) {
          setSelectedWorkspaceId(data[0].id)
        }
      } catch (err) {
        console.error('Error cargando workspaces:', err)
      }
    }
    loadWorkspaces()
  }, [])

  return (
    <main className="min-h-screen p-8 bg-gray-50">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold mb-4">Process AI Core</h1>
        <p className="text-gray-600 mb-8">
          Generación automática de documentación de procesos y recetas
        </p>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Columna izquierda: Acciones */}
          <div className="lg:col-span-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <a
                href="/clients/new"
                className="p-6 border rounded-lg hover:bg-white transition bg-white"
              >
                <h2 className="text-xl font-semibold mb-2">Nuevo Cliente</h2>
                <p className="text-gray-600">
                  Registra una nueva organización/cliente en el sistema
                </p>
              </a>
              
              <a
                href="/processes/new"
                className="p-6 border rounded-lg hover:bg-white transition bg-white"
              >
                <h2 className="text-xl font-semibold mb-2">Nuevo Proceso</h2>
                <p className="text-gray-600">
                  Crea documentación de procesos desde audio, video e imágenes
                </p>
              </a>
            </div>

            {/* Selector de workspace */}
            {workspaces.length > 0 && (
              <div className="bg-white p-4 rounded-lg border border-gray-200 mb-6">
                <label htmlFor="workspace-select" className="block text-sm font-medium text-gray-700 mb-2">
                  Ver estructura de carpetas para:
                </label>
                <select
                  id="workspace-select"
                  value={selectedWorkspaceId}
                  onChange={(e) => setSelectedWorkspaceId(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {workspaces.map((ws) => (
                    <option key={ws.id} value={ws.id}>
                      {ws.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Columna derecha: Gestión de carpetas */}
          <div className="lg:col-span-1">
            {selectedWorkspaceId && (
              <FolderTree
                workspaceId={selectedWorkspaceId}
                showSelectable={false}
                showCrud={true}
              />
            )}
          </div>
        </div>
      </div>
    </main>
  )
}

