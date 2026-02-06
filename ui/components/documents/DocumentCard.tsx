'use client'

import { useState, useEffect } from 'react'
import { Document, getCurrentDocumentVersion } from '@/lib/api'
import { formatDate } from '@/utils/dateFormat'

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

  const getStatusBadge = () => {
    const statusConfig = {
      approved: { label: 'Aprobado', className: 'bg-green-100 text-green-800' },
      pending_validation: { label: 'Pendiente de validación', className: 'bg-yellow-100 text-yellow-800' },
      rejected: { label: 'Rechazado', className: 'bg-red-100 text-red-800' },
      archived: { label: 'Archivado', className: 'bg-gray-100 text-gray-800' },
      draft: { label: 'Borrador', className: 'bg-gray-100 text-gray-800' },
    }

    const config = statusConfig[document.status as keyof typeof statusConfig] || statusConfig.draft

    const badgeContent = (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.className} ${onStatusClick ? 'cursor-pointer hover:opacity-80 transition' : ''}`}>
        {config.label}
      </span>
    )

    if (onStatusClick) {
      return (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onStatusClick(document.status)
          }}
          className="focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded-full"
        >
          {badgeContent}
        </button>
      )
    }

    return badgeContent
  }

  const getStatusLabel = () => {
    const statusLabels: Record<string, string> = {
      approved: 'Aprobado',
      pending_validation: 'Pendiente de validación',
      rejected: 'Rechazado',
      archived: 'Archivado',
      draft: 'Borrador',
    }
    return statusLabels[document.status] || 'Borrador'
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 hover:border-blue-300 hover:shadow-md transition">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-lg font-semibold text-gray-900">{document.name}</h3>
            {getStatusBadge()}
          </div>
          {document.description && (
            <p className="text-sm text-gray-600 mb-2 line-clamp-2">{document.description}</p>
          )}
          {/* Línea audit-friendly: versión · estado · fecha */}
          <div className="text-xs text-gray-500 mb-3">
            {versionNumber !== null ? (
              <span>v{versionNumber} · {getStatusLabel()} · {formatDate(document.created_at)}</span>
            ) : loadingVersion ? (
              <span className="text-gray-400">Cargando versión...</span>
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
            <button
              onClick={(e) => {
                e.stopPropagation()
                onViewPdf()
              }}
              disabled={processing}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
            >
              Ver PDF
            </button>
          )}
          {primaryAction === 'view' && onView && (
            <button
              onClick={onView}
              disabled={processing}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition font-medium"
            >
              Ver Detalles
            </button>
          )}
          {/* Acción secundaria */}
          {primaryAction === 'pdf' && onView && (
            <button
              onClick={onView}
              disabled={processing}
              className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition"
            >
              Ver Detalles
            </button>
          )}
          {primaryAction === 'view' && onViewPdf && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onViewPdf()
              }}
              disabled={processing}
              className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition"
            >
              Ver PDF
            </button>
          )}
          {onReview && (
            <button
              onClick={onReview}
              disabled={processing}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {processing ? 'Procesando...' : 'Iniciar Revisión'}
            </button>
          )}
          {onApprove && (
            <button
              onClick={onApprove}
              disabled={processing}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {processing ? 'Procesando...' : 'Aprobar'}
            </button>
          )}
          {onReject && (
            <button
              onClick={onReject}
              disabled={processing}
              className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {processing ? 'Procesando...' : 'Rechazar'}
            </button>
          )}
          {onCorrect && (
            <button
              onClick={onCorrect}
              disabled={processing}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              Corregir
            </button>
          )}
        </div>
      )}
    </div>
  )
}

