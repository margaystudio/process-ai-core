'use client'

import { useState, useEffect, useCallback } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'

const STORAGE_KEY_PREFIX = 'context_files_'

export interface ContextFile {
  id: string
  name: string
  size: number
  type: string
  content?: string
  addedAt: string
}

const ALLOWED_TYPES = ['.txt', '.md', '.pdf', '.doc', '.docx']
const TEXT_TYPES = ['.txt', '.md']

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve((reader.result as string) || '')
    reader.onerror = () => reject(new Error('Error al leer el archivo'))
    reader.readAsText(file, 'UTF-8')
  })
}

export default function ContextoPage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const [files, setFiles] = useState<ContextFile[]>([])
  const [loading, setLoading] = useState(true)
  const [dragActive, setDragActive] = useState(false)
  const [previewFile, setPreviewFile] = useState<ContextFile | null>(null)

  const storageKey = selectedWorkspaceId ? `${STORAGE_KEY_PREFIX}${selectedWorkspaceId}` : null

  const loadFiles = useCallback(() => {
    if (!storageKey || typeof window === 'undefined') {
      setFiles([])
      setLoading(false)
      return
    }
    try {
      const stored = localStorage.getItem(storageKey)
      const parsed = stored ? JSON.parse(stored) : []
      setFiles(Array.isArray(parsed) ? parsed : [])
    } catch {
      setFiles([])
    } finally {
      setLoading(false)
    }
  }, [storageKey])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  const saveFiles = (newFiles: ContextFile[]) => {
    if (!storageKey) return
    localStorage.setItem(storageKey, JSON.stringify(newFiles))
    setFiles(newFiles)
  }

  const processFile = async (file: File): Promise<ContextFile | null> => {
    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
    if (!ALLOWED_TYPES.includes(ext)) {
      return null
    }

    let content: string | undefined
    if (TEXT_TYPES.includes(ext)) {
      try {
        content = await readFileAsText(file)
      } catch {
        content = '(No se pudo leer el contenido)'
      }
    }
    // PDF y DOC/DOCX: por ahora solo guardamos metadata (la extracción requiere backend)

    return {
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      type: file.type,
      content,
      addedAt: new Date().toISOString(),
    }
  }

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList?.length) return

    const newItems: ContextFile[] = []
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i]
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
      if (!ALLOWED_TYPES.includes(ext)) continue

      const item = await processFile(file)
      if (item) newItems.push(item)
    }

    if (newItems.length > 0) {
      saveFiles([...files, ...newItems])
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = () => {
    setDragActive(false)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files)
    e.target.value = ''
  }

  const removeFile = (id: string) => {
    saveFiles(files.filter((f) => f.id !== id))
    if (previewFile?.id === id) setPreviewFile(null)
  }

  if (!selectedWorkspaceId) {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
            <p className="text-yellow-800">
              Por favor, selecciona un espacio de trabajo en el header para gestionar los archivos de contexto.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">
            Contexto del negocio
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Archivos con información general de tu negocio (manuales, políticas, descripciones) que enriquecen la generación de procesos
          </p>
        </div>

        {/* Zona de carga */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
            dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white hover:border-gray-400'
          }`}
        >
          <input
            type="file"
            multiple
            accept={ALLOWED_TYPES.join(',')}
            onChange={handleInputChange}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
          <div className="pointer-events-none">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="mt-2 text-sm text-gray-600">
              Arrastra archivos aquí o haz clic para seleccionar
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Formatos: TXT, MD, PDF, DOC, DOCX
            </p>
          </div>
        </div>

        {/* Lista de archivos */}
        <div className="mt-6 bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Archivos de contexto ({files.length})
          </h2>

          {loading ? (
            <div className="text-center py-8 text-gray-500">Cargando...</div>
          ) : files.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p className="mb-2">No hay archivos de contexto cargados</p>
              <p className="text-sm">
                Los archivos TXT y MD se indexan para enriquecer el contexto al generar procesos.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {files.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <div className="flex items-center min-w-0 flex-1">
                    <svg
                      className="h-8 w-8 text-gray-400 flex-shrink-0 mr-3"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900 truncate">{file.name}</p>
                      <p className="text-xs text-gray-500">
                        {(file.size / 1024).toFixed(1)} KB
                        {file.content !== undefined && (
                          <span className="ml-2 text-green-600">• Texto indexado</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 flex-shrink-0 ml-4">
                    {file.content !== undefined && (
                      <button
                        onClick={() => setPreviewFile(previewFile?.id === file.id ? null : file)}
                        className="px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-md"
                      >
                        {previewFile?.id === file.id ? 'Ocultar' : 'Ver'}
                      </button>
                    )}
                    <button
                      onClick={() => removeFile(file.id)}
                      className="p-1.5 text-red-600 hover:bg-red-50 rounded-md"
                      title="Eliminar"
                    >
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {previewFile && previewFile.content && (
            <div className="mt-4 p-4 bg-gray-100 rounded-lg border border-gray-200">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Vista previa: {previewFile.name}
              </h3>
              <pre className="text-sm text-gray-800 whitespace-pre-wrap max-h-64 overflow-y-auto">
                {previewFile.content}
              </pre>
            </div>
          )}
        </div>

        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Tip:</strong> Los archivos de contexto (manuales, políticas, descripciones del negocio) se utilizan para enriquecer la generación de procesos. El contenido de archivos TXT y MD se indexa automáticamente.
          </p>
        </div>
      </div>
    </div>
  )
}
