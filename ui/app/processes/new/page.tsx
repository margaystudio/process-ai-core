'use client'

import { useState, useEffect } from 'react'
import { createProcessRun, getArtifactUrl } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import ProcessNameInput from '@/components/processes/ProcessNameInput'
import ModeSelector from '@/components/processes/ModeSelector'
import OptionalFields from '@/components/processes/OptionalFields'
import FolderTree from '@/components/processes/FolderTree'
import FileUploadModal, { FileType } from '@/components/processes/FileUploadModal'
import FileList from '@/components/processes/FileList'
import { FileItemData } from '@/components/processes/FileItem'

export default function NewProcessPage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const [processName, setProcessName] = useState('')
  const [mode, setMode] = useState<'operativo' | 'gestion'>('operativo')
  const [folderId, setFolderId] = useState('')
  const [detailLevel, setDetailLevel] = useState('')
  const [contextText, setContextText] = useState('')
  
  const [files, setFiles] = useState<FileItemData[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)

  const handleAddFile = (file: File, type: FileType, description: string) => {
    const newFile: FileItemData = {
      id: `${Date.now()}-${Math.random()}`,
      file,
      type,
      description,
    }
    setFiles([...files, newFile])
  }

  const handleRemoveFile = (id: string) => {
    setFiles(files.filter(f => f.id !== id))
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      
      // Campos requeridos
      formData.append('process_name', processName)
      formData.append('mode', mode)
      
      // Campos requeridos
      if (!selectedWorkspaceId) {
        throw new Error('Debes seleccionar un workspace en el header')
      }
      if (!folderId) {
        throw new Error('Debes seleccionar una carpeta')
      }
      formData.append('workspace_id', selectedWorkspaceId)
      formData.append('folder_id', folderId)
      
      // Campos opcionales (solo si tienen valor)
      if (detailLevel) formData.append('detail_level', detailLevel)
      if (contextText.trim()) formData.append('context_text', contextText.trim())
      
      // Agregar archivos según su tipo
      files.forEach((fileItem) => {
        const fieldName = `${fileItem.type}_files`
        formData.append(fieldName, fileItem.file)
      })
      
      const response = await createProcessRun(formData)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Columna izquierda: Árbol de carpetas */}
          <div className="lg:col-span-1">
            {!selectedWorkspaceId ? (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <p className="text-sm text-gray-600 mb-4">
                  Por favor, selecciona un workspace en el header para continuar.
                </p>
                {selectedWorkspace && (
                  <div className="mt-4 p-3 bg-blue-50 rounded-md">
                    <p className="text-sm font-medium text-blue-900">Workspace actual:</p>
                    <p className="text-sm text-blue-700">{selectedWorkspace.name}</p>
                  </div>
                )}
              </div>
            ) : (
              <>
                <div className="mb-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Carpeta * <span className="text-red-500">*</span>
                  </label>
                  {!folderId && (
                    <p className="text-xs text-red-600 mb-2">Debes seleccionar una carpeta para continuar</p>
                  )}
                </div>
                <FolderTree
                  workspaceId={selectedWorkspaceId}
                  selectedFolderId={folderId}
                  onSelectFolder={(id) => setFolderId(id || '')}
                  showSelectable={true}
                  showCrud={false}
                />
              </>
            )}
          </div>

          {/* Columna derecha: Formulario */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-sm p-8">
              <h1 className="text-3xl font-bold mb-6">Nuevo Proceso</h1>

              {!selectedWorkspaceId ? (
                <div className="p-6 bg-yellow-50 border border-yellow-200 rounded-md">
                  <p className="text-sm text-yellow-800">
                    Por favor, selecciona un workspace en el header para crear un proceso.
                  </p>
                </div>
              ) : (
                <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-sm font-medium text-blue-900">Workspace:</p>
                  <p className="text-sm text-blue-700">{selectedWorkspace?.name}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-6">
                <ProcessNameInput 
                  value={processName}
                  onChange={setProcessName}
                />

                <ModeSelector 
                  value={mode}
                  onChange={setMode}
                />

                <OptionalFields
                  detailLevel={detailLevel}
                  contextText={contextText}
                  onDetailLevelChange={setDetailLevel}
                  onContextTextChange={setContextText}
                />

                <div className="pt-6 border-t">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-gray-900">Archivos</h3>
                    <button
                      type="button"
                      onClick={() => setIsModalOpen(true)}
                      className="px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-700 border border-blue-600 rounded-md hover:bg-blue-50"
                    >
                      + Agregar archivo
                    </button>
                  </div>

                  <FileList files={files} onRemove={handleRemoveFile} />
                </div>

                <div className="pt-6 border-t">
                  <div className="flex gap-4">
                    <button
                      type="submit"
                      disabled={isSubmitting || !processName.trim() || files.length === 0 || !selectedWorkspaceId || !folderId}
                      className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                    >
                      {isSubmitting ? 'Procesando...' : 'Generar Documento'}
                    </button>
                    
                    <a
                      href="/"
                      className="px-6 py-3 border border-gray-300 rounded-md hover:bg-gray-50 font-medium"
                    >
                      Cancelar
                    </a>
                  </div>
                </div>
              </form>

              {error && (
                <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
                  <p className="font-semibold">Error</p>
                  <p className="text-sm mt-1">{error}</p>
                </div>
              )}

              {result && (
                <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
                  <p className="font-semibold text-green-800">¡Documento generado exitosamente!</p>
                  <p className="text-sm text-green-700 mt-2">Run ID: {result.run_id}</p>
                  {result.artifacts && (
                    <div className="mt-4 space-y-2">
                      {result.artifacts.json && (
                        <a
                          href={getArtifactUrl(result.run_id, 'process.json')}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-blue-600 hover:underline"
                        >
                          📄 Ver JSON
                        </a>
                      )}
                      {result.artifacts.markdown && (
                        <a
                          href={getArtifactUrl(result.run_id, 'process.md')}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-blue-600 hover:underline"
                        >
                          📝 Ver Markdown
                        </a>
                      )}
                      {result.artifacts.pdf && (
                        <a
                          href={getArtifactUrl(result.run_id, 'process.pdf')}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-blue-600 hover:underline"
                        >
                          📑 Ver PDF
                        </a>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <FileUploadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAdd={handleAddFile}
      />
    </div>
  )
}
