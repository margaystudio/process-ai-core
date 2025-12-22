'use client'

import { useState, useEffect } from 'react'
import { Document, getDocumentRuns, getArtifactUrl } from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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

  useEffect(() => {
    async function loadPdf() {
      if (!isOpen) return

      try {
        setLoadingPdf(true)
        const runs = await getDocumentRuns(document.id)
        if (runs.length > 0 && runs[0].artifacts.pdf) {
          // Convertir URL relativa a absoluta
          const relativeUrl = runs[0].artifacts.pdf
          const absoluteUrl = relativeUrl.startsWith('http') 
            ? relativeUrl 
            : `${API_URL}${relativeUrl}`
          setPdfUrl(absoluteUrl)
        }
      } catch (err) {
        console.error('Error cargando PDF:', err)
      } finally {
        setLoadingPdf(false)
      }
    }

    loadPdf()
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
            <h2 className="text-xl font-semibold text-gray-900">
              Revisar Documento: {document.name}
            </h2>
            <button
              onClick={onClose}
              disabled={processing}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          {/* Preview del PDF */}
          <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
            {loadingPdf ? (
              <div className="h-96 flex items-center justify-center bg-gray-50">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                  <p className="text-sm text-gray-600">Cargando PDF...</p>
                </div>
              </div>
            ) : pdfUrl ? (
              <iframe
                src={pdfUrl}
                className="w-full h-96"
                title="Preview del documento"
              />
            ) : (
              <div className="h-96 flex items-center justify-center bg-gray-50">
                <p className="text-gray-500">No hay PDF disponible para este documento</p>
              </div>
            )}
          </div>

          {/* Información del documento */}
          <div className="mb-4 text-sm text-gray-600">
            <p>
              <span className="font-medium">Estado:</span>{' '}
              {document.status === 'pending_validation' ? 'Pendiente de validación' : document.status}
            </p>
            <p>
              <span className="font-medium">Creado:</span>{' '}
              {new Date(document.created_at).toLocaleDateString('es-UY')}
            </p>
          </div>

          {/* Acciones */}
          <div className="flex items-center justify-end gap-3">
            <button
              onClick={onClose}
              disabled={processing}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              onClick={onApprove}
              disabled={processing}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {processing ? 'Aprobando...' : 'Aprobar Documento'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

