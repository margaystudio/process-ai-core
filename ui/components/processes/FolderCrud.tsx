'use client'

import { useState } from 'react'
import { createFolder, updateFolder, deleteFolder, Folder, listFolders } from '@/lib/api'

interface FolderCrudProps {
  workspaceId: string
  folders: Folder[]
  onFoldersChange: () => void
  parentId?: string | null
}

export default function FolderCrud({ workspaceId, folders, onFoldersChange, parentId = null }: FolderCrudProps) {
  const [isCreating, setIsCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [parentIdForNew, setParentIdForNew] = useState<string | null>(null)
  
  const [newFolderName, setNewFolderName] = useState('')
  const [newFolderPath, setNewFolderPath] = useState('')
  const [editFolderName, setEditFolderName] = useState('')
  const [editFolderPath, setEditFolderPath] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Filtrar carpetas por parent_id
  const filteredFolders = folders.filter(f => 
    (parentId === null && !f.parent_id) || 
    (parentId !== null && f.parent_id === parentId)
  )

  const handleCreate = async () => {
    if (!newFolderName.trim()) {
      setError('El nombre es requerido')
      return
    }

    if (!workspaceId) {
      setError('Workspace ID es requerido')
      return
    }

    try {
      setError(null)
      const actualParentId = parentIdForNew !== null ? parentIdForNew : (parentId || undefined)
      
      // Construir path automáticamente si no se especifica
      let finalPath = newFolderPath.trim() || newFolderName.trim()
      if (actualParentId && !newFolderPath.trim()) {
        // Si tiene parent, construir path jerárquico
        const parentFolder = folders.find(f => f.id === actualParentId)
        if (parentFolder) {
          finalPath = parentFolder.path ? `${parentFolder.path}/${newFolderName.trim()}` : `${parentFolder.name}/${newFolderName.trim()}`
        }
      }
      
      console.log('Creando carpeta:', {
        workspace_id: workspaceId,
        name: newFolderName.trim(),
        path: finalPath,
        parent_id: actualParentId,
        sort_order: filteredFolders.length,
      })
      
      const created = await createFolder({
        workspace_id: workspaceId,
        name: newFolderName.trim(),
        path: finalPath,
        parent_id: actualParentId || undefined,
        sort_order: filteredFolders.length,
      })
      
      console.log('Carpeta creada exitosamente:', created)
      
      // Limpiar formulario
      setNewFolderName('')
      setNewFolderPath('')
      setIsCreating(false)
      setParentIdForNew(null)
      
      // Recargar carpetas
      console.log('Recargando carpetas...')
      await onFoldersChange()
      console.log('Carpetas recargadas')
    } catch (err) {
      console.error('Error al crear carpeta:', err)
      setError(err instanceof Error ? err.message : 'Error al crear carpeta')
    }
  }

  const handleStartEdit = (folder: Folder) => {
    setEditingId(folder.id)
    setEditFolderName(folder.name)
    setEditFolderPath(folder.path)
    setError(null)
  }

  const handleUpdate = async (folderId: string) => {
    if (!editFolderName.trim()) {
      setError('El nombre es requerido')
      return
    }

    try {
      setError(null)
      await updateFolder(folderId, {
        name: editFolderName.trim(),
        path: editFolderPath.trim() || editFolderName.trim(),
      })
      setEditingId(null)
      onFoldersChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al actualizar carpeta')
    }
  }

  const handleDelete = async (folderId: string) => {
    if (!confirm('¿Estás seguro de eliminar esta carpeta? Los documentos quedarán sin carpeta.')) {
      return
    }

    try {
      setError(null)
      await deleteFolder(folderId)
      setDeletingId(null)
      onFoldersChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al eliminar carpeta')
    }
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Botón para crear nueva carpeta - solo mostrar en raíz, más discreto */}
      {!isCreating && parentId === null && (
        <button
          onClick={() => {
            setIsCreating(true)
            setParentIdForNew(null)
          }}
          className="w-full px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded hover:bg-gray-50 transition"
          title="Crear nueva carpeta"
        >
          + Nueva Carpeta
        </button>
      )}

      {/* Formulario de creación */}
      {isCreating && (
        <div className="p-3 bg-gray-50 border border-gray-200 rounded-md space-y-2">
          <input
            type="text"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            placeholder="Nombre de la carpeta *"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            autoFocus
          />
          <input
            type="text"
            value={newFolderPath}
            onChange={(e) => setNewFolderPath(e.target.value)}
            placeholder="Path (opcional, se usa el nombre si está vacío)"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              className="flex-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Crear
            </button>
            <button
              onClick={() => {
                setIsCreating(false)
                setNewFolderName('')
                setNewFolderPath('')
                setParentIdForNew(null)
                setError(null)
              }}
              className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Lista de carpetas */}
      <div className="space-y-2">
        {filteredFolders.map((folder) => (
          <div
            key={folder.id}
            className="p-3 bg-white border border-gray-200 rounded-md hover:border-gray-300"
          >
            {editingId === folder.id ? (
              // Modo edición
              <div className="space-y-2">
                <input
                  type="text"
                  value={editFolderName}
                  onChange={(e) => setEditFolderName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  autoFocus
                />
                <input
                  type="text"
                  value={editFolderPath}
                  onChange={(e) => setEditFolderPath(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleUpdate(folder.id)}
                    className="flex-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                  >
                    Guardar
                  </button>
                  <button
                    onClick={() => {
                      setEditingId(null)
                      setError(null)
                    }}
                    className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              // Modo visualización
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {folder.name}
                    </div>
                    {folder.path !== folder.name && (
                      <div className="text-xs text-gray-500 truncate">
                        {folder.path}
                      </div>
                    )}
                  </div>
                  <div className="flex gap-1 ml-2">
                    <button
                      onClick={() => {
                        setNewFolderName('')
                        setNewFolderPath('')
                        setIsCreating(true)
                        // Establecer parent_id para crear subcarpeta
                        setParentIdForNew(folder.id)
                      }}
                      className="px-2 py-1 text-xs text-blue-600 hover:text-blue-900 hover:bg-blue-50 rounded"
                      title="Crear subcarpeta"
                    >
                      ➕
                    </button>
                    <button
                      onClick={() => handleStartEdit(folder)}
                      className="px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded"
                      title="Editar"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={() => {
                        setDeletingId(folder.id)
                        handleDelete(folder.id)
                      }}
                      className="px-2 py-1 text-xs text-red-600 hover:text-red-900 hover:bg-red-50 rounded"
                      title="Eliminar"
                      disabled={deletingId === folder.id}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
                {/* Mostrar subcarpetas si existen */}
                {(() => {
                  const subfolders = folders.filter(f => f.parent_id === folder.id)
                  const showSubfolders = subfolders.length > 0 || (isCreating && parentIdForNew === folder.id)
                  if (showSubfolders) {
                    return (
                      <div className="mt-2 ml-4 pl-3 border-l-2 border-gray-200">
                        <FolderCrud
                          workspaceId={workspaceId}
                          folders={folders}
                          onFoldersChange={onFoldersChange}
                          parentId={folder.id}
                        />
                      </div>
                    )
                  }
                  return null
                })()}
              </div>
            )}
          </div>
        ))}
      </div>

      {filteredFolders.length === 0 && !isCreating && parentId === null && (
        <p className="text-sm text-gray-500 text-center py-4">
          No hay carpetas {parentId ? 'en esta carpeta' : 'en la raíz'}. Hacé clic en "+ Nueva Carpeta" para crear la primera.
        </p>
      )}
    </div>
  )
}

