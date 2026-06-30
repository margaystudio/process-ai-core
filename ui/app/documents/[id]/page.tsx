'use client'

import { useState, useEffect } from 'react'
import { CheckCircle } from 'lucide-react'
import { useParams, useRouter } from 'next/navigation'
import {
  getDocument,
  updateDocument,
  deleteDocument,
  getCatalogOptions,
  getDocumentRuns,
  createDocumentRun,
  CatalogOption,
  Document,
  DocumentUpdateRequest,
  listValidations,
  Validation,
  approveDocumentValidation,
  rejectDocumentValidation,
  patchDocumentWithAI,
  getDocumentAuditLog,
  getDocumentVersions,
  getVersionPreviewPdfUrl,
  cancelDocumentSubmission,
  submitVersionForReview,
  getUser,
  AuditLogEntry,
  DocumentVersion,
} from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useLoading } from '@/contexts/LoadingContext'
import { FileType } from '@/components/processes/FileUploadModal'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { FileItemData } from '@/components/processes/FileItem'
import { formatDateTime } from '@/utils/dateFormat'
import { useCanApproveDocuments, useCanRejectDocuments, useHasPermission } from '@/hooks/useHasPermission'
import { useUserId } from '@/hooks/useUserId'
import { useUserRole } from '@/hooks/useUserRole'
import { getDocumentActions } from '@/lib/documentActions'

// Sub-componentes
import { DocumentDetailHeader } from '@/components/documents/DocumentDetailHeader'
import { DocumentBodyCard } from '@/components/documents/DocumentBodyCard'
import { DocumentValidationPanel } from '@/components/documents/DocumentValidationPanel'
import { DocumentCorrectionPanel } from '@/components/documents/DocumentCorrectionPanel'
import { DocumentRunsSection } from '@/components/documents/DocumentRunsSection'
import { DocumentHistorySection } from '@/components/documents/DocumentHistorySection'
import { DocumentMetadataForm } from '@/components/documents/DocumentMetadataForm'

// ─── Skeleton de carga ────────────────────────────────────────────────────────
function DocumentDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl px-8 pb-16 pt-7 animate-pulse" aria-busy="true" aria-label="Cargando documento">
      <div className="mb-6 h-5 w-24 rounded bg-ink-200" />
      <div className="mb-2 h-7 w-2/3 rounded bg-ink-200" />
      <div className="mb-8 flex gap-2">
        <div className="h-5 w-20 rounded-full bg-ink-100" />
        <div className="h-5 w-16 rounded-full bg-ink-100" />
      </div>
      <div className="h-[520px] rounded-[14px] bg-ink-100" />
    </div>
  )
}

// ─── Componente principal ────────────────────────────────────────────────────
export default function DocumentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params.id as string
  const { selectedWorkspaceId } = useWorkspace()
  const { withLoading } = useLoading()

  // Permisos
  const userId = useUserId()
  const { hasPermission: hasApprovePermission } = useCanApproveDocuments()
  const { hasPermission: hasRejectPermission } = useCanRejectDocuments()
  const { hasPermission: hasDocumentEditPermission } = useHasPermission('documents.edit')
  const { hasPermission: hasDocumentDeletePermission } = useHasPermission('documents.delete')
  const { role: userRoleName } = useUserRole()

  // Datos
  const [document, setDocument] = useState<Document | null>(null)
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [validations, setValidations] = useState<Validation[]>([])
  const [runs, setRuns] = useState<Array<{
    run_id: string
    created_at: string
    artifacts: { json?: string; md?: string; pdf?: string }
  }>>([])
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [userDisplayNames, setUserDisplayNames] = useState<Record<string, string>>({})
  const [submitterDisplayName, setSubmitterDisplayName] = useState<string | null>(null)

  // UI state
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSubmittingForReview, setIsSubmittingForReview] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [isPatching, setIsPatching] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [savedDraftBanner, setSavedDraftBanner] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [showNewVersionForm, setShowNewVersionForm] = useState(false)
  const [isNewVersionModalOpen, setIsNewVersionModalOpen] = useState(false)

  // Modales de confirmación
  const [showCancelSubmitConfirm, setShowCancelSubmitConfirm] = useState(false)
  const [showApproveConfirm, setShowApproveConfirm] = useState(false)
  const [showRejectConfirm, setShowRejectConfirm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Formulario metadatos
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState('')
  const [folderId, setFolderId] = useState('')
  const [audience, setAudience] = useState('')
  const [detailLevel, setDetailLevel] = useState('')
  const [contextText, setContextText] = useState('')
  const [audienceOptions, setAudienceOptions] = useState<CatalogOption[]>([])
  const [detailLevelOptions, setDetailLevelOptions] = useState<CatalogOption[]>([])

  // Validaciones / correcciones
  const [approveObservations, setApproveObservations] = useState('')
  const [rejectObservations, setRejectObservations] = useState('')
  const [aiPatchObservations, setAiPatchObservations] = useState('')

  // Nueva versión
  const [revisionNotes, setRevisionNotes] = useState('')
  const [newVersionFiles, setNewVersionFiles] = useState<FileItemData[]>([])

  // PDF viewer
  const { openArtifactFromRun, openVersionPreviewPdf, ModalComponent } = usePdfViewer()

  // ── Carga inicial ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!documentId) return
    loadDocument()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId])

  async function loadDocument() {
    try {
      setLoading(true)
      setError(null)
      const [doc, documentRuns, docValidations, docVersions] = await Promise.all([
        getDocument(documentId),
        getDocumentRuns(documentId).catch(() => []),
        listValidations(documentId).catch(() => []),
        getDocumentVersions(documentId).catch(() => []),
      ])
      setDocument(doc)
      setName(doc.name)
      setDescription(doc.description)
      setStatus(doc.status)
      setFolderId(doc.folder_id || '')
      setRuns(documentRuns)
      setValidations(docValidations)
      setVersions(docVersions)

      if (doc.domain === 'process') {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const { getAccessToken } = await import('@/lib/api-auth')
        const authToken = await getAccessToken()
        const authHeaders: HeadersInit = {}
        if (authToken) authHeaders['Authorization'] = `Bearer ${authToken}`
        const [audienceOpts, detailOpts, processDocResponse] = await Promise.all([
          getCatalogOptions('audience').catch(() => []),
          getCatalogOptions('detail_level').catch(() => []),
          fetch(`${apiUrl}/api/v1/documents/${documentId}/process`, { headers: authHeaders })
            .then((r) => (r.ok ? r.json() : null))
            .catch(() => null),
        ])
        setAudienceOptions(audienceOpts)
        setDetailLevelOptions(detailOpts)
        const processDoc = (processDocResponse as { audience?: string; detail_level?: string; context_text?: string }) || {}
        setAudience(processDoc?.audience || '')
        setDetailLevel(processDoc?.detail_level || '')
        setContextText(processDoc?.context_text || '')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  // ── Resolver nombre del remitente de la versión IN_REVIEW ─────────────────
  const inReviewVersion = versions.find((v) => v.version_status === 'IN_REVIEW')
  const draftVersion = versions.find((v) => v.version_status === 'DRAFT')

  useEffect(() => {
    const createdBy = inReviewVersion?.created_by
    if (!createdBy) { setSubmitterDisplayName(null); return }
    let cancelled = false
    getUser(createdBy)
      .then((u) => { if (!cancelled) setSubmitterDisplayName(u.name?.trim() || u.email || u.id) })
      .catch(() => { if (!cancelled) setSubmitterDisplayName(null) })
    return () => { cancelled = true }
  }, [inReviewVersion?.created_by])

  // ── Resolver nombres de usuarios de validaciones ───────────────────────────
  const validationUserIdsKey = Array.from(
    new Set(
      validations.flatMap((validation) => {
        const v = versions.find((ver) => ver.validation_id === validation.id)
        const ids: string[] = []
        if (v?.created_by) ids.push(v.created_by)
        if (validation.validator_user_id) ids.push(validation.validator_user_id)
        return ids
      })
    )
  ).sort().join(',')

  useEffect(() => {
    const userIds = validationUserIdsKey ? validationUserIdsKey.split(',') : []
    if (userIds.length === 0) return
    let cancelled = false
    Promise.all(
      userIds.map(async (uid) => {
        try {
          const u = await getUser(uid)
          return { id: uid, name: u.name?.trim() || u.email || u.id }
        } catch {
          return { id: uid, name: uid }
        }
      })
    ).then((results) => {
      if (cancelled) return
      const next: Record<string, string> = {}
      results.forEach(({ id, name: n }) => { next[id] = n })
      setUserDisplayNames((prev) => ({ ...prev, ...next }))
    })
    return () => { cancelled = true }
  }, [validationUserIdsKey])

  // ── Selector centralizado de acciones (arregla el bug D4) ─────────────────
  const actions = getDocumentActions({
    status: (document?.status ?? 'draft') as Parameters<typeof getDocumentActions>[0]['status'],
    hasDraftVersion: Boolean(draftVersion),
    hasInReviewVersion: Boolean(inReviewVersion),
    userId,
    draftCreatedBy: draftVersion?.created_by ?? null,
    inReviewCreatedBy: inReviewVersion?.created_by ?? null,
    canApprovePermission: hasApprovePermission ?? false,
    canRejectPermission: hasRejectPermission ?? false,
    canEditPermission: hasDocumentEditPermission ?? false,
    canDeletePermission: hasDocumentDeletePermission ?? false,
  })

  // ── Versión relevante para la previsualización ─────────────────────────────
  function getRelevantPdfVersion(): DocumentVersion | null {
    return (
      versions.find((v) => v.version_status === 'DRAFT' && v.content_type === 'manual_edit') ||
      versions.find((v) => v.version_status === 'IN_REVIEW') ||
      versions.find((v) => v.version_status === 'APPROVED') ||
      versions.find((v) => v.version_status === 'DRAFT') ||
      null
    )
  }

  const previewVersion = getRelevantPdfVersion()
  const pdfUrl = previewVersion ? getVersionPreviewPdfUrl(documentId, previewVersion.id) : null

  // ── Handlers ──────────────────────────────────────────────────────────────
  async function handleSave() {
    if (!document) return
    try {
      setIsSaving(true)
      setError(null)
      const updateData: DocumentUpdateRequest = { name, description, status, folder_id: folderId || undefined }
      if (document.domain === 'process') {
        updateData.audience = audience || undefined
        updateData.detail_level = detailLevel || undefined
        updateData.context_text = contextText || undefined
      }
      const updated = await updateDocument(documentId, updateData)
      setDocument(updated)
      setIsEditing(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setIsSaving(false)
    }
  }

  function handleCancelEdit() {
    if (document) {
      setName(document.name)
      setDescription(document.description)
      setStatus(document.status)
      setFolderId(document.folder_id || '')
    }
    setIsEditing(false)
  }

  async function handleSubmitForReview() {
    if (!draftVersion || !userId || !selectedWorkspaceId) return
    await withLoading(async () => {
      try {
        setIsSubmittingForReview(true)
        setError(null)
        await submitVersionForReview(documentId, draftVersion.id, userId, selectedWorkspaceId)
        const [updatedDoc, updatedVersions, updatedValidations] = await Promise.all([
          getDocument(documentId),
          getDocumentVersions(documentId),
          listValidations(documentId),
        ])
        setDocument(updatedDoc)
        setStatus(updatedDoc.status)
        setVersions(updatedVersions)
        setValidations(updatedValidations)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al enviar a revisión')
      } finally {
        setIsSubmittingForReview(false)
      }
    })
  }

  async function handleCancelSubmission() {
    if (!inReviewVersion || !userId || !selectedWorkspaceId) return
    setShowCancelSubmitConfirm(false)
    await withLoading(async () => {
      try {
        setIsCancelling(true)
        setError(null)
        await cancelDocumentSubmission(documentId, inReviewVersion.id, userId, selectedWorkspaceId)
        const [updatedDoc, updatedVersions, updatedValidations] = await Promise.all([
          getDocument(documentId),
          getDocumentVersions(documentId),
          listValidations(documentId),
        ])
        setDocument(updatedDoc)
        setStatus(updatedDoc.status)
        setVersions(updatedVersions)
        setValidations(updatedValidations)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cancelar envío')
      } finally {
        setIsCancelling(false)
      }
    })
  }

  async function handleApproveDocument() {
    if (!document) return
    await withLoading(async () => {
      try {
        setIsValidating(true)
        setError(null)
        await approveDocumentValidation(documentId, approveObservations || undefined)
        const [updatedValidations, updatedDoc, updatedVersions] = await Promise.all([
          listValidations(documentId),
          getDocument(documentId),
          getDocumentVersions(documentId),
        ])
        setValidations(updatedValidations)
        setDocument(updatedDoc)
        setStatus(updatedDoc.status)
        setVersions(updatedVersions)
        setApproveObservations('')
        setShowApproveConfirm(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al aprobar documento')
      } finally {
        setIsValidating(false)
      }
    })
  }

  async function handleRejectDocument() {
    if (!rejectObservations.trim()) {
      setError('Las observaciones son obligatorias para rechazar un documento')
      return
    }
    if (!document) return
    await withLoading(async () => {
      try {
        setIsValidating(true)
        setError(null)
        await rejectDocumentValidation(documentId, rejectObservations)
        const [updatedValidations, updatedDoc, updatedVersions] = await Promise.all([
          listValidations(documentId),
          getDocument(documentId),
          getDocumentVersions(documentId),
        ])
        setValidations(updatedValidations)
        setDocument(updatedDoc)
        setStatus(updatedDoc.status)
        setVersions(updatedVersions)
        setRejectObservations('')
        setShowRejectConfirm(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al rechazar documento')
      } finally {
        setIsValidating(false)
      }
    })
  }

  async function handlePatchWithAI() {
    if (!aiPatchObservations.trim()) {
      setError('Debes proporcionar observaciones para el patch')
      return
    }
    try {
      setIsPatching(true)
      setError(null)
      const lastRun = runs.length > 0 ? runs[0] : null
      await patchDocumentWithAI(documentId, aiPatchObservations, lastRun?.run_id)
      const [updatedRuns, updatedDoc, updatedVersions, updatedValidations] = await Promise.all([
        getDocumentRuns(documentId),
        getDocument(documentId),
        getDocumentVersions(documentId),
        listValidations(documentId),
      ])
      setRuns(updatedRuns)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
      setVersions(updatedVersions)
      setValidations(updatedValidations)
      setAiPatchObservations('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aplicar patch')
    } finally {
      setIsPatching(false)
    }
  }

  async function handleDelete() {
    if (!document) return
    setShowDeleteConfirm(false)
    await withLoading(async () => {
      try {
        setIsDeleting(true)
        setError(null)
        await deleteDocument(documentId)
        router.push('/workspace')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al eliminar documento')
        setIsDeleting(false)
      }
    })
  }

  async function handleGenerateNewVersion() {
    if (newVersionFiles.length === 0 && !revisionNotes.trim()) {
      setError('Agregá al menos un archivo o instrucciones de revisión')
      return
    }
    try {
      setIsGenerating(true)
      setError(null)
      const formData = new FormData()
      newVersionFiles.forEach((fileItem) => {
        formData.append(`${fileItem.type}_files`, fileItem.file)
      })
      const response = await createDocumentRun(documentId, formData)
      const [documentRuns, docVersions, docValidations, updatedDoc] = await Promise.all([
        getDocumentRuns(documentId),
        getDocumentVersions(documentId),
        listValidations(documentId),
        getDocument(documentId),
      ])
      setRuns(documentRuns)
      setVersions(docVersions)
      setValidations(docValidations)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
      setNewVersionFiles([])
      setShowNewVersionForm(false)
      setRevisionNotes('')
      if (response.artifacts?.pdf) {
        setTimeout(() => openArtifactFromRun(response.artifacts!.pdf!, 'pdf'), 2000)
      } else if (response.artifacts?.markdown) {
        setTimeout(() => openArtifactFromRun(response.artifacts!.markdown!, 'markdown'), 2000)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al generar nueva versión')
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleToggleHistory() {
    if (!showHistory) {
      try {
        const [log, vers] = await Promise.all([
          getDocumentAuditLog(documentId),
          getDocumentVersions(documentId),
        ])
        setAuditLog(log)
        setVersions(vers)
      } catch {
        setError('Error al cargar el historial')
      }
    }
    setShowHistory((s) => !s)
  }

  // ── Estados de carga y error ───────────────────────────────────────────────
  if (loading) return <DocumentDetailSkeleton />

  if (error && !document) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-12" data-module="process">
        <div className="rounded-lg border border-danger-bd bg-danger-bg p-5">
          <p className="text-sm text-danger mb-3">Error: {error}</p>
          <button
            onClick={() => router.push('/')}
            className="rounded-md bg-ink-200 px-4 py-2 text-sm hover:bg-ink-300"
          >
            Volver al inicio
          </button>
        </div>
      </div>
    )
  }

  if (!document) return null

  // Viewer: solo puede ver documentos aprobados
  if (userRoleName === 'viewer' && document.status !== 'approved') {
    return (
      <div className="mx-auto max-w-5xl px-8 py-12" data-module="process">
        <div className="rounded-lg border border-danger-bd bg-danger-bg p-5">
          <p className="text-sm text-danger mb-3">
            No tenés permisos para ver este documento. Solo podés consultar documentos aprobados.
          </p>
          <button
            onClick={() => router.push('/dashboard/view')}
            className="rounded-md bg-danger px-4 py-2 text-sm text-white hover:bg-danger"
          >
            Ver documentos aprobados
          </button>
        </div>
      </div>
    )
  }

  const openQuestions =
    typeof document.metadata?.preguntas_abiertas === 'string'
      ? document.metadata.preguntas_abiertas.trim()
      : ''

  const isPendingValidation = document.status === 'pending_validation'

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-5xl px-8 pb-16 pt-7" data-module="process">

      {/* Banner: borrador guardado */}
      {savedDraftBanner && (
        <div
          role="status"
          aria-live="polite"
          className="mb-4 flex items-center gap-3 rounded-lg bg-success-bg border border-success-bd px-5 py-3 text-sm font-medium text-success-fg"
        >
          <CheckCircle className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span>
            Borrador guardado. Usá <strong>Ver PDF</strong> para ver los cambios o{' '}
            <strong>Enviar a revisión</strong> cuando estés listo.
          </span>
        </div>
      )}

      {/* Banner: error global */}
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-danger-bd bg-danger-bg p-4 text-sm text-danger"
        >
          {error}
        </div>
      )}

      {/* ── Header con todas las acciones ────────────────────────────────── */}
      {!isEditing && (
        <DocumentDetailHeader
          document={document}
          currentVersion={previewVersion}
          actions={actions}
          onBack={() => router.back()}
          onEdit={() => setIsEditing(true)}
          onSubmitForReview={handleSubmitForReview}
          onCancelSubmission={() => setShowCancelSubmitConfirm(true)}
          onApprove={() => setShowApproveConfirm(true)}
          onReject={() => setShowRejectConfirm(true)}
          onNewVersion={() => setShowNewVersionForm((s) => !s)}
          onDelete={() => setShowDeleteConfirm(true)}
          isSubmittingForReview={isSubmittingForReview}
          isCancelling={isCancelling}
          isValidating={isValidating}
          isDeleting={isDeleting}
        />
      )}

      {/* ── Banner pendiente de validación ───────────────────────────────── */}
      {isPendingValidation && !isEditing && (
        <div className="mb-6 rounded-lg border border-warning-bd bg-warning-bg p-4">
          <p className="text-sm font-semibold text-warning mb-1">
            Este documento está pendiente de validación.
          </p>
          <p className="text-sm text-warning">
            Enviado el{' '}
            {inReviewVersion ? formatDateTime(inReviewVersion.created_at) : '—'} por{' '}
            {inReviewVersion?.created_by ? (
              <span title={inReviewVersion.created_by}>
                {submitterDisplayName ?? inReviewVersion.created_by}
              </span>
            ) : (
              '—'
            )}
            .
          </p>
        </div>
      )}

      {/* ── Formulario de edición de metadatos ───────────────────────────── */}
      {isEditing ? (
        <div className="mb-8 rounded-lg border border-ink-200 bg-white p-7 shadow-sm">
          <h2 className="text-h2 text-ink-900 mb-5">Editar documento</h2>
          <DocumentMetadataForm
            document={document}
            workspaceId={selectedWorkspaceId}
            name={name}
            onNameChange={setName}
            description={description}
            onDescriptionChange={setDescription}
            status={status}
            onStatusChange={setStatus}
            folderId={folderId}
            onFolderIdChange={setFolderId}
            audience={audience}
            onAudienceChange={setAudience}
            detailLevel={detailLevel}
            onDetailLevelChange={setDetailLevel}
            contextText={contextText}
            onContextTextChange={setContextText}
            audienceOptions={audienceOptions}
            detailLevelOptions={detailLevelOptions}
            isSaving={isSaving}
            onSave={handleSave}
            onCancel={handleCancelEdit}
          />
        </div>
      ) : (
        <>
          {/* Descripción y preguntas abiertas en modo visualización */}
          {(document.description || openQuestions) && (
            <div className="mb-6 rounded-lg border border-ink-200 bg-white p-6 shadow-sm space-y-4">
              {document.description && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-400">
                    Descripción
                  </p>
                  <p className="text-sm text-ink-700 whitespace-pre-wrap">{document.description}</p>
                </div>
              )}
              {openQuestions && (
                <div className="rounded-lg border border-warning-bd bg-warning-bg p-4">
                  <p className="mb-1 text-xs font-semibold text-warning uppercase tracking-wide">
                    Preguntas abiertas / pendientes
                  </p>
                  <p className="text-sm text-warning whitespace-pre-wrap">{openQuestions}</p>
                </div>
              )}
            </div>
          )}

          {/* ── Cuerpo del documento (PDF) ──────────────────────────────── */}
          <div className="mb-8">
            <DocumentBodyCard
              documentId={documentId}
              version={previewVersion}
              pdfUrl={pdfUrl}
            />
          </div>

          {/* ── Layout de validación: PDF (2/3) + decisión (1/3) ───────── */}
          {(actions.canApprove || actions.canReject) && (
            <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Preview del PDF para el aprobador (ya visible arriba, aquí en compacto) */}
              <div className="lg:col-span-2">
                {/* reutilizamos la misma card, altura más compacta */}
                <div className="rounded-lg border border-ink-200 overflow-hidden">
                  {pdfUrl ? (
                    <iframe
                      src={`${pdfUrl}#toolbar=0`}
                      className="h-[540px] w-full"
                      title="Vista previa para aprobación"
                    />
                  ) : (
                    <div className="flex h-64 items-center justify-center bg-ink-50">
                      <p className="text-sm text-ink-500">No hay PDF disponible.</p>
                    </div>
                  )}
                </div>
              </div>
              {/* Panel de decisión */}
              <div className="lg:col-span-1">
                <div className="sticky top-4">
                  <DocumentValidationPanel
                    actions={actions}
                    approveObservations={approveObservations}
                    onApproveObservationsChange={setApproveObservations}
                    rejectObservations={rejectObservations}
                    onRejectObservationsChange={setRejectObservations}
                    onApprove={handleApproveDocument}
                    onReject={handleRejectDocument}
                    isValidating={isValidating}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Mensaje: versión en revisión sin permisos de aprobación */}
          {isPendingValidation && Boolean(inReviewVersion) && !actions.canApprove && !actions.canReject && (
            <div className="mb-6 rounded-lg border border-indigo-border bg-indigo-tint p-4">
              <p className="text-sm text-indigo">
                El documento tiene una versión en revisión, pero no tenés permisos para aprobar o rechazar.
              </p>
            </div>
          )}

          {/* ── Panel de corrección ─────────────────────────────────────── */}
          {actions.canEditMetadata && (
            <div className="mb-8">
              <DocumentCorrectionPanel
                document={document}
                userId={userId}
                aiPatchObservations={aiPatchObservations}
                onAiPatchObservationsChange={setAiPatchObservations}
                onPatchWithAI={handlePatchWithAI}
                isPatching={isPatching}
                onVersionsRefresh={async () => {
                  const docVersions = await getDocumentVersions(documentId)
                  setVersions(docVersions)
                }}
                onDocumentRefresh={async () => {
                  const updatedDoc = await getDocument(documentId)
                  setDocument(updatedDoc)
                  setStatus(updatedDoc.status)
                }}
                onSavedDraftBanner={() => {
                  setSavedDraftBanner(true)
                  setTimeout(() => setSavedDraftBanner(false), 4000)
                }}
              />
            </div>
          )}
        </>
      )}

      {/* ── Versiones generadas ─────────────────────────────────────────── */}
      <div className="mb-8 border-t border-ink-200 pt-8">
        <DocumentRunsSection
          runs={runs}
          versions={versions}
          documentId={documentId}
          canCreateNewVersion={actions.canCreateNewVersion}
          showNewVersionForm={showNewVersionForm}
          onToggleNewVersionForm={() => {
            setShowNewVersionForm((s) => !s)
            if (showNewVersionForm) {
              setNewVersionFiles([])
              setRevisionNotes('')
            }
          }}
          revisionNotes={revisionNotes}
          onRevisionNotesChange={setRevisionNotes}
          newVersionFiles={newVersionFiles}
          onAddFile={(file, type, desc) => {
            setNewVersionFiles((prev) => [
              ...prev,
              { id: `${Date.now()}-${Math.random()}`, file, type, description: desc },
            ])
          }}
          onRemoveFile={(id) => setNewVersionFiles((prev) => prev.filter((f) => f.id !== id))}
          isNewVersionModalOpen={isNewVersionModalOpen}
          onOpenModal={() => setIsNewVersionModalOpen(true)}
          onCloseModal={() => setIsNewVersionModalOpen(false)}
          onGenerateNewVersion={handleGenerateNewVersion}
          isGenerating={isGenerating}
          onOpenVersionPreviewPdf={openVersionPreviewPdf}
          onOpenArtifactFromRun={openArtifactFromRun}
        />
      </div>

      {/* ── Historial y trazabilidad ────────────────────────────────────── */}
      <div className="border-t border-ink-200 pt-8">
        <DocumentHistorySection
          versions={versions}
          auditLog={auditLog}
          validations={validations}
          userDisplayNames={userDisplayNames}
          showHistory={showHistory}
          onToggle={handleToggleHistory}
        />
      </div>

      {/* ── Modal PDF ────────────────────────────────────────────────────── */}
      <ModalComponent />

      {/* ── Modales de confirmación ─────────────────────────────────────── */}

      {/* Cancelar envío */}
      {showCancelSubmitConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-label="Confirmar cancelación de envío"
        >
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-modal mx-4">
            <p className="text-sm text-ink-900 mb-5">
              ¿Querés cancelar el envío y volver a borrador?
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCancelSubmitConfirm(false)}
                className="rounded-md border border-ink-300 px-4 py-2 text-sm hover:bg-ink-50"
              >
                No
              </button>
              <button
                type="button"
                onClick={handleCancelSubmission}
                disabled={isCancelling}
                className="rounded-md bg-warning px-4 py-2 text-sm text-white hover:bg-warning disabled:opacity-50"
              >
                {isCancelling ? 'Cancelando…' : 'Sí, volver a borrador'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Aprobar */}
      {showApproveConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-label="Confirmar aprobación"
        >
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-modal mx-4">
            <h3 className="text-h3 text-ink-900 mb-4">Aprobar documento</h3>
            <label htmlFor="modal-approve-obs" className="mb-1.5 block text-sm font-medium text-ink-700">
              Observaciones (opcional)
            </label>
            <textarea
              id="modal-approve-obs"
              value={approveObservations}
              onChange={(e) => setApproveObservations(e.target.value)}
              rows={3}
              className="mb-4 w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400"
              placeholder="Observaciones adicionales…"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowApproveConfirm(false)}
                className="rounded-md border border-ink-300 px-4 py-2 text-sm hover:bg-ink-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleApproveDocument}
                disabled={isValidating}
                className="rounded-md bg-create px-4 py-2 text-sm text-white hover:bg-create-hover disabled:opacity-50"
              >
                {isValidating ? 'Aprobando…' : 'Confirmar aprobación'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rechazar */}
      {showRejectConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-label="Rechazar documento"
        >
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-modal mx-4">
            <h3 className="text-h3 text-ink-900 mb-4">Rechazar documento</h3>
            <label htmlFor="modal-reject-obs" className="mb-1.5 block text-sm font-medium text-ink-700">
              Motivo del rechazo <span className="text-danger" aria-hidden="true">*</span>
            </label>
            <textarea
              id="modal-reject-obs"
              value={rejectObservations}
              onChange={(e) => setRejectObservations(e.target.value)}
              rows={4}
              className="mb-4 w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400"
              placeholder="Describe los motivos del rechazo y las correcciones necesarias…"
              required
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowRejectConfirm(false)}
                className="rounded-md border border-ink-300 px-4 py-2 text-sm hover:bg-ink-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleRejectDocument}
                disabled={isValidating || !rejectObservations.trim()}
                className="rounded-md bg-danger px-4 py-2 text-sm text-white hover:bg-danger disabled:opacity-50"
              >
                {isValidating ? 'Rechazando…' : 'Confirmar rechazo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Eliminar */}
      {showDeleteConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
        >
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-modal mx-4">
            <h3 id="delete-dialog-title" className="text-h3 text-ink-900 mb-2">
              Eliminar documento
            </h3>
            <p className="text-sm text-ink-700 mb-5">
              ¿Estás seguro de que querés eliminar el documento &quot;{document.name}&quot;? Esta
              acción no se puede deshacer y eliminará el documento, todas sus versiones y todos los
              archivos generados.
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-md border border-ink-300 px-4 py-2 text-sm hover:bg-ink-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
                className="rounded-md bg-danger px-4 py-2 text-sm text-white hover:bg-danger disabled:opacity-50"
              >
                {isDeleting ? 'Eliminando…' : 'Eliminar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
