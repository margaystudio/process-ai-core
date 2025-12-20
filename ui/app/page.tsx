'use client'

import Link from 'next/link'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import FolderTree from '@/components/processes/FolderTree'

export default function Home() {
  const { selectedWorkspaceId, selectedWorkspace, workspaces } = useWorkspace()

  return (
    <main className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Dashboard</h1>
          <p className="text-gray-600">
            Generación automática de documentación de procesos y recetas
          </p>
        </div>
        
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

            {/* Información del workspace actual */}
            {selectedWorkspace && (
              <div className="bg-white p-4 rounded-lg border border-gray-200 mb-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-700">Workspace actual:</p>
                    <p className="text-lg font-semibold text-gray-900">{selectedWorkspace.name}</p>
                  </div>
                  <div className="text-sm text-gray-500">
                    {selectedWorkspace.country && (
                      <span className="inline-block px-2 py-1 bg-gray-100 rounded">
                        {selectedWorkspace.country}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Columna derecha: Gestión de carpetas */}
          <div className="lg:col-span-1">
            {selectedWorkspaceId ? (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Estructura de Carpetas</h3>
                <FolderTree
                  workspaceId={selectedWorkspaceId}
                  showSelectable={false}
                  showCrud={true}
                />
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-sm text-gray-500 text-center py-8">
                  Selecciona un workspace en el header para ver la estructura de carpetas
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}

