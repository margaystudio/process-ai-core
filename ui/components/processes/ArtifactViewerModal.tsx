'use client'

import { useState, useEffect } from 'react'
import { getArtifactUrl } from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ArtifactViewerModalProps {
  isOpen: boolean
  onClose: () => void
  runId: string
  filename: string
  type: 'json' | 'markdown' | 'pdf'
}

export default function ArtifactViewerModal({
  isOpen,
  onClose,
  runId,
  filename,
  type,
}: ArtifactViewerModalProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setContent(null)
      setPdfUrl(null)
      setError(null)
      return
    }

    async function loadContent() {
      try {
        setLoading(true)
        setError(null)

        const artifactUrl = getArtifactUrl(runId, filename)
        const absoluteUrl = artifactUrl.startsWith('http') 
          ? artifactUrl 
          : `${API_URL}${artifactUrl}`

        if (type === 'pdf') {
          // Para PDF, cargar como blob para evitar cache
          const urlWithCacheBust = `${absoluteUrl}?t=${Date.now()}`
          try {
            const response = await fetch(urlWithCacheBust, {
              cache: 'no-store',
            })
            if (response.ok) {
              const blob = await response.blob()
              const blobUrl = URL.createObjectURL(blob)
              setPdfUrl(blobUrl)
            } else {
              setPdfUrl(urlWithCacheBust)
            }
          } catch (fetchErr) {
            setPdfUrl(urlWithCacheBust)
          }
        } else {
          // Para JSON y Markdown, cargar como texto
          const response = await fetch(absoluteUrl)
          if (!response.ok) {
            throw new Error(`Error al cargar ${filename}`)
          }
          const text = await response.text()
          setContent(text)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cargar el archivo')
      } finally {
        setLoading(false)
      }
    }

    loadContent()

    // Cleanup: revocar blob URL cuando el componente se desmonte
    return () => {
      if (pdfUrl && pdfUrl.startsWith('blob:')) {
        URL.revokeObjectURL(pdfUrl)
      }
    }
  }, [isOpen, runId, filename, type])

  if (!isOpen) return null

  const getTitle = () => {
    switch (type) {
      case 'json':
        return 'Vista JSON'
      case 'markdown':
        return 'Vista Markdown'
      case 'pdf':
        return 'Vista PDF'
      default:
        return 'Vista de Archivo'
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">{getTitle()}</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl"
            >
              ✕
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-auto p-6">
            {loading ? (
              <div className="flex items-center justify-center h-96">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                  <p className="text-sm text-gray-600">Cargando contenido...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-96">
                <div className="text-center">
                  <p className="text-red-600">{error}</p>
                </div>
              </div>
            ) : type === 'pdf' && pdfUrl ? (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <iframe
                  src={`${pdfUrl}#toolbar=0`}
                  className="w-full h-[600px]"
                  title="Preview del PDF"
                />
              </div>
            ) : type === 'json' && content ? (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <pre className="p-4 bg-gray-50 overflow-auto max-h-[600px] text-sm">
                  {JSON.stringify(JSON.parse(content), null, 2)}
                </pre>
              </div>
            ) : type === 'markdown' && content ? (
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <div className="p-4 bg-white overflow-auto max-h-[600px] prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap text-sm font-mono">{content}</pre>
                </div>
              </div>
            ) : null}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

