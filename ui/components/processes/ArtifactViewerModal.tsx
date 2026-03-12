'use client'

import { useState, useEffect, useRef } from 'react'
import { getArtifactUrl, getVersionPreviewPdfUrl } from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ArtifactViewerModalProps {
  isOpen: boolean
  onClose: () => void
  runId: string
  filename: string
  type: 'json' | 'markdown' | 'pdf'
  /** Cuando está definido, para type 'pdf' se usa esta URL (PDF del borrador actual) en lugar del artifact del run. */
  versionPreviewPdf?: { documentId: string; versionId: string } | null
}

export default function ArtifactViewerModal({
  isOpen,
  onClose,
  runId,
  filename,
  type,
  versionPreviewPdf,
}: ArtifactViewerModalProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfZoom, setPdfZoom] = useState(100)
  const blobUrlRef = useRef<string | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setContent(null)
      setPdfUrl(null)
      setPdfZoom(100)
      setError(null)
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
      return
    }

    const abortController = new AbortController()

    async function loadContent() {
      try {
        setLoading(true)
        setError(null)

        let absoluteUrl: string
        if (type === 'pdf' && versionPreviewPdf) {
          absoluteUrl = getVersionPreviewPdfUrl(versionPreviewPdf.documentId, versionPreviewPdf.versionId)
        } else {
          const artifactUrl = getArtifactUrl(runId, filename)
          absoluteUrl = artifactUrl.startsWith('http') ? artifactUrl : `${API_URL}${artifactUrl}`
        }

        if (type === 'pdf') {
          const urlWithCacheBust = `${absoluteUrl}${absoluteUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
          try {
            const response = await fetch(urlWithCacheBust, {
              cache: 'no-store',
              credentials: 'include',
              signal: abortController.signal,
            })

            const contentType = response.headers.get('content-type') || ''
            if (response.ok) {
              const blob = await response.blob()
              const isPdfType = blob.type === 'application/pdf' || contentType.includes('application/pdf')
              const isPdfBytes = blob.size >= 5 && (await blob.slice(0, 5).text()) === '%PDF-'
              if (isPdfType && isPdfBytes) {
                const blobUrl = URL.createObjectURL(blob)
                blobUrlRef.current = blobUrl
                setPdfUrl(blobUrl)
                setPdfZoom(100)
              } else if (!isPdfBytes && blob.size < 10000) {
                const text = await blob.text()
                setError(text.slice(0, 200) || 'La respuesta no es un PDF válido.')
              } else {
                setError('La respuesta no es un PDF válido. No se pudo generar el documento.')
              }
            } else {
              const text = await response.text().catch(() => '')
              setError(text || `Error ${response.status} al cargar el PDF`)
            }
          } catch (fetchErr) {
            if ((fetchErr as Error).name === 'AbortError') return
            setError(fetchErr instanceof Error ? fetchErr.message : 'Error al cargar el PDF')
          }
        } else {
          const response = await fetch(absoluteUrl, { signal: abortController.signal })
          if (!response.ok) {
            throw new Error(`Error al cargar ${filename}`)
          }
          const text = await response.text()
          setContent(text)
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Error al cargar el archivo')
      } finally {
        setLoading(false)
      }
    }

    loadContent()

    return () => {
      abortController.abort()
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current)
        blobUrlRef.current = null
      }
    }
  }, [isOpen, runId, filename, type, versionPreviewPdf?.documentId, versionPreviewPdf?.versionId])

  if (!isOpen) return null

  const pdfViewerSrc = pdfUrl
    ? `${pdfUrl}#toolbar=1&navpanes=0&statusbar=0&messages=0&zoom=${pdfZoom}`
    : null

  const handleZoomIn = () => setPdfZoom((z) => Math.min(300, z + 10))
  const handleZoomOut = () => setPdfZoom((z) => Math.max(50, z - 10))
  const handleZoomReset = () => setPdfZoom(100)

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
                <div className="flex items-center justify-between gap-3 p-3 border-b border-gray-200 bg-gray-50">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleZoomOut}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-100"
                    >
                      -
                    </button>
                    <button
                      type="button"
                      onClick={handleZoomReset}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-100"
                    >
                      {pdfZoom}%
                    </button>
                    <button
                      type="button"
                      onClick={handleZoomIn}
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-100"
                    >
                      +
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <a
                      href={pdfUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-100"
                    >
                      Abrir en pestaña
                    </a>
                    <a
                      href={pdfUrl}
                      download={filename || 'preview.pdf'}
                      className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      Descargar
                    </a>
                  </div>
                </div>
                <iframe
                  src={pdfViewerSrc ?? undefined}
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



