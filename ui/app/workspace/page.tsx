'use client'

import { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { listDocuments, Document } from '@/lib/api'
import FolderTree from '@/components/processes/FolderTree'

export default function WorkspacePage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)

  // Cargar documentos
  useEffect(() => {
    async function loadDocuments() {
      if (!selectedWorkspaceId) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const docs = await listDocuments(
          selectedWorkspaceId,
          selectedFolderId || undefined,
          'process' // Solo procesos por ahora
        )
        setDocuments(docs)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
        setDocuments([])
      } finally {
        setLoading(false)
      }
    }

    loadDocuments()
  }, [selectedWorkspaceId, selectedFolderId])

  // Filtrar documentos por búsqueda
  const filteredDocuments = useMemo(() => {
    if (!searchQuery.trim()) {
      return documents
    }

    const query = searchQuery.toLowerCase()
    return documents.filter(
      (doc) =>
        doc.name.toLowerCase().includes(query) ||
        doc.description.toLowerCase().includes(query)
    )
  }, [documents, searchQuery])

  if (!selectedWorkspaceId) {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
            <p className="text-yellow-800">
              Por favor, selecciona un workspace en el header para ver sus documentos.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {selectedWorkspace?.name || 'Workspace'}
              </h1>
              <p className="text-gray-600 mt-1">
                Gestión de documentos y estructura de carpetas
              </p>
            </div>
            <Link
              href="/processes/new"
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
            >
              + Nuevo Proceso
            </Link>
          </div>

          {/* Barra de búsqueda */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div>
              <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
                Buscar documentos
              </label>
              <input
                id="search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por nombre o descripción..."
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Filtro de carpeta activo */}
            {selectedFolderId && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">
                    Filtrando por carpeta seleccionada
                  </span>
                  <button
                    onClick={() => setSelectedFolderId(null)}
                    className="text-sm text-blue-600 hover:text-blue-700"
                  >
                    Limpiar filtro
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Contenido principal */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Columna izquierda: Estructura de carpetas */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg border border-gray-200 p-4 sticky top-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Estructura de Carpetas
              </h2>
              <FolderTree
                workspaceId={selectedWorkspaceId}
                selectedFolderId={selectedFolderId || undefined}
                onSelectFolder={(id) => setSelectedFolderId(id)}
                showSelectable={true}
                showCrud={false}
              />
            </div>
          </div>

          {/* Columna derecha: Lista de documentos */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              {loading ? (
                <div className="text-center py-12">
                  <div className="animate-pulse text-gray-500">Cargando documentos...</div>
                </div>
              ) : error ? (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <p className="text-red-700">Error: {error}</p>
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500 mb-4">
                    {searchQuery
                      ? 'No se encontraron documentos que coincidan con la búsqueda'
                      : selectedFolderId
                      ? 'No hay documentos en esta carpeta'
                      : 'No hay documentos en este workspace'}
                  </p>
                  {!searchQuery && (
                    <Link
                      href="/processes/new"
                      className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      Crear primer documento
                    </Link>
                  )}
                </div>
              ) : (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">
                      Documentos ({filteredDocuments.length})
                    </h2>
                  </div>
                  <div className="space-y-3">
                    {filteredDocuments.map((doc) => (
                      <Link
                        key={doc.id}
                        href={`/documents/${doc.id}`}
                        className="block border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-md transition"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <h3 className="text-lg font-semibold text-gray-900">
                                {doc.name}
                              </h3>
                              <span
                                className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  doc.status === 'active'
                                    ? 'bg-green-100 text-green-800'
                                    : doc.status === 'archived'
                                    ? 'bg-gray-100 text-gray-800'
                                    : 'bg-yellow-100 text-yellow-800'
                                }`}
                              >
                                {doc.status === 'active'
                                  ? 'Activo'
                                  : doc.status === 'archived'
                                  ? 'Archivado'
                                  : 'Borrador'}
                              </span>
                            </div>
                            {doc.description && (
                              <p className="text-sm text-gray-600 mb-2 line-clamp-2">
                                {doc.description}
                              </p>
                            )}
                            <div className="flex items-center gap-4 text-xs text-gray-500">
                              <span>
                                Creado: {new Date(doc.created_at).toLocaleDateString('es-UY')}
                              </span>
                              <span className="capitalize">{doc.document_type}</span>
                            </div>
                          </div>
                          <div className="ml-4">
                            <span className="text-gray-400">→</span>
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

