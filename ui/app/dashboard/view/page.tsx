'use client'

import { useState, useEffect, useMemo } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import {
  listApprovedDocuments,
  Document,
  getDocumentRuns,
  getArtifactUrl,
} from '@/lib/api'
import DocumentCard from '@/components/documents/DocumentCard'

export default function ViewPage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const { role } = useUserRole()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)

  useEffect(() => {
    async function loadDocuments() {
      if (!selectedWorkspaceId) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const docs = await listApprovedDocuments(
          selectedWorkspaceId,
          selectedFolderId || undefined
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

  const handleView = async (document: Document) => {
    try {
      const runs = await getDocumentRuns(document.id)
      if (runs.length > 0 && runs[0].artifacts.pdf) {
        window.open(runs[0].artifacts.pdf, '_blank')
      } else {
        alert('No hay PDF disponible para este documento')
      }
    } catch (err) {
      alert('Error al abrir el documento')
    }
  }

  // Verificar que el usuario es viewer
  if (role && role !== 'viewer') {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <p className="text-red-800">
              No tienes permisos para ver esta página. Tu rol actual es: {role}
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
          <h1 className="text-3xl font-bold text-gray-900">Documentos Aprobados</h1>
          <p className="text-gray-600 mt-1">
            {selectedWorkspace?.name || 'Workspace'} - Documentos disponibles para consulta
          </p>
        </div>

        {/* Barra de búsqueda */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
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
            <button
              onClick={() => window.location.reload()}
              className="mt-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              Reintentar
            </button>
          </div>
        ) : filteredDocuments.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500 text-lg mb-2">
                    {searchQuery || selectedFolderId
                      ? 'No se encontraron documentos que coincidan con los filtros'
                      : 'No hay documentos aprobados disponibles'}
                  </p>
                </div>
              ) : (
                <>
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">
                      Documentos ({filteredDocuments.length} de {documents.length})
                    </h2>
                  </div>
                  <div className="space-y-3">
                    {filteredDocuments.map((doc) => (
                      <DocumentCard
                        key={doc.id}
                        document={doc}
                        onView={() => handleView(doc)}
                        showActions={true}
                      />
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

