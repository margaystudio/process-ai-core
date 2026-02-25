'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  getDocument,
  updateDocument,
  deleteDocument,
  getCatalogOptions,
  getDocumentRuns,
  createDocumentRun,
  getArtifactUrl,
  CatalogOption,
  Document,
  DocumentUpdateRequest,
  createValidation,
  approveValidation,
  rejectValidation,
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
import FolderTree from '@/components/processes/FolderTree'
import FileUploadModal, { FileType } from '@/components/processes/FileUploadModal'
import FileList from '@/components/processes/FileList'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { FileItemData } from '@/components/processes/FileItem'
import { formatDateTime } from '@/utils/dateFormat'
import { useCanApproveDocuments, useCanRejectDocuments, useHasPermission } from '@/hooks/useHasPermission'
import { useUserId } from '@/hooks/useUserId'
import ManualEditPanel from '@/components/documents/ManualEditPanel'
import {
  getDocumentRole,
  canApprove,
  canReject,
  canCancelSubmission,
  canEditMetadata,
  canCreateNewVersion,
  canSubmitForReview,
  type DocumentStatus,
} from '@/lib/documentPermissions'

/** Mapea acciones del audit log del backend a etiquetas en español para la UI. */
function actionToLabel(action: string): string {
  const map: Record<string, string> = {
    updated: 'Actualizado',
    validated: 'Validado',
    approved: 'Aprobado',
    rejected: 'Rechazado',
    'version.draft_reused': 'Borrador reutilizado',
    'version.draft_created': 'Borrador creado',
    'version.draft_updated': 'Borrador actualizado',
    'version.draft_updated_by_ai_patch': 'Borrador actualizado (patch IA)',
    'version.draft_created_by_ai_patch': 'Borrador creado (patch IA)',
    'version.submitted': 'Enviado a revisión',
    'version.submission_cancelled': 'Envío cancelado',
    'version.approved': 'Versión aprobada',
    'version.rejected': 'Versión rechazada',
    'manual_edit_saved': 'Edición manual guardada',
  }
  return map[action] ?? action
}

export default function DocumentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params.id as string
  const { selectedWorkspaceId } = useWorkspace()
  const [showCancelSubmitConfirm, setShowCancelSubmitConfirm] = useState(false)
  const [showApproveConfirm, setShowApproveConfirm] = useState(false)
  const [showRejectConfirm, setShowRejectConfirm] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isSubmittingForReview, setIsSubmittingForReview] = useState(false)
  const { withLoading } = useLoading()
  const userId = useUserId()
  const { hasPermission: hasApprovePermission, loading: loadingApprove } = useCanApproveDocuments()
  const { hasPermission: hasRejectPermission, loading: loadingReject } = useCanRejectDocuments()
  const { hasPermission: hasDocumentEditPermission } = useHasPermission('documents.edit')
  
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [showNewVersionForm, setShowNewVersionForm] = useState(false)
  const [newVersionFiles, setNewVersionFiles] = useState<FileItemData[]>([])
  const [isNewVersionModalOpen, setIsNewVersionModalOpen] = useState(false)
  const [revisionNotes, setRevisionNotes] = useState('')
  const [runs, setRuns] = useState<Array<{
    run_id: string;
    created_at: string;
    artifacts: {
      json?: string;
      md?: string;
      pdf?: string;
    };
  }>>([])
  
  // Validation state
  const [validations, setValidations] = useState<Validation[]>([])
  const [isValidating, setIsValidating] = useState(false)
  const [rejectObservations, setRejectObservations] = useState('')
  const [approveObservations, setApproveObservations] = useState('')
  
  // Correction options
  const [showCorrectionOptions, setShowCorrectionOptions] = useState(false)
  const [correctionType, setCorrectionType] = useState<'manual' | 'ai_patch' | null>(null)
  const [savedDraftBanner, setSavedDraftBanner] = useState(false)
  const [aiPatchObservations, setAiPatchObservations] = useState('')
  const [isPatching, setIsPatching] = useState(false)
  
  // History and audit log
  const [showHistory, setShowHistory] = useState(false)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [submitterDisplayName, setSubmitterDisplayName] = useState<string | null>(null)
  const [userDisplayNames, setUserDisplayNames] = useState<Record<string, string>>({})
  
  // Hook para manejar visualización de artifacts
  const { openArtifactFromRun, openVersionPreviewPdf, ModalComponent } = usePdfViewer()
  
  // Delete state
  const [isDeleting, setIsDeleting] = useState(false)
  
  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState('')
  const [folderId, setFolderId] = useState('')
  
  // Process-specific fields
  const [audience, setAudience] = useState('')
  const [detailLevel, setDetailLevel] = useState('')
  const [contextText, setContextText] = useState('')
  
  // Catalog options
  const [audienceOptions, setAudienceOptions] = useState<CatalogOption[]>([])
  const [detailLevelOptions, setDetailLevelOptions] = useState<CatalogOption[]>([])
  
  useEffect(() => {
    async function loadDocument() {
      try {
        setLoading(true)
        setError(null)
        
        // Cargar todo en paralelo para mejor rendimiento y asegurar que las versiones se carguen
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
        
        // Load catalog options and process-specific fields
        if (doc.document_type === 'process') {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const [audienceOpts, detailOpts, processDocResponse] = await Promise.all([
            getCatalogOptions('audience').catch(() => []),
            getCatalogOptions('detail_level').catch(() => []),
            fetch(`${apiUrl}/api/v1/documents/${documentId}/process`)
              .then(r => r.ok ? r.json() : null)
              .catch(() => null),
          ])
          setAudienceOptions(audienceOpts)
          setDetailLevelOptions(detailOpts)
          
          // Set process-specific fields (incluso si están vacíos)
          const processDoc = (processDocResponse as { audience?: string; detail_level?: string; context_text?: string }) || {}
          setAudience(processDoc?.audience || '')
          setDetailLevel(processDoc?.detail_level || '')
          setContextText(processDoc?.context_text || '')
        }
        
        // Load history if needed
        if (showHistory) {
          try {
            const log = await getDocumentAuditLog(documentId)
            setAuditLog(log)
          } catch (err) {
            console.error('Error cargando historial:', err)
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        setLoading(false)
      }
    }
    
    if (documentId) {
      loadDocument()
    }
  }, [documentId, showHistory])

  // Resolver nombre del usuario que envió a revisión (para mostrar en banner e historial)
  const inReviewVersionForSubmitter = versions.find(v => v.version_status === 'IN_REVIEW')
  useEffect(() => {
    const createdBy = inReviewVersionForSubmitter?.created_by
    if (!createdBy) {
      setSubmitterDisplayName(null)
      return
    }
    let cancelled = false
    getUser(createdBy)
      .then(u => {
        if (!cancelled) {
          setSubmitterDisplayName(u.name?.trim() || u.email || u.id)
        }
      })
      .catch(() => {
        if (!cancelled) setSubmitterDisplayName(null)
      })
    return () => { cancelled = true }
  }, [inReviewVersionForSubmitter?.created_by])

  // Resolver nombres de usuarios del historial (quien envió y quien aprobó/rechazó)
  const validationUserIdsKey = Array.from(new Set(
    validations.flatMap(validation => {
      const v = versions.find(ver => ver.validation_id === validation.id)
      const ids: string[] = []
      if (v?.created_by) ids.push(v.created_by)
      if (validation.validator_user_id) ids.push(validation.validator_user_id)
      return ids
    })
  )).sort().join(',')
  useEffect(() => {
    const userIds = validationUserIdsKey ? validationUserIdsKey.split(',') : []
    if (userIds.length === 0) return
    let cancelled = false
    const next: Record<string, string> = {}
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
      results.forEach(({ id, name }) => { next[id] = name })
      setUserDisplayNames(prev => ({ ...prev, ...next }))
    })
    return () => { cancelled = true }
  }, [validationUserIdsKey])
  
  const handleSave = async () => {
    if (!document) return
    
    try {
      setIsSaving(true)
      setError(null)
      
      const updateData: DocumentUpdateRequest = {
        name,
        description,
        status,
        folder_id: folderId || undefined,
      }
      
      if (document.document_type === 'process') {
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
  
  const handleCancel = () => {
    if (document) {
      setName(document.name)
      setDescription(document.description)
      setStatus(document.status)
      setFolderId(document.folder_id || '')
    }
    setIsEditing(false)
  }
  
  const handleAddNewVersionFile = (file: File, type: FileType, description: string) => {
    const newFile: FileItemData = {
      id: `${Date.now()}-${Math.random()}`,
      file,
      type,
      description,
    }
    setNewVersionFiles([...newVersionFiles, newFile])
  }
  
  const handleRemoveNewVersionFile = (id: string) => {
    setNewVersionFiles(newVersionFiles.filter(f => f.id !== id))
  }
  
  // Validation handlers (one-shot validation)
  const handleApproveDocument = async () => {
    if (!document) return
    
    await withLoading(async () => {
      try {
        setIsValidating(true)
        setError(null)
        
        await approveDocumentValidation(documentId, approveObservations || undefined)
        
        // Reload validations, document, and versions
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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al aprobar documento')
      } finally {
        setIsValidating(false)
      }
    })
  }
  
  const handleRejectDocument = async () => {
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
        
        // Reload validations, document, and versions
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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al rechazar documento')
      } finally {
        setIsValidating(false)
      }
    })
  }

  const handleSubmitForReview = async () => {
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

  const handleCancelSubmission = async () => {
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
  
  // Correction handlers
  const handlePatchWithAI = async () => {
    if (!aiPatchObservations.trim()) {
      setError('Debes proporcionar observaciones para el patch')
      return
    }
    
    try {
      setIsPatching(true)
      setError(null)
      
      const lastRun = runs.length > 0 ? runs[0] : null
      await patchDocumentWithAI(documentId, aiPatchObservations, lastRun?.run_id)
      
      // Reload runs, document, versions, and validations to reflect the new IN_REVIEW version
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
      setShowCorrectionOptions(false)
      setCorrectionType(null)
      setAiPatchObservations('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aplicar patch')
    } finally {
      setIsPatching(false)
    }
  }
  
  const handleDelete = async () => {
    if (!document) return
    
    if (!confirm(`¿Estás seguro de que deseas eliminar el documento "${document.name}"?\n\nEsta acción no se puede deshacer y eliminará:\n- El documento\n- Todas sus versiones\n- Todos los archivos generados`)) {
      return
    }
    
    await withLoading(async () => {
      try {
        setIsDeleting(true)
        setError(null)
        
        await deleteDocument(documentId)
        
        // Redirigir a la página principal después de eliminar
        router.push('/workspace')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al eliminar documento')
        setIsDeleting(false)
      }
    })
  }

  const handleGenerateNewVersion = async () => {
    if (newVersionFiles.length === 0) {
      setError('Debes agregar al menos un archivo para generar una nueva versión')
      return
    }
    
    try {
      setIsGenerating(true)
      setError(null)
      
      const formData = new FormData()
      
      // Agregar archivos según su tipo
      newVersionFiles.forEach((fileItem) => {
        const fieldName = `${fileItem.type}_files`
        formData.append(fieldName, fileItem.file)
      })
      
      const response = await createDocumentRun(documentId, formData)
      
      // Recargar runs, versiones, validaciones y documento para reflejar los cambios
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
      
      // Limpiar formulario
      setNewVersionFiles([])
      setShowNewVersionForm(false)
      setRevisionNotes('')
      
      // Abrir automáticamente el PDF del run generado para visualización (solo lectura)
      if (response.run_id && response.artifacts?.pdf) {
        // Delay más largo para asegurar que el archivo esté disponible y la versión se haya creado
        setTimeout(() => {
          openArtifactFromRun(response.run_id, 'process.pdf', 'pdf')
        }, 2000)
      } else if (response.run_id && response.artifacts?.markdown) {
        // Si no hay PDF, abrir el markdown
        setTimeout(() => {
          openArtifactFromRun(response.run_id, 'process.md', 'markdown')
        }, 2000)
      }
      
      // Mostrar mensaje de éxito
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al generar nueva versión')
    } finally {
      setIsGenerating(false)
    }
  }
  
  // Calcular si mostrar panel de validación (ANTES de los returns condicionales - regla de hooks)
  const hasInReviewVersion = document ? versions.some(v => v.version_status === 'IN_REVIEW') : false
  const isPendingValidation = document?.status === 'pending_validation' || false
  
  // Obtener versión IN_REVIEW y DRAFT para validar segregación y rol
  const inReviewVersion = versions.find(v => v.version_status === 'IN_REVIEW')
  const draftVersion = versions.find(v => v.version_status === 'DRAFT')
  // Calcular canValidate: el usuario puede validar si NO creó la versión (o si created_by es null)
  const canValidate = inReviewVersion ? (inReviewVersion.created_by === null || inReviewVersion.created_by !== userId) : true
  
  // Rol: "creator" si creó la versión IN_REVIEW o la versión DRAFT (así tras "cancelar envío" sigue pudiendo editar)
  const isCreatorOfInReview = Boolean(inReviewVersion && userId && inReviewVersion.created_by === userId)
  const isCreatorOfDraft = Boolean(draftVersion && userId && draftVersion.created_by === userId)
  const isCreator = isCreatorOfInReview || isCreatorOfDraft
  
  // Rol y permisos centralizados (helpers)
  const docStatus = (document?.status || 'draft') as DocumentStatus
  const documentRole = getDocumentRole(isCreator, hasApprovePermission ?? false, hasRejectPermission ?? false)
  const allowApprove = canApprove(documentRole, docStatus)
  const allowReject = canReject(documentRole, docStatus)
  const allowCancelSubmission = canCancelSubmission(documentRole, docStatus)
  const allowEditMetadata = canEditMetadata(documentRole, docStatus)
  const allowNewVersion = canCreateNewVersion(docStatus)
  const allowSubmitForReview =
    canSubmitForReview(documentRole, docStatus) ||
    (docStatus === 'draft' && Boolean(draftVersion) && hasDocumentEditPermission)
  
  // Mostrar panel si hay versión IN_REVIEW, el usuario tiene permisos Y puede validar (no es el creador)
  const showValidationPanel = isPendingValidation && hasInReviewVersion && (hasApprovePermission || hasRejectPermission) && canValidate
  // Mostrar sección si hay panel, validaciones previas, o estado rechazado, o si hay versión IN_REVIEW (para mostrar mensaje)
  const shouldShowValidationSection = showValidationPanel || (validations.length > 0) || (document?.status === 'rejected') || (isPendingValidation && hasInReviewVersion)
  
  // Debug logs (solo en desarrollo) - DEBE estar antes de los returns condicionales
  useEffect(() => {
    if (process.env.NODE_ENV === 'development' && document) {
      console.log('[DEBUG Validación]', {
        documentStatus: document.status,
        isPendingValidation,
        versions: versions.map(v => ({ id: v.id, status: v.version_status })),
        hasInReviewVersion,
        hasApprovePermission,
        hasRejectPermission,
        loadingApprove,
        loadingReject,
        showValidationPanel,
        shouldShowValidationSection,
        validationsCount: validations.length,
      })
    }
  }, [document, versions, hasInReviewVersion, isPendingValidation, hasApprovePermission, hasRejectPermission, loadingApprove, loadingReject, showValidationPanel, shouldShowValidationSection, validations.length])
  
  if (loading) {
    return (
      <div className="p-8">
        <div className="max-w-4xl mx-auto">
          <div className="animate-pulse">Cargando documento...</div>
        </div>
      </div>
    )
  }
  
  if (error && !document) {
    return (
      <div className="p-8">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-700">Error: {error}</p>
            <button
              onClick={() => router.push('/')}
              className="mt-4 px-4 py-2 bg-gray-200 rounded-md hover:bg-gray-300"
            >
              Volver al inicio
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
      <div className="max-w-6xl mx-auto">

        {/* Banner de borrador guardado */}
        {savedDraftBanner && (
          <div className="mb-4 flex items-center gap-3 px-5 py-3 bg-green-600 text-white rounded-lg shadow-lg text-sm font-medium animate-pulse">
            <span className="text-lg">✅</span>
            <span>Borrador guardado. Ya podés usar <strong>Ver PDF</strong> para ver los cambios o <strong>Enviar a revisión</strong>.</span>
          </div>
        )}

        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="text-sm text-gray-600 hover:text-gray-900 mb-4"
          >
            ← Volver
          </button>
          <div className="flex items-center justify-between">
            <h1 className="text-3xl font-bold text-gray-900">
              {isEditing ? 'Editar Documento' : document.name}
            </h1>
            {!isEditing && (
            <div className="flex items-center gap-2">
              {allowEditMetadata && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Editar
                </button>
              )}
              {allowSubmitForReview && draftVersion && (
                <button
                  onClick={handleSubmitForReview}
                  disabled={isSubmittingForReview}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmittingForReview ? 'Enviando...' : 'Enviar a revisión'}
                </button>
              )}
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isDeleting ? 'Eliminando...' : 'Eliminar'}
              </button>
            </div>
            )}
          </div>
        </div>
        
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
            {error}
          </div>
        )}

        {/* Banner contextual: Pendiente de validación */}
        {isPendingValidation && document && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-amber-900 font-medium mb-1">Este documento está pendiente de validación.</p>
            <p className="text-amber-800 text-sm mb-4">
              Enviado el {inReviewVersion ? formatDateTime(inReviewVersion.created_at) : '—'} por{' '}
              {inReviewVersion?.created_by ? (
                <span title={inReviewVersion.created_by}>
                  {submitterDisplayName ?? inReviewVersion.created_by}
                </span>
              ) : (
                '—'
              )}
              .
            </p>
            {allowCancelSubmission && inReviewVersion && (
              <button
                type="button"
                onClick={() => setShowCancelSubmitConfirm(true)}
                disabled={isCancelling}
                className="px-4 py-2 border border-amber-600 text-amber-800 bg-white rounded-md hover:bg-amber-50 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
              >
                {isCancelling ? 'Cancelando...' : 'Cancelar envío y volver a borrador'}
              </button>
            )}
          </div>
        )}
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Columna izquierda: Árbol de carpetas (solo en modo edición) */}
          {isEditing && selectedWorkspaceId && (
            <div className="lg:col-span-1">
              <div className="mb-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Carpeta
                </label>
              </div>
              <FolderTree
                workspaceId={selectedWorkspaceId}
                selectedFolderId={folderId}
                onSelectFolder={(id) => setFolderId(id || '')}
                showSelectable={true}
                showCrud={false}
              />
            </div>
          )}
          
          {/* Columna derecha: Formulario */}
          <div className={isEditing ? 'lg:col-span-2' : 'lg:col-span-3'}>
            <div className="bg-white rounded-lg shadow-sm p-8">
              {isEditing ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    handleSave()
                  }}
                  className="space-y-6"
                >
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Nombre *
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Descripción
                    </label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={4}
                      className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Estado
                    </label>
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="draft">Borrador</option>
                      <option value="pending_validation">Pendiente de Validación</option>
                      <option value="approved">Aprobado</option>
                      <option value="rejected">Rechazado</option>
                      <option value="archived">Archivado</option>
                    </select>
                  </div>
                  
                  {document.document_type === 'process' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Audiencia
                        </label>
                        <select
                          value={audience}
                          onChange={(e) => setAudience(e.target.value)}
                          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="">Seleccionar...</option>
                          {audienceOptions.map(opt => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Nivel de Detalle
                        </label>
                        <select
                          value={detailLevel}
                          onChange={(e) => setDetailLevel(e.target.value)}
                          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="">Seleccionar...</option>
                          {detailLevelOptions.map(opt => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Contexto
                        </label>
                        <textarea
                          value={contextText}
                          onChange={(e) => setContextText(e.target.value)}
                          rows={4}
                          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          placeholder="Contexto adicional del proceso..."
                        />
                      </div>
                    </>
                  )}
                  
                  <div className="pt-6 border-t flex gap-4">
                    <button
                      type="submit"
                      disabled={isSaving || !name.trim()}
                      className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                    >
                      {isSaving ? 'Guardando...' : 'Guardar'}
                    </button>
                    <button
                      type="button"
                      onClick={handleCancel}
                      className="px-6 py-3 border border-gray-300 rounded-md hover:bg-gray-50 font-medium"
                    >
                      Cancelar
                    </button>
                  </div>
                </form>
              ) : (
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Nombre
                    </label>
                    <p className="text-gray-900">{document.name}</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Descripción
                    </label>
                    <p className="text-gray-900 whitespace-pre-wrap">
                      {document.description || '(Sin descripción)'}
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Estado
                    </label>
                    <span className={`inline-block px-3 py-1 rounded-full text-sm ${
                      document.status === 'approved' ? 'bg-green-100 text-green-800' :
                      document.status === 'pending_validation' ? 'bg-yellow-100 text-yellow-800' :
                      document.status === 'rejected' ? 'bg-red-100 text-red-800' :
                      document.status === 'archived' ? 'bg-gray-100 text-gray-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {document.status === 'approved' ? 'Aprobado' :
                       document.status === 'pending_validation' ? 'Pendiente de Validación' :
                       document.status === 'rejected' ? 'Rechazado' :
                       document.status === 'archived' ? 'Archivado' :
                       'Borrador'}
                    </span>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Tipo
                    </label>
                    <p className="text-gray-900 capitalize">{document.document_type}</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Creado
                    </label>
                    <p className="text-gray-900">
                      {formatDateTime(document.created_at)}
                    </p>
                  </div>
                </div>
              )}
              
              {/* Sección de Validación - Layout con PDF y botones lado a lado */}
              {shouldShowValidationSection && (
                <div className="mt-8 pt-8 border-t">
                  <h2 className="text-xl font-semibold text-gray-900 mb-4">Validación</h2>
                  
                  {/* Layout de dos columnas cuando hay versión IN_REVIEW y permisos */}
                  {showValidationPanel && hasInReviewVersion ? (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                      {/* Columna izquierda: Preview del PDF */}
                      <div className="lg:col-span-2">
                        <div className="bg-white rounded-lg border border-gray-200 p-6">
                          <h3 className="text-lg font-semibold text-gray-900 mb-4">Vista Previa del Documento</h3>
                          
                          {(() => {
                            // PDF desde la versión en revisión (fuente de verdad: content_html o content_markdown)
                            const inReviewVersion = versions.find(v => v.version_status === 'IN_REVIEW')
                            if (inReviewVersion) {
                              const pdfUrl = getVersionPreviewPdfUrl(documentId, inReviewVersion.id)
                              return (
                                <div className="border border-gray-200 rounded-lg overflow-hidden">
                                  <iframe
                                    src={`${pdfUrl}#toolbar=0`}
                                    className="w-full h-[600px]"
                                    title="Preview del documento"
                                  />
                                </div>
                              )
                            }
                            return (
                              <div className="h-96 flex items-center justify-center bg-gray-50 rounded">
                                <p className="text-gray-500">No hay PDF disponible para este documento</p>
                              </div>
                            )
                          })()}
                        </div>
                      </div>

                      {/* Columna derecha: Formulario de validación */}
                      <div className="lg:col-span-1">
                        <div className="bg-white rounded-lg border border-gray-200 p-6 sticky top-4">
                          <h3 className="text-lg font-semibold text-gray-900 mb-4">Decisión de Validación</h3>
                          
                          {/* Aprobar */}
                          <div className="mb-6">
                            <div className="mb-3">
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                Observaciones (opcional)
                              </label>
                              <textarea
                                value={approveObservations}
                                onChange={(e) => setApproveObservations(e.target.value)}
                                rows={3}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-green-500"
                                placeholder="Observaciones adicionales para la aprobación..."
                              />
                            </div>
                            {hasApprovePermission && (
                              <button
                                onClick={handleApproveDocument}
                                disabled={isValidating}
                                className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                              >
                                {isValidating ? 'Aprobando...' : '✓ Aprobar Documento'}
                              </button>
                            )}
                          </div>
                          
                          {/* Rechazar */}
                          <div className="pt-6 border-t border-gray-300">
                            <div className="mb-3">
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                Motivo del rechazo <span className="text-red-600">*</span>
                              </label>
                              <textarea
                                value={rejectObservations}
                                onChange={(e) => setRejectObservations(e.target.value)}
                                rows={5}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-red-500 focus:border-red-500"
                                placeholder="Describe las razones del rechazo y las correcciones necesarias..."
                                required
                              />
                            </div>
                            {hasRejectPermission && canValidate && (
                              <button
                                onClick={handleRejectDocument}
                                disabled={isValidating || !rejectObservations.trim()}
                                className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                              >
                                {isValidating ? 'Rechazando...' : '✗ Rechazar y Devolver'}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : showValidationPanel ? (
                    // Si hay panel pero no versión IN_REVIEW, mostrar solo el formulario
                    <div className="mb-6 p-6 bg-gray-50 rounded-lg border border-gray-200">
                      <h3 className="text-lg font-medium text-gray-900 mb-4">Decisión de Validación</h3>
                      
                      {/* Aprobar */}
                      <div className="mb-6">
                        <div className="mb-3">
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Observaciones (opcional)
                          </label>
                          <textarea
                            value={approveObservations}
                            onChange={(e) => setApproveObservations(e.target.value)}
                            rows={2}
                            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-green-500"
                            placeholder="Observaciones adicionales para la aprobación..."
                          />
                        </div>
                        {hasApprovePermission && canValidate && (
                          <button
                            onClick={handleApproveDocument}
                            disabled={isValidating}
                            className="px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                          >
                            {isValidating ? 'Aprobando...' : '✓ Aprobar Documento'}
                          </button>
                        )}
                      </div>
                      
                      {/* Rechazar */}
                      <div className="pt-6 border-t border-gray-300">
                        <div className="mb-3">
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Motivo del rechazo <span className="text-red-600">*</span>
                          </label>
                          <textarea
                            value={rejectObservations}
                            onChange={(e) => setRejectObservations(e.target.value)}
                            rows={4}
                            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-red-500 focus:border-red-500"
                            placeholder="Describe las razones del rechazo y las correcciones necesarias..."
                            required
                          />
                        </div>
                        {hasRejectPermission && canValidate && (
                          <button
                            onClick={handleRejectDocument}
                            disabled={isValidating || !rejectObservations.trim()}
                            className="px-6 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                          >
                            {isValidating ? 'Rechazando...' : '✗ Rechazar y Devolver'}
                          </button>
                        )}
                      </div>
                    </div>
                  ) : null}
                    
                    {/* Mensaje si hay versión IN_REVIEW pero el usuario no tiene permisos */}
                    {isPendingValidation && hasInReviewVersion && !hasApprovePermission && !hasRejectPermission && (
                      <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <p className="text-sm text-blue-800">
                          El documento tiene una versión en revisión, pero no tienes permisos para aprobar o rechazar documentos.
                        </p>
                      </div>
                    )}
                    
                    {/* Mensaje si no hay versión IN_REVIEW */}
                    {isPendingValidation && !hasInReviewVersion && (
                      <div className="mb-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                        <p className="text-sm text-yellow-800">
                          No hay versión en revisión. El documento debe tener una versión enviada a revisión para poder validarla.
                        </p>
                      </div>
                    )}
                    
                    {/* Historial de validaciones */}
                    {validations.length > 0 && (
                      <div className="space-y-4">
                        <h3 className="text-md font-medium text-gray-900">Historial de Validaciones</h3>
                        {[...validations]
                          .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
                          .map((validation, index) => {
                            const versionForValidation = versions.find(v => v.validation_id === validation.id)
                            const submittedBy = versionForValidation?.created_by ?? null
                            const validatorId = validation.validator_user_id ?? null
                            const isFirstSubmission = index === 0
                            const submitLabel = isFirstSubmission ? 'Enviado' : 'Reenviado para validación'
                            const isPending = validation.status !== 'approved' && validation.status !== 'rejected'
                            const eventLabel = isPending
                              ? submitLabel
                              : validation.status === 'approved'
                                ? 'Aprobada'
                                : 'Rechazada'
                            const eventActorId = isPending ? (submittedBy ?? validatorId) : validatorId ?? submittedBy
                            return (
                              <div key={validation.id} className="border border-gray-200 rounded-lg p-4">
                                <div className="flex items-center gap-2 mb-2 flex-wrap">
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                                    validation.status === 'approved' ? 'bg-green-100 text-green-800' :
                                    validation.status === 'rejected' ? 'bg-red-100 text-red-800' :
                                    'bg-yellow-100 text-yellow-800'
                                  }`}>
                                    {validation.status === 'approved' ? 'Aprobada' :
                                     validation.status === 'rejected' ? 'Rechazada' :
                                     'Pendiente'}
                                  </span>
                                  <span className="text-xs text-gray-600">
                                    {eventLabel} el {formatDateTime(validation.created_at)}
                                    {eventActorId && (
                                      <> por <span title={eventActorId}>{userDisplayNames[eventActorId] ?? eventActorId}</span></>
                                    )}
                                  </span>
                                </div>
                                {validation.observations && (
                                  <p className="text-sm text-gray-700 whitespace-pre-wrap mt-2">
                                    {validation.observations}
                                  </p>
                                )}
                              </div>
                            )
                          })}
                      </div>
                    )}
                </div>
              )}
              
              {/* Opciones de corrección: en rechazado o en borrador (creador puede modificar contenido) */}
              {(document.status === 'rejected' || (document.status === 'draft' && allowEditMetadata)) && (
                <div className="mt-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-gray-900">
                      {document.status === 'draft' ? 'Modificar contenido del documento' : 'Corregir Documento'}
                    </h3>
                    <button
                      onClick={() => setShowCorrectionOptions(!showCorrectionOptions)}
                      className="px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 text-sm font-medium"
                    >
                      {showCorrectionOptions ? 'Ocultar' : 'Mostrar Opciones'}
                    </button>
                  </div>
                  
                  {showCorrectionOptions && (
                    <div className="space-y-4">
                      <div className="flex gap-3">
                        <button
                          onClick={() => setCorrectionType('ai_patch')}
                          className={`px-4 py-2 rounded-md text-sm font-medium ${
                            correctionType === 'ai_patch'
                              ? 'bg-blue-600 text-white'
                              : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                          }`}
                        >
                          Patch por IA
                        </button>
                        <button
                          onClick={() => setCorrectionType('manual')}
                          className={`px-4 py-2 rounded-md text-sm font-medium ${
                            correctionType === 'manual'
                              ? 'bg-blue-600 text-white'
                              : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                          }`}
                        >
                          Edición Manual
                        </button>
                      </div>
                      
                      {correctionType === 'ai_patch' && (
                        <div className="p-4 bg-white rounded-lg border border-gray-200">
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Observaciones para el LLM
                          </label>
                          <textarea
                            value={aiPatchObservations}
                            onChange={(e) => setAiPatchObservations(e.target.value)}
                            rows={4}
                            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-3"
                            placeholder="Describe las correcciones que debe aplicar la IA..."
                          />
                          <div className="flex gap-3">
                            <button
                              onClick={handlePatchWithAI}
                              disabled={isPatching || !aiPatchObservations.trim()}
                              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                            >
                              {isPatching ? 'Aplicando Patch...' : 'Aplicar Patch por IA'}
                            </button>
                            <button
                              onClick={() => {
                                setCorrectionType(null)
                                setAiPatchObservations('')
                              }}
                              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      )}
                      
                      {correctionType === 'manual' && document && (
                        <ManualEditPanel
                          documentId={document.id}
                          workspaceId={document.workspace_id}
                          userId={userId}
                          onCancel={() => setCorrectionType(null)}
                          onSaved={async () => {
                            // Refrescar versiones para que content_type='manual_edit' quede actualizado
                            const docVersions = await getDocumentVersions(documentId)
                            setVersions(docVersions)
                            // Colapsar editor y mostrar banner de éxito
                            setCorrectionType(null)
                            setShowCorrectionOptions(false)
                            setSavedDraftBanner(true)
                            setTimeout(() => setSavedDraftBanner(false), 4000)
                          }}
                          onSubmitForReview={async () => {
                            setCorrectionType(null)
                            setShowCorrectionOptions(false)
                            const [docVersions, updatedDoc] = await Promise.all([
                              getDocumentVersions(documentId),
                              getDocument(documentId),
                            ])
                            setVersions(docVersions)
                            setDocument(updatedDoc)
                            setStatus(updatedDoc.status)
                          }}
                        />
                      )}
                    </div>
                  )}
                </div>
              )}
              
              {/* Sección de Generar Nueva Versión */}
              <div className="mt-8 pt-8 border-t">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-gray-900">Versiones Generadas</h2>
                  <button
                    onClick={() => allowNewVersion && setShowNewVersionForm(!showNewVersionForm)}
                    disabled={!allowNewVersion}
                    title={!allowNewVersion ? 'Solo disponible cuando el documento está aprobado o rechazado' : undefined}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                  >
                    {showNewVersionForm ? 'Cancelar' : '+ Nueva Versión'}
                  </button>
                </div>
                
                {showNewVersionForm && (
                  <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">Generar Nueva Versión</h3>
                    <p className="text-sm text-gray-600 mb-4">
                      Sube nuevos archivos o agrega instrucciones de revisión para generar una versión corregida del documento.
                      Si no subes archivos nuevos, se reutilizarán los del último run.
                    </p>
                    
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Instrucciones de Revisión
                      </label>
                      <textarea
                        value={revisionNotes}
                        onChange={(e) => setRevisionNotes(e.target.value)}
                        rows={4}
                        className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Ej: Corregir errores gramaticales, mejorar la descripción del paso 3, agregar más detalle en la sección de indicadores..."
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Describe las correcciones o mejoras que quieres aplicar al documento.
                      </p>
                    </div>
                    
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-sm font-medium text-gray-700">
                          Archivos (opcional)
                        </label>
                        <button
                          type="button"
                          onClick={() => setIsNewVersionModalOpen(true)}
                          className="px-3 py-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 border border-blue-600 rounded-md hover:bg-blue-50"
                        >
                          + Agregar archivo
                        </button>
                      </div>
                      <FileList files={newVersionFiles} onRemove={handleRemoveNewVersionFile} />
                      {newVersionFiles.length === 0 && (
                        <p className="text-xs text-gray-500 mt-1">
                          Si no agregas archivos nuevos, se reutilizarán los del último run.
                        </p>
                      )}
                    </div>
                    
                    <div className="flex gap-3">
                      <button
                        onClick={handleGenerateNewVersion}
                        disabled={isGenerating || (newVersionFiles.length === 0 && !revisionNotes.trim())}
                        className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                      >
                        {isGenerating ? 'Generando...' : 'Generar Nueva Versión'}
                      </button>
                      <button
                        onClick={() => {
                          setShowNewVersionForm(false)
                          setNewVersionFiles([])
                          setRevisionNotes('')
                        }}
                        className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 font-medium"
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Lista de runs */}
                {runs.length > 0 ? (
                  <div className="space-y-4">
                    {runs.map((run) => (
                      <div key={run.run_id} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <p className="text-sm font-medium text-gray-900">Run ID: {run.run_id.substring(0, 8)}...</p>
                            <p className="text-xs text-gray-500">
                              {formatDateTime(run.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-3">
                          {run.artifacts.pdf && (
                            <button
                              onClick={() => {
                                // Buscar la versión más relevante para este run que tenga contenido editado.
                                // Prioridad: APPROVED > IN_REVIEW > DRAFT con edición manual.
                                const relevantVersion =
                                  versions.find((v) => v.version_status === 'APPROVED' && v.run_id === run.run_id) ||
                                  versions.find((v) => v.version_status === 'IN_REVIEW' && v.run_id === run.run_id) ||
                                  versions.find((v) => v.version_status === 'DRAFT' && v.run_id === run.run_id && v.content_type === 'manual_edit')
                                if (relevantVersion) {
                                  openVersionPreviewPdf(documentId, relevantVersion.id)
                                } else {
                                  const filename = run.artifacts.pdf!.split('/').pop() || 'process.pdf'
                                  openArtifactFromRun(run.run_id, filename, 'pdf')
                                }
                              }}
                              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium inline-flex items-center gap-2"
                            >
                              📑 Ver PDF
                            </button>
                          )}
                          {run.artifacts.md && (
                            <button
                              onClick={() => {
                                const filename = run.artifacts.md!.split('/').pop() || 'process.md'
                                openArtifactFromRun(run.run_id, filename, 'markdown')
                              }}
                              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium inline-flex items-center gap-2"
                            >
                              📝 Ver Markdown
                            </button>
                          )}
                          {run.artifacts.json && (
                            <button
                              onClick={() => {
                                const filename = run.artifacts.json!.split('/').pop() || 'process.json'
                                openArtifactFromRun(run.run_id, filename, 'json')
                              }}
                              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium inline-flex items-center gap-2"
                            >
                              📄 Ver JSON
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 text-center py-8">
                    No hay versiones generadas aún. Usa el botón "Nueva Versión" para crear la primera.
                  </p>
                )}
              </div>
              
              <FileUploadModal
                isOpen={isNewVersionModalOpen}
                onClose={() => setIsNewVersionModalOpen(false)}
                onAdd={handleAddNewVersionFile}
              />

              {/* Modal: Cancelar envío */}
              {showCancelSubmitConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
                  <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
                    <p className="text-gray-900 mb-6">¿Querés cancelar el envío y volver a borrador?</p>
                    <div className="flex gap-3 justify-end">
                      <button
                        type="button"
                        onClick={() => setShowCancelSubmitConfirm(false)}
                        className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        No
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelSubmission}
                        disabled={isCancelling}
                        className="px-4 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:opacity-50"
                      >
                        {isCancelling ? 'Cancelando...' : 'Sí, volver a borrador'}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Modal: Confirmar aprobación */}
              {showApproveConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
                  <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
                    <p className="text-gray-900 mb-6">¿Confirmar aprobación?</p>
                    <div className="flex gap-3 justify-end">
                      <button
                        type="button"
                        onClick={() => setShowApproveConfirm(false)}
                        className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          setShowApproveConfirm(false)
                          await handleApproveDocument()
                        }}
                        disabled={isValidating}
                        className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                      >
                        {isValidating ? 'Aprobando...' : 'Aprobar'}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Modal: Rechazar (motivo obligatorio) */}
              {showRejectConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
                  <div className="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4">
                    <h3 className="text-lg font-medium text-gray-900 mb-2">Rechazar documento</h3>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Motivo del rechazo <span className="text-red-600">*</span>
                    </label>
                    <textarea
                      value={rejectObservations}
                      onChange={(e) => setRejectObservations(e.target.value)}
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-red-500 mb-4"
                      placeholder="Describe las razones del rechazo y las correcciones necesarias..."
                    />
                    <div className="flex gap-3 justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          setShowRejectConfirm(false)
                        }}
                        className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          setShowRejectConfirm(false)
                          await handleRejectDocument()
                        }}
                        disabled={isValidating || !rejectObservations.trim()}
                        className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
                      >
                        {isValidating ? 'Rechazando...' : 'Confirmar rechazo'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
              
              <ModalComponent />
              
              {/* Sección de Historial y Trazabilidad */}
              <div className="mt-8 pt-8 border-t">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-gray-900">Historial y Trazabilidad</h2>
                  <button
                    onClick={async () => {
                      if (!showHistory) {
                        try {
                          const [log, vers] = await Promise.all([
                            getDocumentAuditLog(documentId),
                            getDocumentVersions(documentId),
                          ])
                          setAuditLog(log)
                          setVersions(vers)
                        } catch (err) {
                          console.error('Error cargando historial:', err)
                          setError('Error al cargar el historial')
                        }
                      }
                      setShowHistory(!showHistory)
                    }}
                    className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm font-medium"
                  >
                    {showHistory ? 'Ocultar Historial' : 'Ver Historial'}
                  </button>
                </div>
                
                {showHistory && (
                  <div className="space-y-6">
                    {/* Versiones Aprobadas */}
                    {(() => {
                      const approvedVersions = versions.filter(v => v.version_status === 'APPROVED')
                      if (approvedVersions.length === 0) {
                        return (
                          <div>
                            <h3 className="text-lg font-medium text-gray-900 mb-3">Versiones Aprobadas</h3>
                            <p className="text-sm text-gray-500">No hay versiones aprobadas.</p>
                          </div>
                        )
                      }
                      return (
                      <div>
                        <h3 className="text-lg font-medium text-gray-900 mb-3">Versiones Aprobadas</h3>
                        <div className="space-y-3">
                          {approvedVersions.map((version) => (
                            <div
                              key={version.id}
                              className={`border rounded-lg p-4 ${
                                version.is_current
                                  ? 'border-green-500 bg-green-50'
                                  : 'border-gray-200 bg-white'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div>
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="font-medium text-gray-900">
                                      Versión {version.version_number}
                                    </span>
                                    {version.is_current && (
                                      <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                                        Actual
                                      </span>
                                    )}
                                    <span className="text-xs text-gray-500">
                                      {version.content_type === 'generated' ? 'Generada' :
                                       version.content_type === 'manual_edit' ? 'Edición Manual' :
                                       version.content_type === 'ai_patch' ? 'Patch por IA' :
                                       version.content_type}
                                    </span>
                                  </div>
                                  <p className="text-xs text-gray-500">
                                    {version.approved_at && (
                                      <>
                                        Aprobada: {formatDateTime(version.approved_at)}
                                        {version.approved_by && ` por ${version.approved_by}`}
                                      </>
                                    )}
                                  </p>
                                  {version.run_id && (
                                    <p className="text-xs text-gray-500">
                                      Run ID: {version.run_id.substring(0, 8)}...
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                      )
                    })()}
                    
                    {/* Audit Log */}
                    {auditLog.length > 0 && (
                      <div>
                        <h3 className="text-lg font-medium text-gray-900 mb-3">Registro de Auditoría</h3>
                        <div className="space-y-2">
                          {auditLog.map((entry) => (
                            <div
                              key={entry.id}
                              className="border border-gray-200 rounded-lg p-3 bg-white"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="font-medium text-gray-900">
                                      {actionToLabel(entry.action)}
                                    </span>
                                    <span className="text-xs text-gray-500">
                                      {entry.entity_type}
                                    </span>
                                  </div>
                                  <p className="text-xs text-gray-500 mb-1">
                                    {formatDateTime(entry.created_at)}
                                  </p>
                                  {entry.changes_json && (
                                    <details className="mt-2">
                                      <summary className="text-xs text-gray-600 cursor-pointer hover:text-gray-900">
                                        Ver cambios
                                      </summary>
                                      <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                        {JSON.stringify(JSON.parse(entry.changes_json), null, 2)}
                                      </pre>
                                    </details>
                                  )}
                                  {entry.metadata_json && (
                                    <details className="mt-2">
                                      <summary className="text-xs text-gray-600 cursor-pointer hover:text-gray-900">
                                        Ver metadata
                                      </summary>
                                      <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                        {JSON.stringify(JSON.parse(entry.metadata_json), null, 2)}
                                      </pre>
                                    </details>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {versions.length === 0 && auditLog.length === 0 && (
                      <p className="text-sm text-gray-500 text-center py-8">
                        No hay historial disponible aún.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

