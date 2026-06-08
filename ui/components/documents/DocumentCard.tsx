'use client'

import { useState, useEffect } from 'react'
import { Document, getCurrentDocumentVersion } from '@/lib/api'
import { formatDate } from '@/utils/dateFormat'
import { Badge, Button, type BadgeProps } from '@/shared/ui/components'
import { cn } from '@/shared/ui/cn'

interface DocumentCardProps {
  document: Document
  onView?: () => void
  onApprove?: () => void
  onReject?: () => void
  onCorrect?: () => void
  onReview?: () => void
  onViewPdf?: () => void
  onStatusClick?: (status: string) => void
  showActions?: boolean
  processing?: boolean
  primaryAction?: 'view' | 'pdf' // Acción principal según rol
}

const STATUS_CONFIG: Record<string, { label: string; variant: BadgeProps['variant'] }> = {
  approved: { label: 'Aprobado', variant: 'success' },
  pending_validation: { label: 'Pendiente', variant: 'warning' },
  rejected: { label: 'Rechazado', variant: 'danger' },
  archived: { label: 'Archivado', variant: 'neutral' },
  draft: { label: 'Borrador', variant: 'neutral' },
}

export default function DocumentCard({
  document,
  onView,
  onApprove,
  onReject,
  onCorrect,
  onReview,
  onViewPdf,
  onStatusClick,
  showActions = false,
  processing = false,
  primaryAction = 'view',
}: DocumentCardProps) {
  const [versionNumber, setVersionNumber] = useState<number | null>(null)
  const [loadingVersion, setLoadingVersion] = useState(false)

  // Cargar número de versión si está disponible
  useEffect(() => {
    async function loadVersion() {
      if (document.status === 'approved') {
        try {
          setLoadingVersion(true)
          const version = await getCurrentDocumentVersion(document.id)
          setVersionNumber(version.version_number)
        } catch (err) {
          // Si falla, no mostrar versión
          console.error('Error cargando versión:', err)
        } finally {
          setLoadingVersion(false)
        }
      }
    }
    loadVersion()
  }, [document.id, document.status])

  const config = STATUS_CONFIG[document.status] || STATUS_CONFIG.draft

  const statusBadge = <Badge variant={config.variant}>{config.label}</Badge>

  const getStatusLabel = () => config.label

  // Indicador visual sutil para documentos pendientes de validación
  const isPendingValidation = document.status === 'pending_validation'

  return (
    <div
      className={cn(
        'rounded-lg border border-ink-200 bg-white p-5 transition-colors hover:border-accent hover:shadow-md',
        isPendingValidation && 'border-l-4 border-l-warning'
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-h3 text-ink-900">{document.name}</h3>
            {onStatusClick ? (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onStatusClick(document.status)
                }}
                className="rounded-full"
                title="Filtrar por este estado"
              >
                {statusBadge}
              </button>
            ) : (
              statusBadge
            )}
          </div>
          {document.description && (
            <p className="mb-2 line-clamp-2 text-sm text-ink-600">{document.description}</p>
          )}
          {/* Línea audit-friendly: versión · estado · fecha */}
          <div className="mb-3 text-xs text-ink-500">
            {versionNumber !== null ? (
              <span>v{versionNumber} · {getStatusLabel()} · {formatDate(document.created_at)}</span>
            ) : loadingVersion ? (
              <span className="text-ink-400">Cargando versión...</span>
            ) : (
              <span>{getStatusLabel()} · {formatDate(document.created_at)}</span>
            )}
          </div>
        </div>
      </div>

      {showActions && (
        <div className="mt-4 flex items-center gap-2">
          {/* Acción principal según rol */}
          {primaryAction === 'pdf' && onViewPdf && (
            <Button
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                onViewPdf()
              }}
              disabled={processing}
            >
              Ver PDF
            </Button>
          )}
          {primaryAction === 'view' && onView && (
            <Button size="sm" onClick={onView} disabled={processing}>
              Ver detalles
            </Button>
          )}
          {/* Acción secundaria */}
          {primaryAction === 'pdf' && onView && (
            <Button size="sm" variant="ghost" onClick={onView} disabled={processing}>
              Ver detalles
            </Button>
          )}
          {primaryAction === 'view' && onViewPdf && (
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation()
                onViewPdf()
              }}
              disabled={processing}
            >
              Ver PDF
            </Button>
          )}
          {onReview && (
            <Button size="sm" onClick={onReview} disabled={processing}>
              {processing ? 'Procesando...' : 'Iniciar revisión'}
            </Button>
          )}
          {onApprove && (
            <Button size="sm" variant="create" onClick={onApprove} disabled={processing}>
              {processing ? 'Procesando...' : 'Aprobar'}
            </Button>
          )}
          {onReject && (
            <Button size="sm" variant="danger" onClick={onReject} disabled={processing}>
              {processing ? 'Procesando...' : 'Rechazar'}
            </Button>
          )}
          {onCorrect && (
            <Button size="sm" onClick={onCorrect} disabled={processing}>
              Corregir
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
