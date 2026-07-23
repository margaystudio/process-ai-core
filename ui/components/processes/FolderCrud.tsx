'use client'

import { useState } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { type Folder } from '@/lib/api'
import { useFolderCrud } from '@/hooks/useFolderCrud'

const FOLDER_COLOR_PALETTE = [
  '#48569C',
  '#2F9E62',
  '#C99A2E',
  '#2E8B8B',
  '#CB4242',
  '#6366F1',
  '#8B5CF6',
  '#64748B',
] as const

export const DEFAULT_FOLDER_COLOR = FOLDER_COLOR_PALETTE[0]

function FolderColorPicker({
  value,
  onChange,
}: {
  value: string
  onChange: (color: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {FOLDER_COLOR_PALETTE.map((color) => (
        <button
          key={color}
          type="button"
          onClick={() => onChange(color)}
          aria-label={`Color ${color}`}
          aria-pressed={value === color}
          className={
            'h-7 w-7 rounded-full border-2 transition ' +
            (value === color ? 'border-ink-900 scale-110' : 'border-transparent hover:scale-105')
          }
          style={{ backgroundColor: color }}
        />
      ))}
    </div>
  )
}

interface FolderCrudProps {
  workspaceId: string
  folders: Folder[]
  onFoldersChange: () => void
  parentId?: string | null
}

export default function FolderCrud({ workspaceId, folders, onFoldersChange, parentId = null }: FolderCrudProps) {
  const { createFolder, updateFolder, deleteFolder, saving } = useFolderCrud(workspaceId)

  const [isCreating, setIsCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [parentIdForNew, setParentIdForNew] = useState<string | null>(null)

  const [newFolderName, setNewFolderName] = useState('')
  const [newFolderPath, setNewFolderPath] = useState('')
  const [newFolderColor, setNewFolderColor] = useState<string>(DEFAULT_FOLDER_COLOR)
  const [editFolderName, setEditFolderName] = useState('')
  const [editFolderPath, setEditFolderPath] = useState('')
  const [editFolderColor, setEditFolderColor] = useState<string>(DEFAULT_FOLDER_COLOR)
  const [error, setError] = useState<string | null>(null)

  // Filtrar carpetas por parent_id
  const filteredFolders = folders.filter(f =>
    (parentId === null && !f.parent_id) ||
    (parentId !== null && f.parent_id === parentId)
  )

  const handleCreate = async () => {
    if (saving) return // evitar doble-submit (crea carpetas duplicadas)
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

      await createFolder({
        name: newFolderName.trim(),
        path: newFolderPath.trim() || undefined,
        parentId: actualParentId,
        sortOrder: filteredFolders.length,
        color: newFolderColor,
        allFolders: folders,
      })

      // Limpiar formulario
      setNewFolderName('')
      setNewFolderPath('')
      setNewFolderColor(DEFAULT_FOLDER_COLOR)
      setIsCreating(false)
      setParentIdForNew(null)

      await onFoldersChange()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear carpeta')
    }
  }

  const handleStartEdit = (folder: Folder) => {
    setEditingId(folder.id)
    setEditFolderName(folder.name)
    setEditFolderPath(folder.path)
    setEditFolderColor(folder.color || DEFAULT_FOLDER_COLOR)
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
        color: editFolderColor,
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
        <div className="p-3 bg-danger-bg border border-danger-bd rounded-md text-danger text-sm">
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
          className="w-full px-2 py-1.5 text-xs text-ink-500 hover:text-ink-700 border border-ink-200 rounded hover:bg-ink-50 transition"
          title="Crear nueva carpeta"
        >
          + Nueva Carpeta
        </button>
      )}

      {/* Formulario de creación */}
      {isCreating && (
        <div className="p-3 bg-ink-50 border border-ink-200 rounded-md space-y-2">
          <input
            type="text"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            placeholder="Nombre de la carpeta *"
            className="w-full px-3 py-2 text-sm border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
            autoFocus
          />
          <input
            type="text"
            value={newFolderPath}
            onChange={(e) => setNewFolderPath(e.target.value)}
            placeholder="Path (opcional, se usa el nombre si está vacío)"
            className="w-full px-3 py-2 text-sm border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
          />
          <div>
            <div className="mb-1.5 text-xs font-medium text-ink-600">Color</div>
            <FolderColorPicker value={newFolderColor} onChange={setNewFolderColor} />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={saving}
              className="flex-1 px-3 py-1.5 text-sm bg-action text-white rounded-md hover:bg-action-hover disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Creando...' : 'Crear'}
            </button>
            <button
              onClick={() => {
                setIsCreating(false)
                setNewFolderName('')
                setNewFolderPath('')
                setNewFolderColor(DEFAULT_FOLDER_COLOR)
                setParentIdForNew(null)
                setError(null)
              }}
              className="flex-1 px-3 py-1.5 text-sm border border-ink-300 rounded-md hover:bg-ink-50"
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
            className="p-3 bg-white border border-ink-200 rounded-md hover:border-ink-300"
          >
            {editingId === folder.id ? (
              // Modo edición
              <div className="space-y-2">
                <input
                  type="text"
                  value={editFolderName}
                  onChange={(e) => setEditFolderName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
                  autoFocus
                />
                <input
                  type="text"
                  value={editFolderPath}
                  onChange={(e) => setEditFolderPath(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
                />
                <div>
                  <div className="mb-1.5 text-xs font-medium text-ink-600">Color</div>
                  <FolderColorPicker value={editFolderColor} onChange={setEditFolderColor} />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleUpdate(folder.id)}
                    className="flex-1 px-3 py-1.5 text-sm bg-action text-white rounded-md hover:bg-action-hover"
                  >
                    Guardar
                  </button>
                  <button
                    onClick={() => {
                      setEditingId(null)
                      setError(null)
                    }}
                    className="flex-1 px-3 py-1.5 text-sm border border-ink-300 rounded-md hover:bg-ink-50"
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
                    <div className="flex items-center gap-2">
                      <span
                        className="h-3 w-3 flex-shrink-0 rounded-full"
                        style={{ backgroundColor: folder.color || DEFAULT_FOLDER_COLOR }}
                        aria-hidden
                      />
                      <div className="text-sm font-medium text-ink-900 truncate">
                        {folder.name}
                      </div>
                    </div>
                    {folder.path !== folder.name && (
                      <div className="text-xs text-ink-500 truncate">
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
                      className="px-2 py-1 text-xs text-accent hover:text-accent-ink hover:bg-accent-tint rounded"
                      title="Crear subcarpeta"
                    >
                      <Plus className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => handleStartEdit(folder)}
                      className="px-2 py-1 text-xs text-ink-600 hover:text-ink-900 hover:bg-ink-100 rounded"
                      title="Editar"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        setDeletingId(folder.id)
                        handleDelete(folder.id)
                      }}
                      className="px-2 py-1 text-xs text-danger hover:text-danger hover:bg-danger-bg rounded"
                      title="Eliminar"
                      disabled={deletingId === folder.id}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                {/* Mostrar subcarpetas si existen */}
                {(() => {
                  const subfolders = folders.filter(f => f.parent_id === folder.id)
                  const showSubfolders = subfolders.length > 0 || (isCreating && parentIdForNew === folder.id)
                  if (showSubfolders) {
                    return (
                      <div className="mt-2 ml-4 pl-3 border-l-2 border-ink-200">
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
        <p className="text-sm text-ink-500 text-center py-4">
          No hay carpetas {parentId ? 'en esta carpeta' : 'en la raíz'}. Hacé clic en &ldquo;+ Nueva Carpeta&rdquo; para crear la primera.
        </p>
      )}
    </div>
  )
}
