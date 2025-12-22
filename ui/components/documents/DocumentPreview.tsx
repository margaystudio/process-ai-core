'use client'

import { useState, useEffect } from 'react'
import { getDocumentRuns, getArtifactUrl } from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface DocumentPreviewProps {
  documentId: string
}

export default function DocumentPreview({ documentId }: DocumentPreviewProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadPdf() {
      try {
        setLoading(true)
        setError(null)
        const runs = await getDocumentRuns(documentId)
        if (runs.length > 0 && runs[0].artifacts.pdf) {
          // Convertir URL relativa a absoluta
          const relativeUrl = runs[0].artifacts.pdf
          const absoluteUrl = relativeUrl.startsWith('http') 
            ? relativeUrl 
            : `${API_URL}${relativeUrl}`
          setPdfUrl(absoluteUrl)
        } else {
          setError('No hay PDF disponible')
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando PDF')
      } finally {
        setLoading(false)
      }
    }

    loadPdf()
  }, [documentId])

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 sticky top-4">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Preview del Documento</h3>

      {loading ? (
        <div className="h-96 flex items-center justify-center bg-gray-50 rounded">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-sm text-gray-600">Cargando PDF...</p>
          </div>
        </div>
      ) : error ? (
        <div className="h-96 flex items-center justify-center bg-gray-50 rounded">
          <p className="text-sm text-gray-500">{error}</p>
        </div>
      ) : pdfUrl ? (
        <div className="border border-gray-200 rounded overflow-hidden">
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

