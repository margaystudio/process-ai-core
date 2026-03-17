'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useCanEditWorkspace } from '@/hooks/useHasPermission'
import {
  createContextFolder,
  deleteContextFile,
  downloadContextFile,
  listContextFiles,
  listContextFolders,
  moveContextFile,
  moveContextFolder,
  uploadContextFile,
  type ContextFileResponse,
  type ContextFolderResponse,
} from '@/lib/api'

const ALLOWED_TYPES = ['.txt', '.md', '.pdf', '.doc', '.docx']

type DragPayload =
  | { kind: 'file'; id: string }
  | { kind: 'folder'; id: string }

export default function ContextPage() {
  const { selectedWorkspaceId } = useWorkspace()
  const { hasPermission: canEditWorkspace } = useCanEditWorkspace()
  const [files, setFiles] = useState<ContextFileResponse[]>([])
  const [folders, setFolders] = useState<ContextFolderResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [previewFile, setPreviewFile] = useState<ContextFileResponse | null>(null)
  const [viewPdfUrl, setViewPdfUrl] = useState<{ url: string; name: string; fileId: string } | null>(null)
  const [uploadFolderId, setUploadFolderId] = useState<string | null>(null)
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null)
  const [dragOverRoot, setDragOverRoot] = useState(false)
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({})
  const [isFolderModalOpen, setIsFolderModalOpen] = useState(false)
  const [folderModalParentId, setFolderModalParentId] = useState<string | null>(null)
  const [folderName, setFolderName] = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [fileToDelete, setFileToDelete] = useState<ContextFileResponse | null>(null)
  const [deletingFile, setDeletingFile] = useState(false)

  const loadData = useCallback(async () => {
    if (!selectedWorkspaceId) {
      setFiles([])
      setFolders([])
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const [filesData, foldersData] = await Promise.all([
        listContextFiles(selectedWorkspaceId),
        listContextFolders(selectedWorkspaceId),
      ])
      setFiles(filesData)
      setFolders(foldersData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setFiles([])
      setFolders([])
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspaceId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const filesByFolder = useMemo(() => {
    const map = new Map<string | null, ContextFileResponse[]>()
    for (const file of files) {
      const key = file.folder_id ?? null
      const current = map.get(key) || []
      current.push(file)
      map.set(key, current)
    }
    return map
  }, [files])

  const foldersByParent = useMemo(() => {
    const map = new Map<string | null, ContextFolderResponse[]>()
    for (const folder of folders) {
      const key = folder.parent_id ?? null
      const current = map.get(key) || []
      current.push(folder)
      map.set(key, current)
    }
    return map
  }, [folders])

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList?.length || !selectedWorkspaceId) return

    const toUpload: File[] = []
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i]
      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
      if (ALLOWED_TYPES.includes(ext)) toUpload.push(file)
    }

    if (toUpload.length === 0) return

    setUploading(true)
    setError(null)
    try {
      for (const file of toUpload) {
        await uploadContextFile(selectedWorkspaceId, file, uploadFolderId)
      }
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al subir')
    } finally {
      setUploading(false)
    }
  }

  const handleDropUpload = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleDragOverUpload = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(true)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files)
    e.target.value = ''
  }

  const openCreateFolderModal = (parentId: string | null) => {
    setFolderModalParentId(parentId)
    setFolderName('')
    setIsFolderModalOpen(true)
  }

  const closeCreateFolderModal = () => {
    if (creatingFolder) return
    setIsFolderModalOpen(false)
    setFolderModalParentId(null)
    setFolderName('')
  }

  const createFolderAt = async () => {
    if (!selectedWorkspaceId || !folderName.trim()) return

    try {
      setCreatingFolder(true)
      await createContextFolder(selectedWorkspaceId, {
        name: folderName.trim(),
        parent_id: folderModalParentId,
      })
      await loadData()
      closeCreateFolderModal()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear carpeta')
    } finally {
      setCreatingFolder(false)
    }
  }

  const removeFile = async (id: string) => {
    if (!selectedWorkspaceId) return
    try {
      setDeletingFile(true)
      await deleteContextFile(selectedWorkspaceId, id)
      setFiles((prev) => prev.filter((f) => f.id !== id))
      if (previewFile?.id === id) setPreviewFile(null)
      setFileToDelete(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al eliminar')
    } finally {
      setDeletingFile(false)
    }
  }

  const handleDownload = async (file: Pick<ContextFileResponse, 'id' | 'name'>) => {
    if (!selectedWorkspaceId) return
    try {
      await downloadContextFile(selectedWorkspaceId, file.id, file.name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al descargar')
    }
  }

  const handleView = (file: ContextFileResponse) => {
    if (file.content != null && file.content !== '') {
      setPreviewFile(previewFile?.id === file.id ? null : file)
      return
    }

    setError(null)
    setViewPdfUrl({
      url: `/api/context-file/${selectedWorkspaceId}/${file.id}`,
      name: file.name,
      fileId: file.id,
    })
  }

  const closeViewPdf = () => setViewPdfUrl(null)

  const onDragStartItem = (payload: DragPayload) => (e: React.DragEvent) => {
    e.dataTransfer.setData('application/json', JSON.stringify(payload))
    e.dataTransfer.effectAllowed = 'move'
  }

  const moveDraggedItem = async (payload: DragPayload, targetFolderId: string | null) => {
    if (!selectedWorkspaceId) return
    try {
      setError(null)
      if (payload.kind === 'file') {
        await moveContextFile(selectedWorkspaceId, payload.id, targetFolderId)
      } else {
        await moveContextFolder(selectedWorkspaceId, payload.id, { parent_id: targetFolderId })
      }
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al mover')
    } finally {
      setDragOverFolderId(null)
      setDragOverRoot(false)
    }
  }

  const onDropTarget = (targetFolderId: string | null) => async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const raw = e.dataTransfer.getData('application/json')
    if (!raw) return

    const payload = JSON.parse(raw) as DragPayload
    await moveDraggedItem(payload, targetFolderId)
  }

  const toggleFolderExpanded = (folderId: string) => {
    setExpandedFolders((prev) => ({
      ...prev,
      [folderId]: !prev[folderId],
    }))
  }

  const renderFileRow = (file: ContextFileResponse, depth: number) => (
    <div
      key={file.id}
      draggable={canEditWorkspace}
      onDragStart={canEditWorkspace ? onDragStartItem({ kind: 'file', id: file.id }) : undefined}
      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
      style={{ marginLeft: depth * 20 }}
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
            {file.content != null && file.content !== '' && (
              <span className="ml-2 text-green-600">• Texto indexado</span>
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center space-x-1 flex-shrink-0 ml-4">
        <button
          onClick={() => handleView(file)}
          className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-md"
          title={file.content != null && file.content !== '' && previewFile?.id === file.id ? 'Ocultar' : 'Ver'}
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
        </button>
        <button
          onClick={() => handleDownload(file)}
          className="p-1.5 text-green-600 hover:bg-green-50 rounded-md"
          title="Descargar"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </button>
        {canEditWorkspace && (
          <button
            onClick={() => setFileToDelete(file)}
            className="p-1.5 text-red-600 hover:bg-red-50 rounded-md"
            title="Eliminar"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )

  const renderFolderNode = (folder: ContextFolderResponse, depth = 0): React.ReactNode => {
    const childFolders = foldersByParent.get(folder.id) || []
    const childFiles = filesByFolder.get(folder.id) || []
    const isDropActive = dragOverFolderId === folder.id
    const isExpanded = !!expandedFolders[folder.id]
    const hasChildren = childFolders.length > 0 || childFiles.length > 0

    return (
      <div key={folder.id} className="space-y-2">
        <div
          draggable={canEditWorkspace}
          onDragStart={canEditWorkspace ? onDragStartItem({ kind: 'folder', id: folder.id }) : undefined}
          onDragOver={(e) => {
            if (!canEditWorkspace) return
            e.preventDefault()
            e.stopPropagation()
            setDragOverFolderId(folder.id)
          }}
          onDragLeave={() => {
            if (dragOverFolderId === folder.id) setDragOverFolderId(null)
          }}
          onDrop={canEditWorkspace ? onDropTarget(folder.id) : undefined}
          className={`flex items-center justify-between rounded-lg border px-3 py-2 ${
            isDropActive ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-white'
          }`}
          style={{ marginLeft: depth * 20 }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => toggleFolderExpanded(folder.id)}
              className="flex items-center gap-2 rounded-md p-1 hover:bg-gray-100"
              title={isExpanded ? 'Cerrar carpeta' : 'Abrir carpeta'}
            >
              <svg
                className={`h-4 w-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''} ${hasChildren ? '' : 'opacity-40'}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {isExpanded ? (
                <svg className="h-5 w-5 text-amber-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 6a2 2 0 012-2h3.172a2 2 0 011.414.586l1.121 1.121A2 2 0 0011.121 6H16a2 2 0 012 2v1H2V6z" />
                  <path d="M2 10h16l-1.2 5.4A2 2 0 0114.85 17H5.15a2 2 0 01-1.95-1.6L2 10z" />
                </svg>
              ) : (
                <svg className="h-5 w-5 text-amber-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 4a2 2 0 012-2h3.172a2 2 0 011.414.586l1.828 1.828H16a2 2 0 012 2v1H2V4z" />
                  <path d="M2 8h16v6a2 2 0 01-2 2H4a2 2 0 01-2-2V8z" />
                </svg>
              )}
            </button>
            <div className="min-w-0">
              <p className="font-medium text-gray-900 truncate">{folder.name}</p>
              <p className="text-xs text-gray-500 truncate">{folder.path}</p>
            </div>
          </div>
          {canEditWorkspace && (
            <div className="flex items-center gap-1 ml-3">
              <button
                onClick={() => setUploadFolderId(folder.id)}
                className={`px-2 py-1 text-xs rounded-md ${
                  uploadFolderId === folder.id ? 'bg-blue-100 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                }`}
                title="Subir archivos a esta carpeta"
              >
                Subir aquí
              </button>
              <button
                onClick={() => openCreateFolderModal(folder.id)}
                className="px-2 py-1 text-xs rounded-md text-gray-600 hover:bg-gray-100"
                title="Crear subcarpeta"
              >
                + Subcarpeta
              </button>
            </div>
          )}
        </div>

        {isExpanded && childFolders.map((child) => renderFolderNode(child, depth + 1))}
        {isExpanded && childFiles.map((file) => renderFileRow(file, depth + 1))}
      </div>
    )
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

  const rootFolders = foldersByParent.get(null) || []
  const rootFiles = filesByFolder.get(null) || []

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Contexto del negocio</h1>
            <p className="text-sm text-gray-500 mt-1">
              Archivos con información general de tu negocio, organizados en carpetas y subcarpetas.
            </p>
          </div>
          {canEditWorkspace && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setUploadFolderId(null)}
                className={`px-3 py-2 text-sm rounded-md border ${
                  uploadFolderId === null ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-700'
                }`}
              >
                Subir a raíz
              </button>
              <button
                onClick={() => openCreateFolderModal(null)}
                className="px-3 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
              >
                + Nueva carpeta
              </button>
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {canEditWorkspace && (
          <div
            onDrop={handleDropUpload}
            onDragOver={handleDragOverUpload}
            onDragLeave={() => setDragActive(false)}
            className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white hover:border-gray-400'
            } ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
          >
            <input
              type="file"
              multiple
              accept={ALLOWED_TYPES.join(',')}
              onChange={handleInputChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              disabled={uploading}
            />
            <div className="pointer-events-none">
              <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                <path
                  d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <p className="mt-2 text-sm text-gray-600">
                {uploading ? 'Subiendo...' : 'Arrastra archivos aquí o haz clic para seleccionar'}
              </p>
              <p className="mt-2 text-sm font-semibold text-gray-700">
                Destino: {uploadFolderId ? folders.find((folder) => folder.id === uploadFolderId)?.path || 'Carpeta seleccionada' : 'Raíz'}
              </p>
            </div>
          </div>
        )}

        <div
          className={`mt-6 bg-white rounded-lg border p-6 ${dragOverRoot ? 'border-blue-400 bg-blue-50' : 'border-gray-200'}`}
          onDragOver={(e) => {
            if (!canEditWorkspace) return
            e.preventDefault()
            e.stopPropagation()
            setDragOverRoot(true)
          }}
          onDragLeave={() => setDragOverRoot(false)}
          onDrop={canEditWorkspace ? onDropTarget(null) : undefined}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Archivos de contexto ({files.length}) / Carpetas ({folders.length})
            </h2>
            {canEditWorkspace && (
              <p className="text-xs text-gray-500">Arrastra archivos o carpetas para reubicarlos</p>
            )}
          </div>

          {loading ? (
            <div className="text-center py-8 text-gray-500">Cargando...</div>
          ) : rootFolders.length === 0 && rootFiles.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>No hay archivos ni carpetas de contexto cargados</p>
            </div>
          ) : (
            <div className="space-y-3">
              {rootFiles.map((file) => renderFileRow(file, 0))}
              {rootFolders.map((folder) => renderFolderNode(folder))}
            </div>
          )}

          {previewFile && previewFile.content && (
            <div className="mt-4 p-4 bg-gray-100 rounded-lg border border-gray-200">
              <h3 className="text-sm font-medium text-gray-700 mb-2">Vista previa: {previewFile.name}</h3>
              <pre className="text-sm text-gray-800 whitespace-pre-wrap max-h-64 overflow-y-auto">
                {previewFile.content}
              </pre>
            </div>
          )}
        </div>
      </div>

      {viewPdfUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={closeViewPdf}>
          <div
            className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-3 border-b border-gray-200">
              <h3 className="font-medium text-gray-900 truncate">{viewPdfUrl.name}</h3>
              <button onClick={closeViewPdf} className="p-2 text-gray-500 hover:bg-gray-100 rounded-md" aria-label="Cerrar">
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-hidden p-4 min-h-[400px]">
              <iframe src={viewPdfUrl.url} title={viewPdfUrl.name} className="w-full h-[80vh] border-0 rounded" />
              <p className="mt-2 text-sm text-gray-500 text-center">
                Si no ves el archivo,{' '}
                <button
                  type="button"
                  onClick={() => handleDownload({ id: viewPdfUrl.fileId, name: viewPdfUrl.name })}
                  className="text-blue-600 hover:underline"
                >
                  descárgalo aquí
                </button>
              </p>
            </div>
          </div>
        </div>
      )}

      {isFolderModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div
              className="fixed inset-0 bg-black/50 transition-opacity"
              onClick={closeCreateFolderModal}
            />

            <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full border border-gray-200">
              <div className="flex items-start justify-between p-5 border-b border-gray-100">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {folderModalParentId ? 'Nueva subcarpeta' : 'Nueva carpeta'}
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {folderModalParentId
                      ? 'Crea una subcarpeta dentro de la carpeta seleccionada.'
                      : 'Organiza tus archivos de contexto en carpetas jerárquicas.'}
                  </p>
                </div>
                <button
                  onClick={closeCreateFolderModal}
                  className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md"
                  aria-label="Cerrar"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  createFolderAt()
                }}
                className="p-5"
              >
                <label htmlFor="folder-name" className="block text-sm font-medium text-gray-700 mb-2">
                  Nombre de la carpeta
                </label>
                <input
                  id="folder-name"
                  type="text"
                  value={folderName}
                  onChange={(e) => setFolderName(e.target.value)}
                  placeholder="Ej: Contratos, RRHH, Legales"
                  autoFocus
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                />

                <div className="mt-5 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={closeCreateFolderModal}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                    disabled={creatingFolder}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-60"
                    disabled={creatingFolder || !folderName.trim()}
                  >
                    {creatingFolder ? 'Creando...' : 'Crear carpeta'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {fileToDelete && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div
              className="fixed inset-0 bg-black/50 transition-opacity"
              onClick={() => !deletingFile && setFileToDelete(null)}
            />

            <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full border border-gray-200">
              <div className="flex items-start justify-between p-5 border-b border-gray-100">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Eliminar archivo</h2>
                  <p className="text-sm text-gray-500 mt-1">
                    Esta acción quitará el archivo del contexto y no se puede deshacer.
                  </p>
                </div>
                <button
                  onClick={() => !deletingFile && setFileToDelete(null)}
                  className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md"
                  aria-label="Cerrar"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="p-5">
                <div className="rounded-lg border border-red-100 bg-red-50 p-4">
                  <p className="text-sm text-red-800">
                    ¿Estás seguro que quieres eliminar <span className="font-semibold">{fileToDelete.name}</span>?
                  </p>
                </div>

                <div className="mt-5 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setFileToDelete(null)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                    disabled={deletingFile}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFile(fileToDelete.id)}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-60"
                    disabled={deletingFile}
                  >
                    {deletingFile ? 'Eliminando...' : 'Sí, eliminar'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
