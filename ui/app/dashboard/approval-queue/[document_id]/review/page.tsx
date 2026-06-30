'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft,
  Shield,
  CheckCircle2,
  MessageSquare,
  X,
  AlertCircle,
} from 'lucide-react'
import { Button } from '@/shared/ui/components'
import { useLoading } from '@/contexts/LoadingContext'
import { useUserId } from '@/hooks/useUserId'
import {
  useCanApproveDocuments,
  useCanRejectDocuments,
} from '@/hooks/useHasPermission'
import { getDocumentActions } from '@/lib/documentActions'
import {
  getDocument,
  getDocumentVersions,
  getVersionPreviewPdfUrl,
  approveDocumentValidation,
  rejectDocumentValidation,
  Document,
  DocumentVersion,
} from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Helpers ──────────────────────────────────────────────────────────────────

function typeLabel(raw: string | undefined): string {
  if (!raw) return ''
  const map: Record<string, string> = {
    process: 'Procedimiento',
    policy: 'Política',
    recipe: 'Receta',
  }
  return map[raw] ?? raw
}

// ── Skeleton del PDF ──────────────────────────────────────────────────────────

function PdfSkeleton() {
  return (
    <div className="flex h-[600px] flex-col items-center justify-center gap-3 rounded-[14px] border border-line bg-ink-50">
      <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-ink-200 border-t-indigo" />
      <p className="text-[13px] text-ink-400">Cargando documento…</p>
    </div>
  )
}

// ── Modal "Pedir cambios" ─────────────────────────────────────────────────────

interface RejectSheetProps {
  docName: string
  processing: boolean
  onCancel: () => void
  onConfirm: (obs: string) => void
}

function RejectSheet({ docName, processing, onCancel, onConfirm }: RejectSheetProps) {
  const [obs, setObs] = useState('')
  const isEmpty = obs.trim().length === 0

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isEmpty) onConfirm(obs.trim())
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-title"
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink-900/40 backdrop-blur-[2px]"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative w-full max-w-[520px] rounded-t-[20px] bg-white p-7 shadow-modal sm:rounded-[20px]">
        {/* Close */}
        <button
          onClick={onCancel}
          disabled={processing}
          aria-label="Cancelar"
          className="absolute right-5 top-5 grid h-8 w-8 place-items-center rounded-full text-ink-400 hover:bg-ink-100 hover:text-ink-700 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring disabled:opacity-40"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>

        <h2 id="reject-title" className="text-[18px] font-extrabold text-ink-900">
          Pedir cambios
        </h2>
        <p className="mt-1 text-[13px] text-ink-500">
          El documento{' '}
          <span className="font-semibold text-ink-700">&ldquo;{docName}&rdquo;</span>{' '}
          volverá al creador con tus observaciones.
        </p>

        <form onSubmit={handleSubmit} className="mt-5">
          <label
            htmlFor="observations"
            className="mb-2 block text-sm font-semibold text-ink-700"
          >
            Observaciones <span className="text-danger" aria-hidden="true">*</span>
          </label>
          <textarea
            id="observations"
            value={obs}
            onChange={(e) => setObs(e.target.value)}
            required
            rows={6}
            disabled={processing}
            placeholder="Describí qué debe corregir el creador antes de volver a enviar…"
            className="w-full rounded-md border border-ink-300 bg-white px-3 py-2 text-body text-ink-800 placeholder:text-ink-500 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring disabled:bg-ink-50 disabled:text-ink-500"
            aria-describedby="obs-hint"
          />
          <p id="obs-hint" className="mt-1 text-xs text-ink-500">
            Campo requerido. El creador verá este texto al recibir la devolución.
          </p>

          <div className="mt-5 flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={onCancel}
              disabled={processing}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="danger"
              size="md"
              disabled={processing || isEmpty}
            >
              <MessageSquare className="h-4 w-4" aria-hidden="true" />
              {processing ? 'Enviando…' : 'Enviar observaciones'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DocumentReviewPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params.document_id as string
  const { withLoading } = useLoading()

  const userId = useUserId()
  const { hasPermission: canApprovePermission } = useCanApproveDocuments()
  const { hasPermission: canRejectPermission } = useCanRejectDocuments()

  const [doc, setDoc] = useState<Document | null>(null)
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfLoading, setPdfLoading] = useState(true)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)
  const [showRejectSheet, setShowRejectSheet] = useState(false)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // ── Carga inicial ────────────────────────────────────────────────────────
  const loadDocument = useCallback(async () => {
    if (!documentId) return
    let blobUrl: string | null = null
    try {
      setLoading(true)
      setError(null)
      setPdfLoading(true)

      const [docData, versionsData] = await Promise.all([
        getDocument(documentId),
        getDocumentVersions(documentId),
      ])
      setDoc(docData)
      setVersions(versionsData)

      // PDF desde versión IN_REVIEW (fuente de verdad para aprobación)
      const inReviewVersion = versionsData.find(
        (v) => v.version_status === 'IN_REVIEW'
      )
      const pdfSourceUrl = inReviewVersion
        ? getVersionPreviewPdfUrl(documentId, inReviewVersion.id)
        : null

      if (pdfSourceUrl) {
        const urlWithCache = `${pdfSourceUrl}${pdfSourceUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
        try {
          const res = await fetch(urlWithCache, { cache: 'no-store' })
          if (res.ok) {
            const blob = await res.blob()
            blobUrl = URL.createObjectURL(blob)
            setPdfUrl(blobUrl)
          } else {
            setPdfUrl(urlWithCache)
          }
        } catch {
          setPdfUrl(urlWithCache)
        }
      } else {
        setPdfUrl(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error cargando documento')
    } finally {
      setLoading(false)
      setPdfLoading(false)
    }

    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [documentId])

  useEffect(() => {
    const cleanup = loadDocument()
    return () => {
      cleanup.then((fn) => fn?.())
    }
  }, [loadDocument])

  // ── Gating con getDocumentActions ─────────────────────────────────────────
  const inReviewVersion = versions.find((v) => v.version_status === 'IN_REVIEW')
  const hasInReviewVersion = Boolean(inReviewVersion)
  const inReviewCreatedBy = inReviewVersion?.created_by ?? null

  const actions = getDocumentActions({
    status: (doc?.status ?? 'draft') as Parameters<typeof getDocumentActions>[0]['status'],
    hasDraftVersion: versions.some((v) => v.version_status === 'DRAFT'),
    hasInReviewVersion,
    userId,
    draftCreatedBy: versions.find((v) => v.version_status === 'DRAFT')?.created_by ?? null,
    inReviewCreatedBy,
    canApprovePermission,
    canRejectPermission,
    canEditPermission: false,
    canDeletePermission: false,
  })

  // ¿Es el creador de la versión en revisión? (muestra aviso en vez de botones)
  const isCreatorOfInReview =
    Boolean(userId) &&
    Boolean(inReviewCreatedBy) &&
    userId === inReviewCreatedBy

  // ── Acciones ──────────────────────────────────────────────────────────────
  const handleApprove = async () => {
    if (!doc) return
    await withLoading(async () => {
      setProcessing(true)
      try {
        await approveDocumentValidation(documentId)
        setSuccessMsg('Documento aprobado exitosamente.')
        setTimeout(() => router.push('/dashboard/approval-queue'), 1500)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al aprobar el documento')
        setProcessing(false)
      }
    })
  }

  const handleReject = async (observations: string) => {
    if (!doc) return
    await withLoading(async () => {
      setProcessing(true)
      try {
        await rejectDocumentValidation(documentId, observations)
        setShowRejectSheet(false)
        setSuccessMsg('Observaciones enviadas. El documento volvió al creador.')
        setTimeout(() => router.push('/dashboard/approval-queue'), 1500)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al rechazar el documento')
        setProcessing(false)
      }
    })
  }

  // ── Estados de carga / error sin documento ────────────────────────────────
  if (loading) {
    return (
      <div data-module="process" className="mx-auto max-w-[920px] px-8 pb-[60px] pt-7">
        {/* Back ghost */}
        <div className="mb-4 h-5 w-36 animate-pulse rounded bg-ink-100" />
        {/* Title ghost */}
        <div className="mb-6 space-y-2">
          <div className="h-4 w-24 animate-pulse rounded bg-ink-100" />
          <div className="h-8 w-64 animate-pulse rounded bg-ink-100" />
        </div>
        <PdfSkeleton />
      </div>
    )
  }

  if (error && !doc) {
    return (
      <div data-module="process" className="mx-auto max-w-[920px] px-8 pb-[60px] pt-7">
        <div className="rounded-lg border border-danger-bd bg-danger-bg p-5">
          <p className="mb-3 text-sm text-danger">{error}</p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push('/dashboard/approval-queue')}
          >
            Volver a la bandeja
          </Button>
        </div>
      </div>
    )
  }

  if (!doc) return null

  return (
    <div data-module="process" className="mx-auto max-w-[920px] px-8 pb-[60px] pt-7">
      {/* Back link */}
      <button
        onClick={() => router.push('/dashboard/approval-queue')}
        className="mb-4 inline-flex items-center gap-1.5 text-[13px] font-bold text-ink-500 hover:text-ink-800 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Volver a la bandeja
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-ink-400">{typeLabel(doc.document_type) || 'Documento'}</div>
          <h1 className="mt-0.5 text-[22px] font-extrabold text-ink-900">{doc.name}</h1>
          {doc.description && (
            <p className="mt-1 text-[13px] text-ink-500">{doc.description}</p>
          )}
        </div>
        {/* Estado badge */}
        <span className="mt-1 inline-flex flex-shrink-0 items-center gap-1.5 rounded-pill border border-warning-bd bg-warning-bg px-3 py-[5px] text-[11px] font-extrabold text-warning">
          <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true" />
          Pendiente de aprobación
        </span>
      </div>

      {/* Notificación de éxito */}
      {successMsg && (
        <div className="mt-5 flex items-center gap-2.5 rounded-lg border border-success-bd bg-success-bg p-4 text-sm font-semibold text-success-fg">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
          {successMsg}
        </div>
      )}

      {/* Error inline */}
      {error && (
        <div className="mt-5 flex items-center gap-2.5 rounded-lg border border-danger-bd bg-danger-bg p-4 text-sm text-danger">
          <AlertCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          {error}
        </div>
      )}

      {/* Preview del documento */}
      <div className="mt-6 rounded-[14px] border border-line bg-surface p-6 shadow-card">
        {/* Aviso: representación derivada */}
        <div className="mb-4 flex items-center gap-2 rounded-[10px] border border-indigo-border bg-indigo-tint px-3.5 py-2.5 text-[11.5px] text-indigo">
          <Shield className="h-[15px] w-[15px] flex-shrink-0" aria-hidden="true" />
          Estás revisando la representación derivada. El archivo original es la fuente oficial.
        </div>

        {/* PDF iframe */}
        {pdfLoading ? (
          <PdfSkeleton />
        ) : pdfUrl ? (
          <div className="overflow-hidden rounded-lg border border-ink-200">
            <iframe
              src={`${pdfUrl}#toolbar=0`}
              className="h-[600px] w-full"
              title={`Vista previa: ${doc.name}`}
            />
          </div>
        ) : (
          <div className="flex h-64 flex-col items-center justify-center gap-2 rounded-lg bg-ink-50">
            <p className="text-[13px] font-semibold text-ink-500">
              No hay PDF disponible para este documento
            </p>
            <p className="text-xs text-ink-400">
              La versión en revisión no tiene un archivo generado.
            </p>
          </div>
        )}
      </div>

      {/* Barra de decisión */}
      <div className="mt-6 flex items-center justify-between gap-4">
        {/* Pedir cambios — izquierda */}
        <div>
          {actions.canReject && (
            <Button
              variant="secondary"
              size="md"
              onClick={() => setShowRejectSheet(true)}
              disabled={processing}
              aria-label="Pedir cambios al creador"
            >
              <MessageSquare className="h-4 w-4 text-ink-400" aria-hidden="true" />
              Pedir cambios
            </Button>
          )}
        </div>

        {/* Aprobar — derecha */}
        <div className="flex items-center gap-3">
          {/* Aviso si el usuario es el creador de la versión */}
          {isCreatorOfInReview && !actions.canApprove && !actions.canReject && (
            <p className="text-[12.5px] text-ink-500">
              No podés aprobar tu propia versión.
            </p>
          )}

          {/* Microcopy solo si puede aprobar */}
          {actions.canApprove && (
            <span className="text-[12.5px] text-ink-400">
              Tu aprobación lo convierte en documento oficial.
            </span>
          )}

          {actions.canApprove && (
            <Button
              variant="create"
              size="md"
              onClick={handleApprove}
              disabled={processing}
              aria-label="Aprobar documento"
            >
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {processing ? 'Procesando…' : 'Aprobar documento'}
            </Button>
          )}

          {/* Si no puede hacer nada (sin permisos, no creador) */}
          {!actions.canApprove && !actions.canReject && !isCreatorOfInReview && !loading && (
            <p className="text-[12.5px] text-ink-500">
              No tenés permisos para decidir sobre este documento.
            </p>
          )}
        </div>
      </div>

      {/* Modal "Pedir cambios" */}
      {showRejectSheet && (
        <RejectSheet
          docName={doc.name}
          processing={processing}
          onCancel={() => setShowRejectSheet(false)}
          onConfirm={handleReject}
        />
      )}
    </div>
  )
}
