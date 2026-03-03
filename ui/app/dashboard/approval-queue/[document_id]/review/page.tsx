'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useLoading } from '@/contexts/LoadingContext'
import {
  getDocument,
  getDocumentRuns,
  getDocumentVersions,
  getVersionPreviewPdfUrl,
  approveDocumentValidation,
  rejectDocumentValidation,
  Document,
} from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function DocumentReviewPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params.document_id as string
  const { withLoading } = useLoading()
  
  const [document, setDocument] = useState<Document | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [observations, setObservations] = useState('')
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    let blobUrl: string | null = null
    
    async function loadDocument() {
      try {
        setLoading(true)
        setError(null)
        
        const [doc, runs, versions] = await Promise.all([
          getDocument(documentId),
          getDocumentRuns(documentId),
          getDocumentVersions(documentId),
        ])
        
        setDocument(doc)
        
        // PDF desde la versión en revisión (fuente de verdad: content_html o content_markdown)
        const inReviewVersion = versions?.find((v: { version_status: string }) => v.version_status === 'IN_REVIEW')
        const pdfSourceUrl = inReviewVersion
          ? getVersionPreviewPdfUrl(documentId, inReviewVersion.id)
          : runs.length > 0 && runs[0].artifacts.pdf
            ? (runs[0].artifacts.pdf.startsWith('http') ? runs[0].artifacts.pdf : `${API_URL}${runs[0].artifacts.pdf}`)
            : null
        
        if (pdfSourceUrl) {
          const urlWithCacheBust = `${pdfSourceUrl}${pdfSourceUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
          try {
            const response = await fetch(urlWithCacheBust, { cache: 'no-store' })
            if (response.ok) {
              const blob = await response.blob()
              blobUrl = URL.createObjectURL(blob)
              setPdfUrl(blobUrl)
            } else {
              setPdfUrl(urlWithCacheBust)
            }
          } catch (fetchErr) {
            setPdfUrl(urlWithCacheBust)
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando documento')
      } finally {
        setLoading(false)
      }
    }

    if (documentId) {
      loadDocument()
    }
    
    // Cleanup: revocar blob URL cuando el componente se desmonte
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl)
      }
    }
  }, [documentId])

  const handleApprove = async () => {
    const confirmed = window.confirm(
      `¿Estás seguro de que deseas aprobar el documento "${document?.name}"?\n\n` +
      `Esta acción marcará el documento como aprobado y estará disponible para su uso.`
    )

    if (!confirmed) {
      return
    }

    await withLoading(async () => {
      setProcessing(true)
      try {
        await approveDocumentValidation(documentId, observations || undefined)
        router.push('/dashboard/approval-queue')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al aprobar documento')
        setProcessing(false)
      }
    })
  }

  const handleReject = async () => {
    if (!observations.trim()) {
      setError('Debes proporcionar observaciones al rechazar el documento')
      return
    }

    const confirmed = window.confirm(
      `¿Estás seguro de que deseas rechazar el documento "${document?.name}"?\n\n` +
      `Observaciones: ${observations}\n\n` +
      `El documento será marcado como rechazado y enviado de vuelta para corrección.`
    )

    if (!confirmed) {
      return
    }

    await withLoading(async () => {
      setProcessing(true)
      try {
        await rejectDocumentValidation(documentId, observations)
        router.push('/dashboard/approval-queue')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al rechazar documento')
        setProcessing(false)
      }
    })
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse text-gray-500">Cargando documento...</div>
        </div>
      </div>
    )
  }

  if (error && !document) {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-700">Error: {error}</p>
            <button
              onClick={() => router.push('/dashboard/approval-queue')}
              className="mt-4 px-4 py-2 bg-gray-200 rounded-md hover:bg-gray-300"
            >
              Volver a la cola de aprobación
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!document) {
    return null
  }

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/dashboard/approval-queue')}
            className="text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            ← Volver a la cola de aprobación
          </button>
          <h1 className="text-3xl font-bold text-gray-900">
            Revisar Documento: {document.name}
          </h1>
          <p className="text-gray-600 mt-1">
            Estado: {document.status === 'pending_validation' ? 'Pendiente de validación' : document.status}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Columna izquierda: Preview del PDF */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Vista Previa del Documento</h2>
              
              {pdfUrl ? (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <iframe
                    src={`${pdfUrl}#toolbar=0`}
                    className="w-full h-[600px]"
                    title="Preview del documento"
                  />
                </div>
              ) : (
                <div className="h-96 flex items-center justify-center bg-gray-50 rounded">
                  <p className="text-gray-500">No hay PDF disponible para este documento</p>
                </div>
              )}
            </div>
          </div>

          {/* Columna derecha: Formulario de revisión */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg border border-gray-200 p-6 sticky top-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Revisión</h2>
              
              <div className="mb-4">
                <label htmlFor="observations" className="block text-sm font-medium text-gray-700 mb-2">
                  Observaciones
                </label>
                <textarea
                  id="observations"
                  value={observations}
                  onChange={(e) => setObservations(e.target.value)}
                  placeholder="Agrega tus observaciones sobre el documento..."
                  rows={8}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Las observaciones son opcionales al aprobar, pero requeridas al rechazar.
                </p>
              </div>

              <div className="space-y-3">
                <button
                  onClick={handleApprove}
                  disabled={processing}
                  className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  {processing ? 'Procesando...' : 'Aprobar Documento'}
                </button>
                
                <button
                  onClick={handleReject}
                  disabled={processing || !observations.trim()}
                  className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  {processing ? 'Procesando...' : 'Rechazar Documento'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

