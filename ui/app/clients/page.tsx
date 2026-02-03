'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { listWorkspaces, WorkspaceResponse } from '@/lib/api'

export default function ClientsPage() {
  const router = useRouter()
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadWorkspaces()
  }, [])

  const loadWorkspaces = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await listWorkspaces()
      setWorkspaces(data)
    } catch (err) {
      console.error('Error cargando espacios de trabajo:', err)
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold">Clientes</h1>
          <Link
            href="/clients/new"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
          >
            + Nuevo Cliente
          </Link>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
            <p className="font-semibold">Error</p>
            <p className="text-sm mt-1">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="bg-white rounded-lg shadow-sm p-8">
            <div className="text-center text-gray-500">Cargando espacios de trabajo...</div>
          </div>
        ) : workspaces.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-8">
            <div className="text-center text-gray-500">
              <p className="text-lg mb-4">No hay espacios de trabajo creados</p>
              <Link
                href="/clients/new"
                className="text-blue-600 hover:text-blue-700 underline"
              >
                Crear el primer espacio de trabajo
              </Link>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden">
            <div className="divide-y divide-gray-200">
              {workspaces.map((workspace) => (
                <div
                  key={workspace.id}
                  className="p-6 hover:bg-gray-50 cursor-pointer"
                  onClick={() => router.push(`/workspace/${workspace.id}/settings`)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{workspace.name}</h3>
                      <p className="text-sm text-gray-500">Slug: {workspace.slug}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        Creado: {new Date(workspace.created_at).toLocaleDateString('es-UY', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          router.push(`/workspace/${workspace.id}/settings`)
                        }}
                        className="px-4 py-2 text-blue-600 hover:text-blue-800 text-sm font-medium border border-blue-600 rounded-md hover:bg-blue-50"
                      >
                        Configurar
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
