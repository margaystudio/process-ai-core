'use client'

/**
 * Panel de validación (aprobar / rechazar).
 * Solo se renderiza cuando actions.canApprove || actions.canReject.
 * Los handlers y estados de carga vienen del padre.
 */

import { CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/shared/ui/components/button'
import type { DocumentActions } from '@/lib/documentActions'

interface DocumentValidationPanelProps {
  actions: DocumentActions
  approveObservations: string
  onApproveObservationsChange: (v: string) => void
  rejectObservations: string
  onRejectObservationsChange: (v: string) => void
  onApprove: () => void
  onReject: () => void
  isValidating: boolean
}

export function DocumentValidationPanel({
  actions,
  approveObservations,
  onApproveObservationsChange,
  rejectObservations,
  onRejectObservationsChange,
  onApprove,
  onReject,
  isValidating,
}: DocumentValidationPanelProps) {
  if (!actions.canApprove && !actions.canReject) return null

  return (
    <section
      className="rounded-lg border border-ink-200 bg-white p-6"
      aria-label="Decisión de validación"
    >
      <h3 className="text-h3 text-ink-900 mb-5">Decisión de validación</h3>

      {/* Aprobar */}
      {actions.canApprove && (
        <div className="mb-6">
          <label
            htmlFor="approve-obs"
            className="mb-1.5 block text-sm font-medium text-ink-700"
          >
            Observaciones (opcional)
          </label>
          <textarea
            id="approve-obs"
            value={approveObservations}
            onChange={(e) => onApproveObservationsChange(e.target.value)}
            rows={3}
            className="mb-3 w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-create focus:outline-none focus:ring-2 focus:ring-create-ring"
            placeholder="Observaciones adicionales para la aprobación…"
          />
          <Button
            variant="create"
            size="md"
            onClick={onApprove}
            disabled={isValidating}
            className="w-full"
          >
            <CheckCircle className="h-4 w-4" aria-hidden="true" />
            {isValidating ? 'Aprobando…' : 'Aprobar documento'}
          </Button>
        </div>
      )}

      {/* Rechazar */}
      {actions.canReject && (
        <div className={actions.canApprove ? 'border-t border-ink-200 pt-6' : ''}>
          <label
            htmlFor="reject-obs"
            className="mb-1.5 block text-sm font-medium text-ink-700"
          >
            Motivo del rechazo <span className="text-danger" aria-hidden="true">*</span>
          </label>
          <textarea
            id="reject-obs"
            value={rejectObservations}
            onChange={(e) => onRejectObservationsChange(e.target.value)}
            rows={4}
            className="mb-3 w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-danger focus:outline-none focus:ring-2 focus:ring-2"
            placeholder="Describe los motivos del rechazo y las correcciones necesarias…"
            required
            aria-required="true"
          />
          <Button
            variant="danger"
            size="md"
            onClick={onReject}
            disabled={isValidating || !rejectObservations.trim()}
            className="w-full"
          >
            <XCircle className="h-4 w-4" aria-hidden="true" />
            {isValidating ? 'Rechazando…' : 'Rechazar y devolver'}
          </Button>
        </div>
      )}
    </section>
  )
}
