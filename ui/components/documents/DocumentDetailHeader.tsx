'use client'

/**
 * Header de la vista de detalle de documento.
 * Muestra: breadcrumb de vuelta, nombre, tipo documental, StatusBadge,
 * versión (si aplica) y las acciones disponibles (gateadas por getDocumentActions).
 */

import { ArrowLeft, Send, CheckCircle, XCircle, RotateCcw, Pencil, Trash2, PlusCircle } from 'lucide-react'
import { Button } from '@/shared/ui/components/button'
import { StatusBadge } from '@/shared/ui/components/StatusBadge'
import type { Document, DocumentVersion } from '@/lib/api'
import type { DocumentActions } from '@/lib/documentActions'

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  procedimiento: 'Procedimiento',
  instructivo: 'Instructivo',
  manual_interno: 'Manual interno',
  manual_externo: 'Manual externo',
  politica: 'Política',
  normativa: 'Normativa',
  formulario: 'Formulario',
  checklist: 'Checklist',
  tramite: 'Trámite',
  faq_validada: 'FAQ validada',
  presupuesto: 'Presupuesto',
}

interface DocumentDetailHeaderProps {
  document: Document
  currentVersion: DocumentVersion | null
  actions: DocumentActions
  // handlers de acción
  onBack: () => void
  onEdit: () => void
  onSubmitForReview: () => void
  onCancelSubmission: () => void
  onApprove: () => void
  onReject: () => void
  onNewVersion: () => void
  onDelete: () => void
  // loading states
  isSubmittingForReview: boolean
  isCancelling: boolean
  isValidating: boolean
  isDeleting: boolean
}

export function DocumentDetailHeader({
  document,
  currentVersion,
  actions,
  onBack,
  onEdit,
  onSubmitForReview,
  onCancelSubmission,
  onApprove,
  onReject,
  onNewVersion,
  onDelete,
  isSubmittingForReview,
  isCancelling,
  isValidating,
  isDeleting,
}: DocumentDetailHeaderProps) {
  const typeLabel =
    DOCUMENT_TYPE_LABELS[document.document_type ?? ''] ?? document.document_type ?? ''

  return (
    <header className="mb-6">
      {/* Breadcrumb / volver */}
      <button
        type="button"
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 hover:text-ink-800 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Volver
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        {/* Título + chips */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            {typeLabel && (
              <span className="rounded-md bg-indigo-tint px-2 py-0.5 text-xs font-bold text-indigo">
                {typeLabel}
              </span>
            )}
            <StatusBadge estado={document.status} />
            {currentVersion?.version_number != null && (
              <span className="rounded-md bg-ink-100 px-2 py-0.5 text-xs font-bold text-ink-600 font-mono">
                v{currentVersion.version_number}
              </span>
            )}
          </div>
          <h1 className="text-h1 text-ink-900 leading-tight">{document.name}</h1>
        </div>

        {/* Acciones primarias */}
        <nav
          aria-label="Acciones del documento"
          className="flex flex-wrap items-center gap-2 pt-1"
        >
          {actions.canEditMetadata && (
            <Button variant="secondary" size="sm" onClick={onEdit}>
              <Pencil className="h-4 w-4" aria-hidden="true" />
              Editar
            </Button>
          )}

          {actions.canSubmitForReview && (
            <Button
              variant="create"
              size="sm"
              onClick={onSubmitForReview}
              disabled={isSubmittingForReview}
            >
              <Send className="h-4 w-4" aria-hidden="true" />
              {isSubmittingForReview ? 'Enviando…' : 'Enviar a revisión'}
            </Button>
          )}

          {actions.canCancelSubmission && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onCancelSubmission}
              disabled={isCancelling}
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              {isCancelling ? 'Cancelando…' : 'Cancelar envío'}
            </Button>
          )}

          {actions.canApprove && (
            <Button
              variant="create"
              size="sm"
              onClick={onApprove}
              disabled={isValidating}
            >
              <CheckCircle className="h-4 w-4" aria-hidden="true" />
              {isValidating ? 'Aprobando…' : 'Aprobar'}
            </Button>
          )}

          {actions.canReject && (
            <Button
              variant="danger"
              size="sm"
              onClick={onReject}
              disabled={isValidating}
            >
              <XCircle className="h-4 w-4" aria-hidden="true" />
              {isValidating ? 'Rechazando…' : 'Rechazar'}
            </Button>
          )}

          {actions.canCreateNewVersion && (
            <Button variant="secondary" size="sm" onClick={onNewVersion}>
              <PlusCircle className="h-4 w-4" aria-hidden="true" />
              Nueva versión
            </Button>
          )}

          {actions.canDelete && (
            <Button
              variant="danger"
              size="sm"
              onClick={onDelete}
              disabled={isDeleting}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              {isDeleting ? 'Eliminando…' : 'Eliminar'}
            </Button>
          )}
        </nav>
      </div>
    </header>
  )
}
