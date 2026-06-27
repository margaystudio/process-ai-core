'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Plus, Upload } from 'lucide-react'
import { Card, CardBody, Input, Button, buttonVariants } from '@/shared/ui/components'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { listDocuments, Document } from '@/lib/api'
import FolderTree from '@/components/processes/FolderTree'
import DocumentCard from '@/components/documents/DocumentCard'
import StatusFilterChips from '@/components/documents/StatusFilterChips'
import FileImportModal from '@/components/processes/FileImportModal'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { useDocumentFilter } from '@/hooks/useDocumentFilter'
import { useCanApproveDocuments, useCanRejectDocuments, useCanEditWorkspace } from '@/hooks/useHasPermission'
import { useUserRole } from '@/hooks/useUserRole'
import { useWorkspaceProfileIncomplete } from '@/hooks/useWorkspaceProfileIncomplete'
import WorkspaceProfileBanner from '@/components/workspace/WorkspaceProfileBanner'

export default function WorkspacePage() {
  const { selectedWorkspaceId, selectedWorkspace, activeTenantId, platformRoles } = useWorkspace()
  const { role, loading: roleLoading } = useUserRole()
  const workspaceRole = selectedWorkspace?.role ?? role
  const { incomplete: profileIncomplete, loading: profileCheckLoading } =
    useWorkspaceProfileIncomplete(selectedWorkspace, workspaceRole, platformRoles)
  const canEditGeneralSettings =
    platformRoles.includes('superadmin') ||
    workspaceRole === 'owner' ||
    workspaceRole === 'creator' ||
    workspaceRole === 'admin'
  const router = useRouter()
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const [importModalOpen, setImportModalOpen] = useState(false)

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

  // Redirigir viewers a su página dedicada
  useEffect(() => {
    if (!roleLoading && role === 'viewer') {
      router.replace('/dashboard/view')
    }
  }, [role, roleLoading, router])

  // Al cambiar de tenant, limpiar carpeta seleccionada
  useEffect(() => {
    setSelectedFolderId(null)
  }, [activeTenantId])

  // Cargar documentos (no cargar si es viewer, será redirigido)
  const loadDocuments = async () => {
    if (!selectedWorkspaceId || !activeTenantId) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const docs = await listDocuments(
        selectedWorkspaceId,
        undefined,
        'process'
      )
      setDocuments(docs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (role === 'viewer') return
    loadDocuments()
  }, [selectedWorkspaceId, activeTenantId, role])

  // Filtrar documentos por búsqueda, carpeta y estado
  const filteredDocuments = useDocumentFilter(documents, searchQuery, selectedFolderId, statusFilter)

  // Early return para viewers (después de todos los hooks)
  if (!roleLoading && role === 'viewer') {
    return null
  }

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
          <div className="mx-auto max-w-7xl">
            <div className="animate-pulse text-ink-500">Cargando espacios de trabajo...</div>
          </div>
        </div>
      )
    }

    if (workspaces.length === 0) {
      // No hay workspaces, redirigir a onboarding
      return (
        <div className="p-8">
          <div className="mx-auto max-w-7xl">
            <Card>
              <CardBody className="space-y-3">
                <h2 className="text-h2 text-ink-900">No tenés espacios de trabajo</h2>
                <p className="text-body text-ink-600">
                  Para comenzar, necesitás crear o unirte a un espacio de trabajo.
                </p>
                <Link href="/onboarding" className={buttonVariants({ variant: 'create' })}>
                  Crear espacio de trabajo
                </Link>
              </CardBody>
            </Card>
          </div>
        </div>
      )
    }

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
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h1 className="text-h1 text-ink-900">
                {selectedWorkspace?.name || 'Espacio de trabajo'}
              </h1>
              <p className="mt-1 text-sm text-ink-500">
                Procesos documentados, versionados y auditables
              </p>
            </div>
            {canCreateDocuments && (
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setImportModalOpen(true)}
                >
                  <Upload />
                  Importar archivo
                </Button>
                <Link href="/processes/new" className={buttonVariants({ variant: 'create' })}>
                  <Plus />
                  Nuevo proceso
                </Link>
              </div>
            )}
          </div>

          {!profileCheckLoading && profileIncomplete && selectedWorkspaceId && (
            <WorkspaceProfileBanner
              workspaceId={selectedWorkspaceId}
              canEditSettings={canEditGeneralSettings}
              className="mb-4"
            />
          )}

          {/* Barra de búsqueda */}
          <Card>
            <CardBody>
              <div className="mb-4">
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
              </div>
              {/* Chips de filtro por estado */}
              <StatusFilterChips
                selectedStatus={statusFilter}
                onStatusChange={setStatusFilter}
              />
            </CardBody>
          </Card>
        </div>

        {/* Contenido principal */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
          {/* Columna izquierda: Estructura de carpetas */}
          <div className="lg:col-span-1">
            <Card className="sticky top-4">
              <CardBody>
                <h2 className="mb-4 text-h3 text-ink-900">Estructura de carpetas</h2>
                <FolderTree
                  key={activeTenantId ?? 'no-tenant'}
                  workspaceId={selectedWorkspaceId}
                  selectedFolderId={selectedFolderId || undefined}
                  onSelectFolder={(id) => setSelectedFolderId(id)}
                  showSelectable={true}
                  showCrud={false}
                  allDocuments={documents}
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
                    <p className="text-sm text-danger">Error: {error}</p>
                  </div>
                ) : filteredDocuments.length === 0 ? (
                  <div className="py-12 text-center">
                    <p className="mb-4 text-ink-500">
                      {searchQuery || statusFilter
                        ? 'No se encontraron documentos que coincidan con los filtros aplicados'
                        : selectedFolderId
                        ? 'No hay documentos en esta carpeta'
                        : 'No hay documentos en este espacio de trabajo'}
                    </p>
                    {!searchQuery && !statusFilter && (
                      <Link href="/processes/new" className={buttonVariants({ variant: 'create' })}>
                        <Plus />
                        Crear primer documento
                      </Link>
                    )}
                    {(searchQuery || statusFilter) && (
                      <button
                        onClick={() => {
                          setSearchQuery('')
                          setStatusFilter(null)
                        }}
                        className={buttonVariants({ variant: 'secondary', size: 'sm' })}
                      >
                        Limpiar filtros
                      </button>
                    )}
                  </div>
                ) : (
                  <>
                    {/* Texto informativo del filtro activo */}
                    {statusFilter && (
                      <div className="mb-3 flex items-center justify-between rounded-md border border-info-bd bg-info-bg p-3">
                        <p className="text-sm text-ink-700">
                          Mostrando: <span className="font-semibold text-ink-900">{getStatusLabel(statusFilter)}</span> ({sortedDocuments.length} {sortedDocuments.length === 1 ? 'documento' : 'documentos'})
                        </p>
                        <button
                          onClick={() => setStatusFilter(null)}
                          className="text-xs font-semibold text-info hover:underline"
                        >
                          Limpiar filtros
                        </button>
                      </div>
                    )}

                    <div className="mb-4 flex items-center justify-between">
                      <h2 className="text-h3 text-ink-900">
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
              </CardBody>
            </Card>
          </div>
        </div>
      </div>

      <ModalComponent />
      {selectedWorkspaceId && (
        <FileImportModal
          workspaceId={selectedWorkspaceId}
          defaultFolderId={selectedFolderId}
          open={importModalOpen}
          onClose={() => setImportModalOpen(false)}
          onImported={loadDocuments}
        />
      )}
    </div>
  )
}
