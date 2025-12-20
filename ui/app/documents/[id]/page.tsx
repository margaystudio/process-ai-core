'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { getDocument, updateDocument, getCatalogOptions, getDocumentRuns, createDocumentRun, getArtifactUrl, CatalogOption, Document, DocumentUpdateRequest } from '@/lib/api'
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
              <button
                onClick={() => setIsEditing(true)}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Editar
              </button>
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
                      <option value="active">Activo</option>
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
                      document.status === 'active' ? 'bg-green-100 text-green-800' :
                      document.status === 'archived' ? 'bg-gray-100 text-gray-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}>
                      {document.status === 'active' ? 'Activo' :
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
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

