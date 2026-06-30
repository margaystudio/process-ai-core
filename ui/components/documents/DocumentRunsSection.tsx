'use client'

/**
 * Sección "Versiones generadas" — lista de runs con sus artefactos.
 * Idéntica funcionalidad a la original; nueva capa visual con tokens DS.
 */

import { FileText, PlusCircle } from 'lucide-react'
import { Button } from '@/shared/ui/components/button'
import { Card, CardBody } from '@/shared/ui/components/card'
import FileList from '@/components/processes/FileList'
import FileUploadModal, { FileType } from '@/components/processes/FileUploadModal'
import { formatDateTime } from '@/utils/dateFormat'
import type { FileItemData } from '@/components/processes/FileItem'
import type { DocumentVersion } from '@/lib/api'

interface Run {
  run_id: string
  created_at: string
  artifacts: { json?: string; md?: string; pdf?: string }
}

interface DocumentRunsSectionProps {
  runs: Run[]
  versions: DocumentVersion[]
  documentId: string
  canCreateNewVersion: boolean
  // nueva versión
  showNewVersionForm: boolean
  onToggleNewVersionForm: () => void
  revisionNotes: string
  onRevisionNotesChange: (v: string) => void
  newVersionFiles: FileItemData[]
  onAddFile: (file: File, type: FileType, description: string) => void
  onRemoveFile: (id: string) => void
  isNewVersionModalOpen: boolean
  onOpenModal: () => void
  onCloseModal: () => void
  onGenerateNewVersion: () => void
  isGenerating: boolean
  // abrir artefactos
  onOpenVersionPreviewPdf: (documentId: string, versionId: string) => void
  onOpenArtifactFromRun: (url: string, type: 'pdf' | 'markdown' | 'json') => void
}

export function DocumentRunsSection({
  runs,
  versions,
  documentId,
  canCreateNewVersion,
  showNewVersionForm,
  onToggleNewVersionForm,
  revisionNotes,
  onRevisionNotesChange,
  newVersionFiles,
  onAddFile,
  onRemoveFile,
  isNewVersionModalOpen,
  onOpenModal,
  onCloseModal,
  onGenerateNewVersion,
  isGenerating,
  onOpenVersionPreviewPdf,
  onOpenArtifactFromRun,
}: DocumentRunsSectionProps) {
  /** Determina la versión PDF más relevante para un run, siguiendo la prioridad original. */
  function getRelevantPdfVersion(runId?: string): DocumentVersion | null {
    const scoped = runId ? versions.filter((v) => v.run_id === runId) : versions
    return (
      scoped.find((v) => v.version_status === 'DRAFT' && v.content_type === 'manual_edit') ||
      scoped.find((v) => v.version_status === 'IN_REVIEW') ||
      scoped.find((v) => v.version_status === 'APPROVED') ||
      scoped.find((v) => v.version_status === 'DRAFT') ||
      null
    )
  }

  return (
    <section aria-label="Versiones generadas">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-h2 text-ink-900">Versiones generadas</h2>
        <Button
          variant="create"
          size="sm"
          onClick={onToggleNewVersionForm}
          disabled={!canCreateNewVersion}
          title={
            !canCreateNewVersion
              ? 'Solo disponible cuando el documento está aprobado o rechazado'
              : undefined
          }
        >
          <PlusCircle className="h-4 w-4" aria-hidden="true" />
          {showNewVersionForm ? 'Cancelar' : 'Nueva versión'}
        </Button>
      </div>

      {/* Formulario de nueva versión */}
      {showNewVersionForm && (
        <Card className="mb-6">
          <CardBody className="space-y-4">
            <h3 className="text-h3 text-ink-900">Generar nueva versión</h3>
            <p className="text-sm text-ink-600">
              Subí nuevos archivos o agregá instrucciones de revisión. Sin archivos nuevos se
              reutilizarán los del último run.
            </p>

            <div>
              <label
                htmlFor="revision-notes"
                className="mb-1.5 block text-sm font-medium text-ink-700"
              >
                Instrucciones de revisión
              </label>
              <textarea
                id="revision-notes"
                value={revisionNotes}
                onChange={(e) => onRevisionNotesChange(e.target.value)}
                rows={4}
                className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
                placeholder="Ej: Corregir errores gramaticales, mejorar la descripción del paso 3…"
              />
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-ink-700">Archivos (opcional)</label>
                <Button variant="ghost" size="sm" onClick={onOpenModal}>
                  + Agregar archivo
                </Button>
              </div>
              <FileList files={newVersionFiles} onRemove={onRemoveFile} />
              {newVersionFiles.length === 0 && (
                <p className="mt-1 text-xs text-ink-500">
                  Sin archivos nuevos se reutilizarán los del último run.
                </p>
              )}
            </div>

            <div className="flex gap-3 pt-1">
              <Button
                variant="create"
                size="md"
                onClick={onGenerateNewVersion}
                disabled={isGenerating || (newVersionFiles.length === 0 && !revisionNotes.trim())}
              >
                {isGenerating ? 'Generando…' : 'Generar nueva versión'}
              </Button>
              <Button
                variant="secondary"
                size="md"
                onClick={onToggleNewVersionForm}
              >
                Cancelar
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Lista de runs */}
      {runs.length > 0 ? (
        <div className="space-y-3">
          {runs.map((run) => (
            <Card key={run.run_id}>
              <CardBody>
                <div className="mb-3">
                  <p className="text-sm font-semibold text-ink-900 font-mono">
                    Run {run.run_id.substring(0, 8)}…
                  </p>
                  <p className="text-xs text-ink-500">{formatDateTime(run.created_at)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {run.artifacts.pdf && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        const rv = getRelevantPdfVersion(run.run_id)
                        if (rv) {
                          onOpenVersionPreviewPdf(documentId, rv.id)
                        } else {
                          onOpenArtifactFromRun(run.artifacts.pdf!, 'pdf')
                        }
                      }}
                    >
                      <FileText className="h-4 w-4" aria-hidden="true" />
                      Ver PDF
                    </Button>
                  )}
                  {run.artifacts.md && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onOpenArtifactFromRun(run.artifacts.md!, 'markdown')}
                    >
                      <FileText className="h-4 w-4" aria-hidden="true" />
                      Ver Markdown
                    </Button>
                  )}
                  {run.artifacts.json && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onOpenArtifactFromRun(run.artifacts.json!, 'json')}
                    >
                      <FileText className="h-4 w-4" aria-hidden="true" />
                      Ver JSON
                    </Button>
                  )}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <p className="text-sm text-ink-500">
            No hay versiones generadas aún.
          </p>
          {canCreateNewVersion && (
            <p className="mt-1 text-xs text-ink-400">
              Usá el botón &quot;Nueva versión&quot; para crear la primera.
            </p>
          )}
        </div>
      )}

      <FileUploadModal
        isOpen={isNewVersionModalOpen}
        onClose={onCloseModal}
        onAdd={onAddFile}
      />
    </section>
  )
}
