'use client'

import { useEffect, useRef, useState } from 'react'
import { fetchArtifactBlobUrl, getDocumentRuns } from '@/lib/api'

interface DocumentPreviewProps {
  documentId: string
}

export default function DocumentPreview({ documentId }: DocumentPreviewProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadPdf() {
      try {
        setLoading(true)
        setError(null)
        const runs = await getDocumentRuns(documentId)
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
        } else if (!cancelled) {
          setError('No hay PDF disponible')
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Error cargando PDF')
      } finally {
        if (!cancelled) setLoading(false)
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
  }, [documentId])

  return (
    <div className="bg-white rounded-lg border border-ink-200 p-4 sticky top-4">
      <h3 className="text-h3 text-ink-900 mb-4">Preview del Documento</h3>

      {loading ? (
        <div className="h-96 flex items-center justify-center bg-ink-50 rounded">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-2"></div>
            <p className="text-sm text-ink-600">Cargando PDF...</p>
          </div>
        </div>
      ) : error ? (
        <div className="h-96 flex items-center justify-center bg-ink-50 rounded">
          <p className="text-sm text-ink-500">{error}</p>
        </div>
      ) : pdfUrl ? (
        <div className="border border-ink-200 rounded overflow-hidden">
          <iframe
            src={pdfUrl}
            className="w-full h-96"
            title="Preview del documento"
          />
        </div>
      ) : null}
    </div>
  )
}
