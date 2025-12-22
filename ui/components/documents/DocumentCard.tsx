'use client'

import { Document } from '@/lib/api'

interface DocumentCardProps {
  document: Document
  onView?: () => void
  onApprove?: () => void
  onReject?: () => void
  onCorrect?: () => void
  onReview?: () => void
  showActions?: boolean
  processing?: boolean
}

export default function DocumentCard({
  document,
  onView,
  onApprove,
  onReject,
  onCorrect,
  onReview,
  showActions = false,
  processing = false,
}: DocumentCardProps) {
  const getStatusBadge = () => {
    const statusConfig = {
      approved: { label: 'Aprobado', className: 'bg-green-100 text-green-800' },
      pending_validation: { label: 'Pendiente', className: 'bg-yellow-100 text-yellow-800' },
      rejected: { label: 'Rechazado', className: 'bg-red-100 text-red-800' },
      archived: { label: 'Archivado', className: 'bg-gray-100 text-gray-800' },
      draft: { label: 'Borrador', className: 'bg-gray-100 text-gray-800' },
    }

    const config = statusConfig[document.status as keyof typeof statusConfig] || statusConfig.draft

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
        {config.label}
      </span>
    )
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
            <p className="text-sm text-gray-600 mb-3 line-clamp-2">{document.description}</p>
          )}
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>
              Creado: {new Date(document.created_at).toLocaleDateString('es-UY')}
            </span>
            {document.folder_id && (
              <span className="text-gray-400">• Carpeta: {document.folder_id}</span>
            )}
          </div>
        </div>
      </div>

      {showActions && (
        <div className="mt-4 flex items-center gap-2">
          {onView && (
            <button
              onClick={onView}
              disabled={processing}
              className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-md transition"
            >
              Ver Detalles
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

