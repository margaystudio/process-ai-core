'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardBody, Input, Button } from '@/shared/ui/components'
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
  const { openLatestPdf, ModalComponent } = usePdfViewer()

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
        <div className="mx-auto max-w-7xl">
          <Card className="border-danger-bd">
            <CardBody>
              <p className="text-body text-ink-700">
                No tenés permisos para ver esta página. Tu rol actual es: {role}
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    )
  }

  if (!selectedWorkspaceId) {
    return (
      <div className="p-8">
        <div className="mx-auto max-w-7xl">
          <Card className="border-warning-bd">
            <CardBody>
              <p className="text-body text-ink-700">
                Seleccioná un espacio de trabajo en el encabezado para ver sus documentos.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-h1 text-ink-900">En revisión</h1>
          <p className="mt-1 text-sm text-ink-500">
            {selectedWorkspace?.name || 'Espacio de trabajo'} · Documentos rechazados que requieren corrección
          </p>
        </div>

        {/* Barra de búsqueda */}
        <Card className="mb-6">
          <CardBody>
            <label htmlFor="search" className="mb-2 block text-sm font-semibold text-ink-700">
              Buscar documentos
            </label>
            <Input
              id="search"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar por nombre o descripción..."
            />
          </CardBody>
        </Card>

        {/* Contenido principal */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
          {/* Columna izquierda: Estructura de carpetas */}
          <div className="lg:col-span-1">
            <Card className="sticky top-4">
              <CardBody>
                <h2 className="mb-4 text-h3 text-ink-900">Estructura de carpetas</h2>
                <FolderTree
                  workspaceId={selectedWorkspaceId}
                  selectedFolderId={selectedFolderId || undefined}
                  onSelectFolder={(id) => setSelectedFolderId(id)}
                  showSelectable={true}
                  showCrud={false}
                />
              </CardBody>
            </Card>
          </div>

          {/* Columna derecha: Lista de documentos */}
          <div className="lg:col-span-3">
            <Card>
              <CardBody>
                {loading ? (
                  <div className="py-12 text-center">
                    <div className="animate-pulse text-ink-500">Cargando documentos...</div>
                  </div>
                ) : error ? (
                  <div className="rounded-md border border-danger-bd bg-danger-bg p-4">
                    <p className="mb-3 text-sm text-danger">Error: {error}</p>
                    <Button variant="danger" size="sm" onClick={() => window.location.reload()}>
                      Reintentar
                    </Button>
                  </div>
                ) : filteredDocuments.length === 0 ? (
                  <div className="py-12 text-center">
                    <p className="mb-2 text-ink-600">
                      {searchQuery || selectedFolderId
                        ? 'No se encontraron documentos que coincidan con los filtros'
                        : 'No hay documentos a revisar'}
                    </p>
                    <p className="text-sm text-ink-500">
                      {searchQuery || selectedFolderId
                        ? 'Probá ajustar los filtros de búsqueda'
                        : 'Todos tus documentos están aprobados o pendientes'}
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="mb-4 flex items-center justify-between">
                      <h2 className="text-h3 text-ink-900">
                        Documentos ({filteredDocuments.length} de {documents.length})
                      </h2>
                    </div>
                    <div className="space-y-3">
                      {filteredDocuments.map((doc) => (
                        <DocumentCard
                          key={doc.id}
                          document={doc}
                          onCorrect={() => handleCorrect(doc)}
                          onViewPdf={() => openLatestPdf(doc)}
                          showActions={true}
                        />
                      ))}
                    </div>
                  </>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      </div>

      <ModalComponent />
    </div>
  )
}
