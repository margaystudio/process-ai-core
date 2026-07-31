'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { AlertCircle, Download, ExternalLink, Loader2, X } from 'lucide-react'
import { downloadVersionPdf, fetchArtifact, getVersionPdfUrl, isFrozenVersionStatus } from '@/lib/api'
import type { VersionPdfTarget } from '@/hooks/usePdfViewer'
import { Button, buttonVariants } from '@/shared/ui/components/button'
import { cn } from '@/shared/ui/cn'

interface ArtifactViewerModalProps {
  isOpen: boolean
  onClose: () => void
  /**
   * Ruta del artifact (viene del backend, ej. `/api/v1/artifacts/{run_id}/process.pdf`).
   * Requiere sesión: se pide con `fetchArtifact` (fetch autenticado), nunca como
   * `src`/`href` directo. Si no se provee, se usa runId + filename como fallback (deprecated).
   */
  artifactUrl?: string
  runId?: string
  filename?: string
  type: 'json' | 'markdown' | 'pdf'
  /**
   * Cuando está definido, para type 'pdf' se sirve el PDF de esa versión en
   * lugar del artifact del run: el congelado si está APPROVED, si no el preview.
   */
  versionPreviewPdf?: VersionPdfTarget | null
}

export default function ArtifactViewerModal({
  isOpen,
  onClose,
  artifactUrl,
  runId = '',
  filename = '',
  type,
  versionPreviewPdf,
}: ArtifactViewerModalProps) {
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfFrameLoading, setPdfFrameLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  // Separado de `error` (que oculta el visor): un fallo al descargar no debe
  // tapar el PDF que ya se está mostrando, solo avisar junto al botón.
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const blobUrlRef = useRef<string | null>(null)

  useEffect(() => {
    if (!isOpen) {
      setContent(null)
      setPdfUrl(null)
      setPdfFrameLoading(false)
      setError(null)
      setDownloadError(null)
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
          absoluteUrl = getVersionPdfUrl(
            versionPreviewPdf.documentId,
            versionPreviewPdf.versionId,
            versionPreviewPdf.versionStatus
          )
        } else if (artifactUrl) {
          // Ruta del artifact que viene del backend (bare path de nuestra API).
          absoluteUrl = artifactUrl
        } else {
          // Fallback deprecated: reconstruir desde runId + filename.
          absoluteUrl = `/api/v1/artifacts/${runId}/${filename}`
        }

        if (type === 'pdf') {
          setPdfFrameLoading(true)
          // El PDF congelado se sirve con `private, no-cache` + ETag: el navegador
          // lo guarda y revalida en cada apertura, resolviendo en 304 sin cuerpo.
          // Cache-bustearlo con ?t= rompería eso (cada URL sería una entrada
          // nueva) y volvería a bajar el PDF entero, así que solo se bustea el
          // preview regenerado. `cache: 'default'` es el modo que revalida.
          const isFrozen = Boolean(versionPreviewPdf) && isFrozenVersionStatus(versionPreviewPdf?.versionStatus)
          const pdfRequestUrl = isFrozen
            ? absoluteUrl
            : `${absoluteUrl}${absoluteUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
          try {
            // `fetchArtifact` agrega el header Authorization: el endpoint de
            // artifacts de nuestra API lo exige (401 sin él), y ahora además
            // verifica el permiso sobre la carpeta del documento del run.
            const response = await fetchArtifact(pdfRequestUrl, {
              cache: isFrozen ? 'default' : 'no-store',
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
              } else if (!isPdfBytes && blob.size < 10000) {
                setPdfFrameLoading(false)
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
          // Mismo endpoint que el PDF: requiere Authorization (fetchArtifact lo agrega).
          const response = await fetchArtifact(absoluteUrl, { signal: abortController.signal })
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
    // artifactUrl es un prop primitivo (string) y versionPreviewPdf viene de
    // useState en usePdfViewer (referencia estable salvo que cambie de verdad):
    // agregarlos no altera cuándo corre este efecto en la práctica.
  }, [isOpen, runId, filename, type, artifactUrl, versionPreviewPdf, versionPreviewPdf?.documentId, versionPreviewPdf?.versionId, versionPreviewPdf?.versionStatus])

  useEffect(() => {
    if (error) {
      setPdfFrameLoading(false)
    }
  }, [error])

  /**
   * Descarga el PDF como archivo.
   *
   * Vuelve a pedirlo al backend con `download=1` en lugar de guardar el blob ya
   * cargado: así el nombre del archivo lo decide el servidor (conserva el
   * original en los documentos importados) y la descarga pasa por el mismo
   * camino que la vista — incluido el sello de versión superada.
   *
   * Para un artifact de run (URL firmada, sin versión) no hay endpoint con ese
   * parámetro: se guarda el blob que ya está en memoria.
   */
  const handleDownload = async () => {
    setDownloading(true)
    setDownloadError(null)
    try {
      if (versionPreviewPdf) {
        await downloadVersionPdf(
          versionPreviewPdf.documentId,
          versionPreviewPdf.versionId,
          versionPreviewPdf.versionStatus,
        )
      } else if (pdfUrl) {
        const link = document.createElement('a')
        link.href = pdfUrl
        link.download = filename || 'documento.pdf'
        document.body.appendChild(link)
        link.click()
        link.remove()
      }
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'No se pudo descargar el PDF')
    } finally {
      setDownloading(false)
    }
  }

  if (!isOpen) return null

  const pdfViewerSrc = pdfUrl
    ? `${pdfUrl}#toolbar=1&navpanes=0&statusbar=0&messages=0`
    : null
  const showPdfLoadingState = type === 'pdf' && !error && !pdfUrl

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
        <div className="relative bg-white rounded-lg shadow-xl max-w-6xl w-full h-[90vh] flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-ink-200">
            <h2 className="text-h2 text-ink-900">{getTitle()}</h2>
            <button
              onClick={onClose}
              className="text-ink-400 hover:text-ink-600 text-2xl"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Content */}
          <div
            className={`flex-1 min-h-0 p-6 ${
              type === 'pdf' && pdfUrl && !loading && !error ? 'overflow-hidden' : 'overflow-auto'
            }`}
          >
            {showPdfLoadingState ? (
              <div className="flex h-full min-h-[24rem] items-center justify-center rounded-lg border border-ink-200 bg-white">
                <div className="flex flex-col items-center gap-4">
                  <Image
                    src="/margay-spiner.png"
                    alt="Cargando PDF"
                    width={64}
                    height={64}
                    className="h-16 w-16 object-contain animate-spin"
                  />
                  <p className="text-sm font-medium text-ink-600">Cargando PDF...</p>
                </div>
              </div>
            ) : loading ? (
              <div className="flex items-center justify-center h-96">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-2"></div>
                  <p className="text-sm text-ink-600">Cargando contenido...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-96">
                <div className="text-center">
                  <p className="text-danger">{error}</p>
                </div>
              </div>
            ) : type === 'pdf' && pdfUrl ? (
              <div className="relative h-full min-h-0 border border-ink-200 rounded-lg overflow-hidden flex flex-col">
                <div className="flex flex-col gap-2 border-b border-ink-200 bg-ink-50 p-3">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={handleDownload}
                      disabled={downloading}
                      aria-busy={downloading}
                    >
                      {downloading ? (
                        <Loader2 className="animate-spin" aria-hidden="true" />
                      ) : (
                        <Download aria-hidden="true" />
                      )}
                      {downloading ? 'Descargando…' : 'Descargar'}
                    </Button>
                    <a
                      href={pdfUrl}
                      target="_blank"
                      rel="noreferrer"
                      className={cn(buttonVariants({ variant: 'secondary', size: 'sm' }))}
                    >
                      <ExternalLink aria-hidden="true" />
                      Abrir en pestaña
                    </a>
                  </div>
                  {downloadError && (
                    <div
                      role="alert"
                      className="flex items-start gap-2 rounded-lg border border-danger-bd bg-danger-bg p-2 text-sm text-danger"
                    >
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                      <span>{downloadError}</span>
                    </div>
                  )}
                </div>
                <iframe
                  src={pdfViewerSrc ?? undefined}
                  className="w-full h-full min-h-0"
                  title="Preview del PDF"
                  onLoad={() => setPdfFrameLoading(false)}
                />
                {pdfFrameLoading && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-white">
                    <div className="flex flex-col items-center gap-4">
                      <Image
                        src="/margay-spiner.png"
                        alt="Cargando PDF"
                        width={64}
                        height={64}
                        className="h-16 w-16 object-contain animate-spin"
                      />
                      <p className="text-sm font-medium text-ink-600">Cargando PDF...</p>
                    </div>
                  </div>
                )}
              </div>
            ) : type === 'json' && content ? (
              <div className="border border-ink-200 rounded-lg overflow-hidden">
                <pre className="p-4 bg-ink-50 overflow-auto max-h-[600px] text-sm">
                  {JSON.stringify(JSON.parse(content), null, 2)}
                </pre>
              </div>
            ) : type === 'markdown' && content ? (
              <div className="border border-ink-200 rounded-lg overflow-hidden">
                <div className="p-4 bg-white overflow-auto max-h-[600px] prose prose-sm max-w-none">
                  <pre className="whitespace-pre-wrap text-sm font-mono">{content}</pre>
                </div>
              </div>
            ) : null}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-ink-200">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-ink-700 bg-ink-100 rounded-md hover:bg-ink-200"
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}



