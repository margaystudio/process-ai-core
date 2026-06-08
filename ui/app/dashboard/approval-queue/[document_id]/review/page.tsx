'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Card, CardBody, Button } from '@/shared/ui/components'
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
        <div className="mx-auto max-w-7xl">
          <div className="animate-pulse text-ink-500">Cargando documento...</div>
        </div>
      </div>
    )
  }

  if (error && !document) {
    return (
      <div className="p-8">
        <div className="mx-auto max-w-7xl">
          <div className="rounded-md border border-danger-bd bg-danger-bg p-4">
            <p className="mb-3 text-sm text-danger">Error: {error}</p>
            <Button variant="secondary" size="sm" onClick={() => router.push('/dashboard/approval-queue')}>
              Volver a la cola de aprobación
            </Button>
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
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/dashboard/approval-queue')}
            className="mb-4 flex items-center gap-1.5 text-sm font-semibold text-ink-500 hover:text-ink-800"
          >
            <ArrowLeft className="h-4 w-4" />
            Volver a la cola de aprobación
          </button>
          <h1 className="text-h1 text-ink-900">
            Revisar documento: {document.name}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            Estado: {document.status === 'pending_validation' ? 'Pendiente de validación' : document.status}
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-md border border-danger-bd bg-danger-bg p-4 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Columna izquierda: Preview del PDF */}
          <div className="lg:col-span-2">
            <Card>
              <CardBody>
                <h2 className="mb-4 text-h3 text-ink-900">Vista previa del documento</h2>

                {pdfUrl ? (
                  <div className="overflow-hidden rounded-lg border border-ink-200">
                    <iframe
                      src={`${pdfUrl}#toolbar=0`}
                      className="h-[600px] w-full"
                      title="Preview del documento"
                    />
                  </div>
                ) : (
                  <div className="flex h-96 items-center justify-center rounded-lg bg-ink-50">
                    <p className="text-ink-500">No hay PDF disponible para este documento</p>
                  </div>
                )}
              </CardBody>
            </Card>
          </div>

          {/* Columna derecha: Formulario de revisión */}
          <div className="lg:col-span-1">
            <Card className="sticky top-4">
              <CardBody>
                <h2 className="mb-4 text-h3 text-ink-900">Revisión</h2>

                <div className="mb-4">
                  <label htmlFor="observations" className="mb-2 block text-sm font-semibold text-ink-700">
                    Observaciones
                  </label>
                  <textarea
                    id="observations"
                    value={observations}
                    onChange={(e) => setObservations(e.target.value)}
                    placeholder="Agregá tus observaciones sobre el documento..."
                    rows={8}
                    className="w-full rounded-md border border-ink-300 bg-white px-3 py-2 text-body text-ink-800 placeholder:text-ink-500 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring"
                  />
                  <p className="mt-1 text-xs text-ink-500">
                    Las observaciones son opcionales al aprobar, pero requeridas al rechazar.
                  </p>
                </div>

                <div className="space-y-3">
                  <Button variant="create" className="w-full" onClick={handleApprove} disabled={processing}>
                    {processing ? 'Procesando...' : 'Aprobar documento'}
                  </Button>

                  <Button
                    variant="danger"
                    className="w-full"
                    onClick={handleReject}
                    disabled={processing || !observations.trim()}
                  >
                    {processing ? 'Procesando...' : 'Rechazar documento'}
                  </Button>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
