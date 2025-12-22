'use client'

import { useState, useEffect, useMemo } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import {
  listDocumentsPendingApproval,
  approveDocument,
  rejectDocument,
  Document,
  getDocumentRuns,
} from '@/lib/api'
import DocumentCard from '@/components/documents/DocumentCard'
import RejectModal from '@/components/documents/RejectModal'
import ApprovalModal from '@/components/documents/ApprovalModal'
import FolderTree from '@/components/processes/FolderTree'

export default function ApprovalQueuePage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const { role } = useUserRole()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [showApprovalModal, setShowApprovalModal] = useState(false)
  const [processing, setProcessing] = useState<string | null>(null) // documentId en proceso
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)

  // TODO: Obtener userId de autenticación
  const getUserId = (): string | null => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('userId')
    }
    return null
  }

  useEffect(() => {
    async function loadDocuments() {
      if (!selectedWorkspaceId) {
        setLoading(false)
        return
      }

      const userId = getUserId()
      if (!userId) {
        setError('Usuario no autenticado')
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const docs = await listDocumentsPendingApproval(selectedWorkspaceId, userId)
        setDocuments(docs)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
        setDocuments([])
      } finally {
        setLoading(false)
      }
    }

    loadDocuments()
  }, [selectedWorkspaceId])

  const handleApprove = async (document: Document) => {
    const userId = getUserId()
    if (!userId || !selectedWorkspaceId) return

    setProcessing(document.id)
    try {
      await approveDocument(document.id, userId, selectedWorkspaceId)
      // Recargar documentos
      const docs = await listDocumentsPendingApproval(selectedWorkspaceId, userId)
      setDocuments(docs)
      setShowApprovalModal(false)
      setSelectedDocument(null)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Error al aprobar documento')
    } finally {
      setProcessing(null)
    }
  }

  const handleReject = async (document: Document, observations: string) => {
    const userId = getUserId()
    if (!userId || !selectedWorkspaceId) return

    setProcessing(document.id)
    try {
      await rejectDocument(document.id, observations, userId, selectedWorkspaceId)
      // Recargar documentos
      const docs = await listDocumentsPendingApproval(selectedWorkspaceId, userId)
      setDocuments(docs)
      setShowRejectModal(false)
      setSelectedDocument(null)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Error al rechazar documento')
    } finally {
      setProcessing(null)
    }
  }

  const handleViewDetails = async (document: Document) => {
    setSelectedDocument(document)
    // Cargar runs del documento para mostrar preview
    try {
      const runs = await getDocumentRuns(document.id)
      // Por ahora, solo abrimos el modal
      setShowApprovalModal(true)
    } catch (err) {
      console.error('Error cargando detalles:', err)
      setShowApprovalModal(true)
    }
  }

  // Filtrar documentos por búsqueda y carpeta
  const filteredDocuments = useMemo(() => {
    let filtered = documents

    // Filtrar por carpeta
    if (selectedFolderId) {
      filtered = filtered.filter((doc) => doc.folder_id === selectedFolderId)
    }

    // Filtrar por búsqueda
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (doc) =>
          doc.name.toLowerCase().includes(query) ||
          doc.description.toLowerCase().includes(query)
      )
    }

    return filtered
  }, [documents, searchQuery, selectedFolderId])

  // Verificar que el usuario es aprobador
  if (role && role !== 'owner' && role !== 'admin' && role !== 'approver') {
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
          <h1 className="text-3xl font-bold text-gray-900">Cola de Aprobación</h1>
          <p className="text-gray-600 mt-1">
            {selectedWorkspace?.name || 'Workspace'} - Documentos pendientes de aprobación
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
                      : 'No hay documentos pendientes de aprobación'}
                  </p>
                  <p className="text-gray-400 text-sm">
                    {searchQuery || selectedFolderId
                      ? 'Intenta ajustar los filtros de búsqueda'
                      : 'Todos los documentos han sido procesados'}
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
                        onView={() => handleViewDetails(doc)}
                        onApprove={() => {
                          setSelectedDocument(doc)
                          setShowApprovalModal(true)
                        }}
                        onReject={() => {
                          setSelectedDocument(doc)
                          setShowRejectModal(true)
                        }}
                        showActions={true}
                        processing={processing === doc.id}
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Modales */}
        {selectedDocument && (
          <>
            <ApprovalModal
              document={selectedDocument}
              isOpen={showApprovalModal}
              onClose={() => {
                setShowApprovalModal(false)
                setSelectedDocument(null)
              }}
              onApprove={() => handleApprove(selectedDocument)}
              processing={processing === selectedDocument.id}
            />

            <RejectModal
              document={selectedDocument}
              isOpen={showRejectModal}
              onClose={() => {
                setShowRejectModal(false)
                setSelectedDocument(null)
              }}
              onReject={(observations) => handleReject(selectedDocument, observations)}
              processing={processing === selectedDocument.id}
            />
          </>
        )}
      </div>
    </div>
  )
}

