'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { listDocuments, Document } from '@/lib/api'
import FolderTree from '@/components/processes/FolderTree'
import DocumentCard from '@/components/documents/DocumentCard'
import StatusFilterChips from '@/components/documents/StatusFilterChips'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { useDocumentFilter } from '@/hooks/useDocumentFilter'
import { useCanApproveDocuments, useCanRejectDocuments, useCanEditWorkspace } from '@/hooks/useHasPermission'

export default function WorkspacePage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  
  // Hooks para permisos y determinar acción principal
  const { hasPermission: canApprove } = useCanApproveDocuments()
  const { hasPermission: canReject } = useCanRejectDocuments()
  const { hasPermission: canEditWorkspace } = useCanEditWorkspace()
  
  // Determinar acción principal: si puede aprobar/rechazar, es admin/validator -> "Ver Detalles", sino "Ver PDF"
  const primaryAction = (canApprove || canReject) ? 'view' : 'pdf'
  
  // Mostrar botón "+ Nuevo Proceso" solo si tiene permisos de edición (admin/editor)
  const canCreateDocuments = canEditWorkspace
  
  // Hook para manejar visualización de PDFs
  const { openLatestPdf, ModalComponent } = usePdfViewer()

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

  // Filtrar documentos por búsqueda, carpeta y estado
  const filteredDocuments = useDocumentFilter(documents, searchQuery, selectedFolderId, statusFilter)
  
  // Ordenar documentos por prioridad de estado (solo UI, sin afectar API)
  // Orden: Pendiente de validación > Borrador > Rechazado > Aprobado > Otros
  const sortedDocuments = [...filteredDocuments].sort((a, b) => {
    const statusPriority: Record<string, number> = {
      'pending_validation': 1,
      'draft': 2,
      'rejected': 3,
      'approved': 4,
    }
    const priorityA = statusPriority[a.status] || 99
    const priorityB = statusPriority[b.status] || 99
    return priorityA - priorityB
  })
  
  // Obtener label del estado para mostrar en el texto informativo
  const getStatusLabel = (status: string | null): string => {
    if (!status) return 'Todos'
    const labels: Record<string, string> = {
      'pending_validation': 'Pendiente',
      'draft': 'Borrador',
      'approved': 'Aprobado',
      'rejected': 'Rechazado',
    }
    return labels[status] || status
  }


  if (!selectedWorkspaceId) {
    // Si no hay workspace seleccionado, verificar si hay workspaces disponibles
    const { workspaces, loading: workspacesLoading } = useWorkspace()
    
    if (workspacesLoading) {
      return (
        <div className="p-8">
          <div className="max-w-7xl mx-auto">
            <div className="animate-pulse text-gray-500">Cargando espacios de trabajo...</div>
          </div>
        </div>
      )
    }
    
    if (workspaces.length === 0) {
      // No hay workspaces, redirigir a onboarding
      return (
        <div className="p-8">
          <div className="max-w-7xl mx-auto">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-blue-900 mb-2">
                No tienes espacios de trabajo
              </h2>
              <p className="text-blue-800 mb-4">
                Para comenzar, necesitas crear o unirte a un espacio de trabajo.
              </p>
              <Link
                href="/onboarding"
                className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
              >
                Crear Espacio de Trabajo
              </Link>
            </div>
          </div>
        </div>
      )
    }
    
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
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {selectedWorkspace?.name || 'Espacio de trabajo'}
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                Procesos documentados, versionados y auditables
              </p>
            </div>
            {canCreateDocuments && (
              <Link
                href="/processes/new"
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
              >
                + Nuevo Proceso
              </Link>
            )}
          </div>

          {/* Barra de búsqueda */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="mb-4">
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
            {/* Chips de filtro por estado */}
            <StatusFilterChips
              selectedStatus={statusFilter}
              onStatusChange={setStatusFilter}
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
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500 mb-4">
                    {searchQuery || statusFilter
                      ? 'No se encontraron documentos que coincidan con los filtros aplicados'
                      : selectedFolderId
                      ? 'No hay documentos en esta carpeta'
                      : 'No hay documentos en este espacio de trabajo'}
                  </p>
                  {!searchQuery && !statusFilter && (
                    <Link
                      href="/processes/new"
                      className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      Crear primer documento
                    </Link>
                  )}
                  {(searchQuery || statusFilter) && (
                    <button
                      onClick={() => {
                        setSearchQuery('')
                        setStatusFilter(null)
                      }}
                      className="inline-block px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 text-sm"
                    >
                      Limpiar filtros
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {/* Texto informativo del filtro activo */}
                  {statusFilter && (
                    <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-md flex items-center justify-between">
                      <p className="text-sm text-gray-700">
                        Mostrando: <span className="font-semibold text-gray-900">{getStatusLabel(statusFilter)}</span> ({sortedDocuments.length} {sortedDocuments.length === 1 ? 'documento' : 'documentos'})
                      </p>
                      <button
                        onClick={() => setStatusFilter(null)}
                        className="text-xs text-blue-600 hover:text-blue-700 hover:underline font-medium"
                      >
                        Limpiar filtros
                      </button>
                    </div>
                  )}
                  
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900">
                      Documentos ({sortedDocuments.length})
                    </h2>
                  </div>
                  <div className="space-y-3">
                    {sortedDocuments.map((doc) => (
                      <DocumentCard
                        key={doc.id}
                        document={doc}
                        onView={() => {
                          window.location.href = `/documents/${doc.id}`
                        }}
                        onViewPdf={() => openLatestPdf(doc)}
                        onStatusClick={(status) => setStatusFilter(status)}
                        showActions={true}
                        primaryAction={primaryAction}
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

