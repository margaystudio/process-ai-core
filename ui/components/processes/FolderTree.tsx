'use client'

import { useState, useEffect } from 'react'
import { Folder as FolderIcon, FileText, Plus, Pencil, Trash2, ChevronDown, ChevronRight, Check } from 'lucide-react'
import { listFolders, listDocuments, type Folder, type Document as DocumentType } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useFolderCrud } from '@/hooks/useFolderCrud'

interface FolderTreeProps {
  workspaceId: string
  selectedFolderId?: string
  onSelectFolder?: (folderId: string | null) => void
  showSelectable?: boolean
  showCrud?: boolean
  showDocuments?: boolean
  /** Si el padre ya cargó documentos, evita fetch duplicados a la API */
  allDocuments?: DocumentType[]
}

interface FolderNode {
  folder: Folder
  children: FolderNode[]
}

function buildTree(folders: Folder[]): FolderNode[] {
  const folderMap = new Map<string, FolderNode>()
  const roots: FolderNode[] = []

  // Primero crear todos los nodos
  folders.forEach(folder => {
    folderMap.set(folder.id, {
      folder,
      children: []
    })
  })

  // Luego construir el árbol
  folders.forEach(folder => {
    const node = folderMap.get(folder.id)!
    if (folder.parent_id && folderMap.has(folder.parent_id)) {
      const parent = folderMap.get(folder.parent_id)!
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  })

  // Ordenar por sort_order y nombre
  const sortNodes = (nodes: FolderNode[]) => {
    nodes.sort((a, b) => {
      if (a.folder.sort_order !== b.folder.sort_order) {
        return a.folder.sort_order - b.folder.sort_order
      }
      return a.folder.name.localeCompare(b.folder.name)
    })
    nodes.forEach(node => sortNodes(node.children))
  }
  sortNodes(roots)

  return roots
}

function FolderTreeNode({
  node,
  level = 0,
  selectedFolderId,
  onSelectFolder,
  workspaceId,
  documents,
  showDocuments = true,
  showCrud = false,
  onFoldersChange,
  skipPerFolderFetch = false,
}: {
  node: FolderNode
  level?: number
  selectedFolderId?: string
  onSelectFolder?: (folderId: string | null) => void
  workspaceId?: string
  documents?: DocumentType[]
  showDocuments?: boolean
  showCrud?: boolean
  onFoldersChange?: () => void
  skipPerFolderFetch?: boolean
}) {
  const { createFolder, renameFolder, deleteFolder: deleteFolderMutation } = useFolderCrud(workspaceId ?? '')

  const [isExpanded, setIsExpanded] = useState(level < 2) // Expandir primeros 2 niveles por defecto
  const [folderDocuments, setFolderDocuments] = useState<DocumentType[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [isCreatingSubfolder, setIsCreatingSubfolder] = useState(false)
  const [isSavingSubfolder, setIsSavingSubfolder] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [newSubfolderName, setNewSubfolderName] = useState('')
  const [editFolderName, setEditFolderName] = useState(node.folder.name)
  const [crudError, setCrudError] = useState<string | null>(null)

  const isSelected = selectedFolderId === node.folder.id
  const hasChildren = node.children.length > 0
  const folderDocs = documents?.filter(d => d.folder_id === node.folder.id) || []

  // Cargar documentos por carpeta solo si el padre no pasó la lista completa
  useEffect(() => {
    if (skipPerFolderFetch) return
    if (isExpanded && workspaceId && folderDocs.length === 0 && folderDocuments.length === 0) {
      setLoadingDocs(true)
      listDocuments(workspaceId, node.folder.id, 'process')
        .then(docs => {
          setFolderDocuments(docs)
        })
        .catch(() => {
          // Error silencioso: documentos simplemente no se muestran
        })
        .finally(() => {
          setLoadingDocs(false)
        })
    }
  }, [isExpanded, workspaceId, node.folder.id, folderDocs.length, folderDocuments.length, skipPerFolderFetch])

  const displayDocs = folderDocs.length > 0 ? folderDocs : folderDocuments
  const hasContent = hasChildren || displayDocs.length > 0

  const handleCreateSubfolder = async () => {
    if (isSavingSubfolder) return // evitar doble-submit (crea carpetas duplicadas)
    if (!newSubfolderName.trim() || !workspaceId) {
      setCrudError('El nombre es requerido')
      return
    }

    try {
      setIsSavingSubfolder(true)
      setCrudError(null)
      await createFolder({
        name: newSubfolderName.trim(),
        parentId: node.folder.id,
        sortOrder: node.children.length,
        allFolders: [], // el path se construye en el hook con el parentId
      })
      setNewSubfolderName('')
      setIsCreatingSubfolder(false)
      if (onFoldersChange) {
        onFoldersChange()
      }
    } catch (err) {
      setCrudError(err instanceof Error ? err.message : 'Error al crear subcarpeta')
    } finally {
      setIsSavingSubfolder(false)
    }
  }

  const handleUpdateFolder = async () => {
    if (!editFolderName.trim()) {
      setCrudError('El nombre es requerido')
      return
    }

    try {
      setCrudError(null)
      await renameFolder(node.folder.id, editFolderName.trim())
      setIsEditing(false)
      if (onFoldersChange) {
        onFoldersChange()
      }
    } catch (err) {
      setCrudError(err instanceof Error ? err.message : 'Error al actualizar carpeta')
    }
  }

  const handleDeleteFolder = async () => {
    if (!workspaceId) {
      setCrudError('Workspace ID es requerido')
      return
    }

    // Verificar si hay documentos en esta carpeta (hacer llamada a API para estar seguros)
    try {
      setCrudError(null)
      const docsInFolder = await listDocuments(workspaceId, node.folder.id, 'process')

      if (docsInFolder.length > 0) {
        setCrudError(`No se puede eliminar la carpeta "${node.folder.name}" porque contiene ${docsInFolder.length} documento(s). Por favor, eliminá o mové los documentos primero.`)
        return
      }

      // Verificar si hay subcarpetas con documentos (recursivamente)
      const checkSubfoldersForDocs = async (childNode: FolderNode): Promise<boolean> => {
        const childDocs = await listDocuments(workspaceId, childNode.folder.id, 'process').catch(() => [])
        if (childDocs.length > 0) return true
        // Verificar recursivamente en los hijos
        for (const child of childNode.children) {
          if (await checkSubfoldersForDocs(child)) {
            return true
          }
        }
        return false
      }

      // Verificar todas las subcarpetas
      for (const child of node.children) {
        if (await checkSubfoldersForDocs(child)) {
          setCrudError(`No se puede eliminar la carpeta "${node.folder.name}" porque contiene subcarpetas con documentos. Por favor, eliminá o mové los documentos primero.`)
          return
        }
      }

      if (!confirm(`¿Estás seguro de eliminar la carpeta "${node.folder.name}"?`)) {
        return
      }

      await deleteFolderMutation(node.folder.id)
      if (onFoldersChange) {
        onFoldersChange()
      }
    } catch (err) {
      setCrudError(err instanceof Error ? err.message : 'Error al eliminar carpeta')
    }
  }

  return (
    <div className="select-none">
      <div
        className={`
          flex items-center gap-2 py-1.5 px-2 rounded-md
          ${isSelected
            ? 'bg-accent-tint text-accent-ink font-medium'
            : 'hover:bg-ink-100 text-ink-700'
          }
        `}
        style={{ paddingLeft: `${level * 1.5 + 0.5}rem` }}
      >
        {hasContent ? (
          <span
            className="text-ink-400 text-xs w-4 cursor-pointer"
            onClick={(e) => {
              e.stopPropagation()
              setIsExpanded(!isExpanded)
            }}
          >
            {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        ) : (
          <span className="w-4" />
        )}
        <span
          className="text-ink-500 text-sm mr-1 cursor-pointer flex-1 flex items-center gap-2"
          onClick={() => {
            if (onSelectFolder) {
              onSelectFolder(isSelected ? null : node.folder.id)
            }
          }}
        >
          <FolderIcon className="h-4 w-4" />
          <span className="text-sm flex-1">
            {isEditing ? (
              <input
                type="text"
                value={editFolderName}
                onChange={(e) => setEditFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleUpdateFolder()
                  } else if (e.key === 'Escape') {
                    setIsEditing(false)
                    setEditFolderName(node.folder.name)
                  }
                }}
                onClick={(e) => e.stopPropagation()}
                className="px-2 py-1 text-sm border border-accent rounded focus:outline-none focus:ring-1 focus:ring-action-ring"
                autoFocus
              />
            ) : (
              node.folder.name
            )}
          </span>
        </span>
        {displayDocs.length > 0 && (
          <span className="text-xs text-ink-500">({displayDocs.length})</span>
        )}
        {isSelected && (
          <Check className="h-3.5 w-3.5 text-accent" />
        )}
        {showCrud && !isEditing && (
          <div className="flex items-center gap-1 ml-2" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setIsCreatingSubfolder(true)
                setNewSubfolderName('')
                setCrudError(null)
              }}
              className="px-1.5 py-0.5 text-xs text-accent hover:text-accent-ink hover:bg-accent-tint rounded"
              title="Crear subcarpeta"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setIsEditing(true)
                setEditFolderName(node.folder.name)
                setCrudError(null)
              }}
              className="px-1.5 py-0.5 text-xs text-ink-600 hover:text-ink-800 hover:bg-ink-100 rounded"
              title="Renombrar"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleDeleteFolder()
              }}
              className="px-1.5 py-0.5 text-xs text-danger hover:text-danger hover:bg-danger-bg rounded"
              title="Eliminar"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
      {crudError && (
        <div className="text-xs text-danger px-2 py-1" style={{ paddingLeft: `${level * 1.5 + 0.5}rem` }}>
          {crudError}
        </div>
      )}
      {isCreatingSubfolder && (
        <div className="px-2 py-2 bg-ink-50 border border-ink-200 rounded-md mx-2 my-1" style={{ marginLeft: `${(level + 1) * 1.5 + 0.5}rem` }}>
          <input
            type="text"
            value={newSubfolderName}
            onChange={(e) => setNewSubfolderName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleCreateSubfolder()
              } else if (e.key === 'Escape') {
                setIsCreatingSubfolder(false)
                setNewSubfolderName('')
              }
            }}
            placeholder="Nombre de la subcarpeta"
            className="w-full px-2 py-1 text-xs border border-ink-300 rounded focus:outline-none focus:ring-1 focus:ring-action-ring"
            autoFocus
          />
          <div className="flex gap-1 mt-1">
            <button
              onClick={handleCreateSubfolder}
              disabled={isSavingSubfolder}
              className="flex-1 px-2 py-1 text-xs bg-action text-white rounded hover:bg-action-hover disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSavingSubfolder ? 'Creando...' : 'Crear'}
            </button>
            <button
              onClick={() => {
                setIsCreatingSubfolder(false)
                setNewSubfolderName('')
                setCrudError(null)
              }}
              className="flex-1 px-2 py-1 text-xs border border-ink-300 rounded hover:bg-ink-50"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
      {isExpanded && (
        <div>
          {/* Subcarpetas */}
          {node.children.map(child => (
            <FolderTreeNode
              key={child.folder.id}
              node={child}
              level={level + 1}
              selectedFolderId={selectedFolderId}
              onSelectFolder={onSelectFolder}
              workspaceId={workspaceId}
              documents={documents}
              showDocuments={showDocuments}
              showCrud={showCrud}
              onFoldersChange={onFoldersChange}
              skipPerFolderFetch={skipPerFolderFetch}
            />
          ))}
          {/* Documentos dentro de esta carpeta (solo si showDocuments es true) */}
          {showDocuments && (
            <>
              {loadingDocs ? (
                <div className="text-xs text-ink-400 px-2 py-1" style={{ paddingLeft: `${(level + 1) * 1.5 + 0.5}rem` }}>
                  Cargando...
                </div>
              ) : displayDocs.length > 0 ? (
                displayDocs.map(doc => (
                  <a
                    key={doc.id}
                    href={`/documents/${doc.id}`}
                    className="flex items-center gap-2 py-1 px-2 text-xs text-ink-600 hover:bg-ink-50 hover:text-accent cursor-pointer"
                    style={{ paddingLeft: `${(level + 1) * 1.5 + 0.5}rem` }}
                    title={doc.description || doc.name}
                  >
                    <FileText className="h-4 w-4" />
                    <span className="flex-1 truncate">{doc.name}</span>
                  </a>
                ))
              ) : null}
            </>
          )}
          {/* Si showDocuments es false, mostrar documentos grisados y no clickeables */}
          {!showDocuments && displayDocs.length > 0 && (
            displayDocs.map(doc => (
              <div
                key={doc.id}
                className="flex items-center gap-2 py-1 px-2 text-xs text-ink-400 cursor-default"
                style={{ paddingLeft: `${(level + 1) * 1.5 + 0.5}rem` }}
                title={doc.description || doc.name}
                onClick={(e) => e.stopPropagation()}
              >
                <FileText className="h-4 w-4" />
                <span className="flex-1 truncate">{doc.name}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function FolderTree({
  workspaceId,
  selectedFolderId,
  onSelectFolder,
  showSelectable = true,
  showCrud = false,
  showDocuments = true,
  allDocuments,
}: FolderTreeProps) {
  const { activeTenantId } = useWorkspace()
  const [folders, setFolders] = useState<Folder[]>([])
  const [documents, setDocuments] = useState<DocumentType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadFolders = async () => {
    if (!workspaceId) {
      setLoading(false)
      setFolders([])
      setDocuments([])
      return
    }

    try {
      setLoading(true)
      setError(null)
      const foldersData = await listFolders(workspaceId)
      setFolders(foldersData)
      if (allDocuments !== undefined) {
        setDocuments(allDocuments)
      } else {
        const docsData = await listDocuments(workspaceId, undefined, 'process').catch(() => [])
        setDocuments(docsData)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setFolders([])
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setFolders([])
    if (allDocuments === undefined) {
      setDocuments([])
    }
    loadFolders()
  }, [workspaceId, activeTenantId])

  useEffect(() => {
    if (allDocuments !== undefined) {
      setDocuments(allDocuments)
    }
  }, [allDocuments])

  if (!workspaceId) {
    return (
      <div className="p-4 bg-ink-50 rounded-lg border border-ink-200">
        <p className="text-sm text-ink-500">Seleccioná un espacio de trabajo para ver las carpetas</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-4 bg-ink-50 rounded-lg border border-ink-200">
        <div className="animate-pulse text-sm text-ink-500">Cargando estructura de carpetas...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 bg-danger-bg rounded-lg border border-danger-bd">
        <p className="text-sm text-danger">Error: {error}</p>
      </div>
    )
  }

  const tree = folders.length > 0 ? buildTree(folders) : []

  return (
    <div className="bg-white rounded-lg border border-ink-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-900">
          {showCrud ? 'Gestión de Carpetas' : 'Estructura de Carpetas'}
        </h3>
        {selectedFolderId && showSelectable && !showCrud && (
          <button
            onClick={() => onSelectFolder?.(null)}
            className="text-xs text-ink-500 hover:text-ink-700"
          >
            Limpiar selección
          </button>
        )}
      </div>


      {folders.length === 0 ? (
        <div className="p-4 bg-ink-50 rounded-md">
          <p className="text-sm text-ink-500 text-center">
            No hay carpetas en este espacio de trabajo
          </p>
        </div>
      ) : (
        <>
          <div className="max-h-96 overflow-y-auto">
            {tree.map(node => (
              <FolderTreeNode
                key={node.folder.id}
                node={node}
                selectedFolderId={selectedFolderId}
                onSelectFolder={showSelectable ? (id) => onSelectFolder?.(id || '') : undefined}
                workspaceId={workspaceId}
                documents={documents}
                showDocuments={showDocuments}
                showCrud={showCrud}
                onFoldersChange={loadFolders}
                skipPerFolderFetch={true}
              />
            ))}
            {/* Documentos sin carpeta */}
            {documents.filter(d => !d.folder_id).length > 0 && (
              <div className="mt-2 pt-2 border-t border-ink-200">
                <div className="text-xs text-ink-500 px-2 py-1 mb-1">Sin carpeta</div>
                {documents.filter(d => !d.folder_id).map(doc => (
                  showDocuments ? (
                    <a
                      key={doc.id}
                      href={`/documents/${doc.id}`}
                      className="flex items-center gap-2 py-1 px-2 text-xs text-ink-600 hover:bg-ink-50 hover:text-accent cursor-pointer"
                      style={{ paddingLeft: '0.5rem' }}
                      title={doc.description || doc.name}
                    >
                      <FileText className="h-4 w-4" />
                      <span className="flex-1 truncate">{doc.name}</span>
                    </a>
                  ) : (
                    <div
                      key={doc.id}
                      className="flex items-center gap-2 py-1 px-2 text-xs text-ink-400 cursor-default"
                      style={{ paddingLeft: '0.5rem' }}
                      title={doc.description || doc.name}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <FileText className="h-4 w-4" />
                      <span className="flex-1 truncate">{doc.name}</span>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
          {selectedFolderId && showSelectable && (
            <div className="mt-3 pt-3 border-t border-ink-200">
              <p className="text-xs text-ink-600">
                <span className="font-medium">Ubicación seleccionada:</span>{' '}
                {folders.find(f => f.id === selectedFolderId)?.path ||
                 folders.find(f => f.id === selectedFolderId)?.name}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
