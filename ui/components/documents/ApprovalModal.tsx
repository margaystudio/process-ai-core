'use client'

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { Document, fetchArtifactBlobUrl, getDocumentRuns } from '@/lib/api'
import { Skeleton } from '@/shared/ui/components'
import { formatDate } from '@/utils/dateFormat'

interface ApprovalModalProps {
  document: Document
  isOpen: boolean
  onClose: () => void
  onApprove: () => void
  processing?: boolean
}

export default function ApprovalModal({
  document,
  isOpen,
  onClose,
  onApprove,
  processing = false,
}: ApprovalModalProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loadingPdf, setLoadingPdf] = useState(true)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  useEffect(() => {
    if (!isOpen) return

    let cancelled = false

    async function loadPdf() {
      try {
        setLoadingPdf(true)
        setPdfError(null)
        const runs = await getDocumentRuns(document.id)
        if (runs.length > 0 && runs[0].artifacts.pdf) {
          // fetch autenticado + blob URL: el endpoint de artifacts exige
          // Authorization, un <iframe src> directo daría 401.
          const blobUrl = await fetchArtifactBlobUrl(runs[0].artifacts.pdf)
          if (cancelled) {
            URL.revokeObjectURL(blobUrl)
            return
          }
          blobUrlRef.current = blobUrl
          setPdfUrl(blobUrl)
        }
      } catch (err) {
        if (!cancelled) setPdfError(err instanceof Error ? err.message : 'Error cargando PDF')
        console.error('Error cargando PDF:', err)
      } finally {
        if (!cancelled) setLoadingPdf(false)
      }
    }

    loadPdf()

    return () => {
      cancelled = true
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
    }
  }, [isOpen, document.id])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-5xl w-full p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-h2 text-ink-900">
              Revisar Documento: {document.name}
            </h2>
            <button
              onClick={onClose}
              disabled={processing}
              className="text-ink-400 hover:text-ink-600"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Preview del PDF */}
          <div className="mb-4 border border-ink-200 rounded-lg overflow-hidden">
            {loadingPdf ? (
              <Skeleton className="h-96 w-full rounded-none" />
            ) : pdfUrl ? (
              <iframe
                src={pdfUrl}
                className="w-full h-96"
                title="Preview del documento"
              />
            ) : (
              <div className="h-96 flex items-center justify-center bg-ink-50">
                <p className="text-ink-500">
                  {pdfError || 'No hay PDF disponible para este documento'}
                </p>
              </div>
            )}
          </div>

          {/* Información del documento */}
          <div className="mb-4 text-sm text-ink-600">
            <p>
              <span className="font-medium">Estado:</span>{' '}
              {document.status === 'pending_validation' ? 'Pendiente de validación' : document.status}
            </p>
            <p>
              <span className="font-medium">Creado:</span>{' '}
              {formatDate(document.created_at)}
            </p>
          </div>

          {/* Acciones */}
          <div className="flex items-center justify-end gap-3">
            <button
              onClick={onClose}
              disabled={processing}
              className="px-4 py-2 text-sm text-ink-700 bg-ink-100 rounded-md hover:bg-ink-200 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              onClick={onApprove}
              disabled={processing}
              className="px-4 py-2 text-sm bg-create text-white rounded-md hover:bg-create-hover disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {processing ? 'Aprobando...' : 'Aprobar Documento'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

