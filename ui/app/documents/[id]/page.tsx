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
  patchDocumentWithAI,
  updateDocumentContent,
  getDocumentAuditLog,
  getDocumentVersions,
  AuditLogEntry,
  DocumentVersion,
} from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import FolderTree from '@/components/processes/FolderTree'
import FileUploadModal, { FileType } from '@/components/processes/FileUploadModal'
import FileList from '@/components/processes/FileList'
import { FileItemData } from '@/components/processes/FileItem'

export default function DocumentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = params.id as string
  const { selectedWorkspaceId } = useWorkspace()
  
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
  const [showValidationForm, setShowValidationForm] = useState(false)
  const [validationObservations, setValidationObservations] = useState('')
  const [rejectObservations, setRejectObservations] = useState('')
  const [rejectingValidationId, setRejectingValidationId] = useState<string | null>(null)
  
  // Correction options
  const [showCorrectionOptions, setShowCorrectionOptions] = useState(false)
  const [correctionType, setCorrectionType] = useState<'manual' | 'ai_patch' | null>(null)
  const [manualEditJson, setManualEditJson] = useState('')
  const [aiPatchObservations, setAiPatchObservations] = useState('')
  const [isPatching, setIsPatching] = useState(false)
  const [isUpdatingContent, setIsUpdatingContent] = useState(false)
  
  // History and audit log
  const [showHistory, setShowHistory] = useState(false)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  
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
        const doc = await getDocument(documentId)
        setDocument(doc)
        setName(doc.name)
        setDescription(doc.description)
        setStatus(doc.status)
        setFolderId(doc.folder_id || '')
        
        // Load catalog options and process-specific fields
        if (doc.document_type === 'process') {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
          const [audienceOpts, detailOpts, processDoc] = await Promise.all([
            getCatalogOptions('audience').catch(() => []),
            getCatalogOptions('detail_level').catch(() => []),
            fetch(`${apiUrl}/api/v1/documents/${documentId}/process`)
              .then(r => r.ok ? r.json() : {})
              .catch(() => ({})),
          ])
          setAudienceOptions(audienceOpts)
          setDetailLevelOptions(detailOpts)
          
          // Set process-specific fields (incluso si están vacíos)
          setAudience(processDoc.audience || '')
          setDetailLevel(processDoc.detail_level || '')
          setContextText(processDoc.context_text || '')
        }
        
        // Load runs
        try {
          const documentRuns = await getDocumentRuns(documentId)
          setRuns(documentRuns)
        } catch (err) {
          console.error('Error cargando runs:', err)
        }
        
        // Load validations
        try {
          const docValidations = await listValidations(documentId)
          setValidations(docValidations)
        } catch (err) {
          console.error('Error cargando validaciones:', err)
        }
        
        // Load history if needed
        if (showHistory) {
          try {
            const [log, vers] = await Promise.all([
              getDocumentAuditLog(documentId),
              getDocumentVersions(documentId),
            ])
            setAuditLog(log)
            setVersions(vers)
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
  }, [documentId])
  
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
  
  // Validation handlers
  const handleCreateValidation = async () => {
    if (!document) return
    
    try {
      setIsValidating(true)
      setError(null)
      
      const lastRun = runs.length > 0 ? runs[0] : null
      const validation = await createValidation(documentId, {
        run_id: lastRun?.run_id,
        observations: validationObservations,
      })
      
      setValidations([...validations, validation])
      setShowValidationForm(false)
      setValidationObservations('')
      
      // Reload document to update status
      const updatedDoc = await getDocument(documentId)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear validación')
    } finally {
      setIsValidating(false)
    }
  }
  
  const handleApproveValidation = async (validationId: string) => {
    if (!document) return
    
    try {
      setIsValidating(true)
      setError(null)
      
      await approveValidation(validationId)
      
      // Reload validations and document
      const [updatedValidations, updatedDoc] = await Promise.all([
        listValidations(documentId),
        getDocument(documentId),
      ])
      
      setValidations(updatedValidations)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aprobar validación')
    } finally {
      setIsValidating(false)
    }
  }
  
  const handleRejectValidation = async (validationId: string) => {
    if (!rejectObservations.trim()) {
      setError('Debes proporcionar observaciones al rechazar')
      return
    }
    
    try {
      setIsValidating(true)
      setError(null)
      
      await rejectValidation(validationId, {
        observations: rejectObservations,
      })
      
      // Reload validations and document
      const [updatedValidations, updatedDoc] = await Promise.all([
        listValidations(documentId),
        getDocument(documentId),
      ])
      
      setValidations(updatedValidations)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
      setRejectingValidationId(null)
      setRejectObservations('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al rechazar validación')
    } finally {
      setIsValidating(false)
    }
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
      
      // Reload runs and document
      const [updatedRuns, updatedDoc] = await Promise.all([
        getDocumentRuns(documentId),
        getDocument(documentId),
      ])
      
      setRuns(updatedRuns)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
      setShowCorrectionOptions(false)
      setCorrectionType(null)
      setAiPatchObservations('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al aplicar patch')
    } finally {
      setIsPatching(false)
    }
  }
  
  const handleManualEdit = async () => {
    if (!manualEditJson.trim()) {
      setError('Debes proporcionar el JSON editado')
      return
    }
    
    try {
      setIsUpdatingContent(true)
      setError(null)
      
      await updateDocumentContent(documentId, manualEditJson)
      
      // Reload document
      const updatedDoc = await getDocument(documentId)
      setDocument(updatedDoc)
      setStatus(updatedDoc.status)
      setShowCorrectionOptions(false)
      setCorrectionType(null)
      setManualEditJson('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al actualizar contenido')
    } finally {
      setIsUpdatingContent(false)
    }
  }
  
  const handleDelete = async () => {
    if (!document) return
    
    if (!confirm(`¿Estás seguro de que deseas eliminar el documento "${document.name}"?\n\nEsta acción no se puede deshacer y eliminará:\n- El documento\n- Todas sus versiones\n- Todos los archivos generados`)) {
      return
    }
    
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
      
      // Recargar runs
      const documentRuns = await getDocumentRuns(documentId)
      setRuns(documentRuns)
      
      // Limpiar formulario
      setNewVersionFiles([])
      setShowNewVersionForm(false)
      
      // Mostrar mensaje de éxito
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al generar nueva versión')
    } finally {
      setIsGenerating(false)
    }
  }
  
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
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Editar
              </button>
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
                      {new Date(document.created_at).toLocaleString('es-UY')}
                    </p>
                  </div>
                </div>
              )}
              
              {/* Sección de Validación */}
              {document.status === 'pending_validation' || document.status === 'rejected' ? (
                <div className="mt-8 pt-8 border-t">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-gray-900">Validación</h2>
                    {document.status === 'pending_validation' && validations.filter(v => v.status === 'pending').length === 0 && (
                      <button
                        onClick={() => setShowValidationForm(true)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
                      >
                        Iniciar Validación
                      </button>
                    )}
                  </div>
                  
                  {showValidationForm && (
                    <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                      <h3 className="text-lg font-medium text-gray-900 mb-4">Nueva Validación</h3>
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Observaciones Iniciales
                        </label>
                        <textarea
                          value={validationObservations}
                          onChange={(e) => setValidationObservations(e.target.value)}
                          rows={3}
                          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                          placeholder="Observaciones o notas iniciales para la validación..."
                        />
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={handleCreateValidation}
                          disabled={isValidating}
                          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                        >
                          {isValidating ? 'Creando...' : 'Crear Validación'}
                        </button>
                        <button
                          onClick={() => {
                            setShowValidationForm(false)
                            setValidationObservations('')
                          }}
                          className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 font-medium"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                  
                  {/* Lista de validaciones */}
                  {validations.length > 0 ? (
                    <div className="space-y-4">
                      {validations.map((validation) => (
                        <div key={validation.id} className="border border-gray-200 rounded-lg p-4">
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`px-2 py-1 rounded text-xs font-medium ${
                                  validation.status === 'approved' ? 'bg-green-100 text-green-800' :
                                  validation.status === 'rejected' ? 'bg-red-100 text-red-800' :
                                  'bg-yellow-100 text-yellow-800'
                                }`}>
                                  {validation.status === 'approved' ? 'Aprobada' :
                                   validation.status === 'rejected' ? 'Rechazada' :
                                   'Pendiente'}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {new Date(validation.created_at).toLocaleString('es-UY')}
                                </span>
                              </div>
                              {validation.observations && (
                                <p className="text-sm text-gray-700 whitespace-pre-wrap">
                                  {validation.observations}
                                </p>
                              )}
                            </div>
                          </div>
                          
                          {validation.status === 'pending' && (
                            <div className="flex gap-3 mt-4">
                              <button
                                onClick={() => handleApproveValidation(validation.id)}
                                disabled={isValidating}
                                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                              >
                                ✓ Aprobar
                              </button>
                              <button
                                onClick={() => setRejectingValidationId(validation.id)}
                                disabled={isValidating}
                                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                              >
                                ✗ Rechazar
                              </button>
                            </div>
                          )}
                          
                          {rejectingValidationId === validation.id && (
                            <div className="mt-4 p-4 bg-red-50 rounded-lg border border-red-200">
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                Observaciones de Rechazo *
                              </label>
                              <textarea
                                value={rejectObservations}
                                onChange={(e) => setRejectObservations(e.target.value)}
                                rows={3}
                                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-red-500 focus:border-red-500 mb-3"
                                placeholder="Describe las razones del rechazo y las correcciones necesarias..."
                              />
                              <div className="flex gap-3">
                                <button
                                  onClick={() => handleRejectValidation(validation.id)}
                                  disabled={isValidating || !rejectObservations.trim()}
                                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                                >
                                  {isValidating ? 'Rechazando...' : 'Confirmar Rechazo'}
                                </button>
                                <button
                                  onClick={() => {
                                    setRejectingValidationId(null)
                                    setRejectObservations('')
                                  }}
                                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium"
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    !showValidationForm && (
                      <p className="text-sm text-gray-500 text-center py-4">
                        No hay validaciones aún. Usa el botón "Iniciar Validación" para crear una.
                      </p>
                    )
                  )}
                  
                  {/* Opciones de corrección para documentos rechazados */}
                  {document.status === 'rejected' && (
                    <div className="mt-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-medium text-gray-900">Corregir Documento</h3>
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
                          
                          {correctionType === 'manual' && (
                            <div className="p-4 bg-white rounded-lg border border-gray-200">
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                JSON Editado
                              </label>
                              <textarea
                                value={manualEditJson}
                                onChange={(e) => setManualEditJson(e.target.value)}
                                rows={12}
                                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm mb-3"
                                placeholder="Pega aquí el JSON del documento editado..."
                              />
                              <div className="flex gap-3">
                                <button
                                  onClick={handleManualEdit}
                                  disabled={isUpdatingContent || !manualEditJson.trim()}
                                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
                                >
                                  {isUpdatingContent ? 'Guardando...' : 'Guardar Edición Manual'}
                                </button>
                                <button
                                  onClick={() => {
                                    setCorrectionType(null)
                                    setManualEditJson('')
                                  }}
                                  className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium"
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ) : null}
              
              {/* Sección de Generar Nueva Versión */}
              <div className="mt-8 pt-8 border-t">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-gray-900">Versiones Generadas</h2>
                  <button
                    onClick={() => setShowNewVersionForm(!showNewVersionForm)}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium"
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
                              {new Date(run.created_at).toLocaleString('es-UY')}
                            </p>
                          </div>
                        </div>
                        <div className="flex gap-3">
                          {run.artifacts.pdf && (
                            <a
                              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${run.artifacts.pdf}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium inline-flex items-center gap-2"
                            >
                              📑 Ver PDF
                            </a>
                          )}
                          {run.artifacts.md && (
                            <a
                              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${run.artifacts.md}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium inline-flex items-center gap-2"
                            >
                              📝 Ver Markdown
                            </a>
                          )}
                          {run.artifacts.json && (
                            <a
                              href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${run.artifacts.json}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium inline-flex items-center gap-2"
                            >
                              📄 Ver JSON
                            </a>
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
                    {/* Versiones */}
                    {versions.length > 0 && (
                      <div>
                        <h3 className="text-lg font-medium text-gray-900 mb-3">Versiones Aprobadas</h3>
                        <div className="space-y-3">
                          {versions.map((version) => (
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
                                    Aprobada: {new Date(version.approved_at).toLocaleString('es-UY')}
                                    {version.approved_by && ` por ${version.approved_by}`}
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
                    )}
                    
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
                                      {entry.action}
                                    </span>
                                    <span className="text-xs text-gray-500">
                                      {entry.entity_type}
                                    </span>
                                  </div>
                                  <p className="text-xs text-gray-500 mb-1">
                                    {new Date(entry.created_at).toLocaleString('es-UY')}
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

