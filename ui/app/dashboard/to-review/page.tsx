'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import { useUserId } from '@/hooks/useUserId'
import {
  listDocumentsToReview,
  Document,
} from '@/lib/api'
import DocumentCard from '@/components/documents/DocumentCard'
import FolderTree from '@/components/processes/FolderTree'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { useDocumentFilter } from '@/hooks/useDocumentFilter'

export default function ToReviewPage() {
  const router = useRouter()
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const { role } = useUserRole()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  
  // Hook para manejar visualización de PDFs
  const { openPdf, ModalComponent } = usePdfViewer()

  const userId = useUserId()

  useEffect(() => {
    async function loadDocuments() {
      if (!selectedWorkspaceId) {
        setLoading(false)
        return
      }

      if (!userId) {
        setError('Usuario no autenticado')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const docs = await listDocumentsToReview(selectedWorkspaceId, userId)
        setDocuments(docs)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
        setDocuments([])
      } finally {
        setLoading(false)
      }
    }

    loadDocuments()
  }, [selectedWorkspaceId, userId])

  const handleCorrect = (document: Document) => {
    router.push(`/documents/${document.id}/correct`)
  }

  // Filtrar documentos por búsqueda y carpeta
  const filteredDocuments = useDocumentFilter(documents, searchQuery, selectedFolderId)

  // Verificar que el usuario es creador
  if (role && role !== 'creator') {
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

  if (!selectedWorkspaceId) {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
            <p className="text-yellow-800">
              Por favor, selecciona un espacio de trabajo en el header para ver sus documentos.
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
          <h1 className="text-3xl font-bold text-gray-900">Documentos a Revisar</h1>
          <p className="text-gray-600 mt-1">
            {selectedWorkspace?.name || 'Espacio de trabajo'} - Documentos rechazados que requieren corrección
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
                      : 'No hay documentos a revisar'}
                  </p>
                  <p className="text-gray-400 text-sm">
                    {searchQuery || selectedFolderId
                      ? 'Intenta ajustar los filtros de búsqueda'
                      : 'Todos tus documentos están aprobados o pendientes'}
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
                        onCorrect={() => handleCorrect(doc)}
                        onViewPdf={() => openPdf(doc)}
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

      <ModalComponent />
    </div>
  )
}

