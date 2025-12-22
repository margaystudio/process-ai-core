'use client'

import { useState, useEffect } from 'react'
import { listFolders, listDocuments, createFolder, updateFolder, deleteFolder, Folder, Document as DocumentType } from '@/lib/api'
import FolderCrud from './FolderCrud'

interface FolderTreeProps {
  workspaceId: string
  selectedFolderId?: string
  onSelectFolder?: (folderId: string | null) => void
  showSelectable?: boolean
  showCrud?: boolean
  showDocuments?: boolean // Controla si se muestran los documentos dentro de las carpetas
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
}) {
  const [isExpanded, setIsExpanded] = useState(level < 2) // Expandir primeros 2 niveles por defecto
  const [folderDocuments, setFolderDocuments] = useState<DocumentType[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [isCreatingSubfolder, setIsCreatingSubfolder] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [newSubfolderName, setNewSubfolderName] = useState('')
  const [editFolderName, setEditFolderName] = useState(node.folder.name)
  const [crudError, setCrudError] = useState<string | null>(null)
  
  const isSelected = selectedFolderId === node.folder.id
  const hasChildren = node.children.length > 0
  const folderDocs = documents?.filter(d => d.folder_id === node.folder.id) || []

  // Cargar documentos cuando se expande (solo si no están ya cargados)
  useEffect(() => {
    if (isExpanded && workspaceId && folderDocs.length === 0 && folderDocuments.length === 0) {
      setLoadingDocs(true)
      listDocuments(workspaceId, node.folder.id, 'process')
        .then(docs => {
          setFolderDocuments(docs)
        })
        .catch(err => {
          console.error('Error cargando documentos:', err)
        })
        .finally(() => {
          setLoadingDocs(false)
        })
    }
  }, [isExpanded, workspaceId, node.folder.id, folderDocs.length, folderDocuments.length])

  const displayDocs = folderDocs.length > 0 ? folderDocs : folderDocuments
  const hasContent = hasChildren || displayDocs.length > 0

  const handleCreateSubfolder = async () => {
    if (!newSubfolderName.trim() || !workspaceId) {
      setCrudError('El nombre es requerido')
      return
    }

    try {
      setCrudError(null)
      const parentPath = node.folder.path || node.folder.name
      await createFolder({
        workspace_id: workspaceId,
        name: newSubfolderName.trim(),
        path: `${parentPath}/${newSubfolderName.trim()}`,
        parent_id: node.folder.id,
        sort_order: node.children.length,
      })
      setNewSubfolderName('')
      setIsCreatingSubfolder(false)
      if (onFoldersChange) {
        onFoldersChange()
      }
    } catch (err) {
      setCrudError(err instanceof Error ? err.message : 'Error al crear subcarpeta')
    }
  }

  const handleUpdateFolder = async () => {
    if (!editFolderName.trim()) {
      setCrudError('El nombre es requerido')
      return
    }

    try {
      setCrudError(null)
      await updateFolder(node.folder.id, {
        name: editFolderName.trim(),
      })
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
        setCrudError(`No se puede eliminar la carpeta "${node.folder.name}" porque contiene ${docsInFolder.length} documento(s). Por favor, elimina o mueve los documentos primero.`)
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
          setCrudError(`No se puede eliminar la carpeta "${node.folder.name}" porque contiene subcarpetas con documentos. Por favor, elimina o mueve los documentos primero.`)
          return
        }
      }

      if (!confirm(`¿Estás seguro de eliminar la carpeta "${node.folder.name}"?`)) {
        return
      }

      await deleteFolder(node.folder.id)
      if (onFoldersChange) {
        onFoldersChange()
      }
    } catch (err) {
      // Si el error es del backend sobre documentos, mostrarlo
      const errorMessage = err instanceof Error ? err.message : 'Error al eliminar carpeta'
      if (errorMessage.includes('documento') || errorMessage.includes('subcarpeta')) {
        setCrudError(errorMessage)
      } else {
        setCrudError(errorMessage)
      }
    }
  }

  return (
    <div className="select-none">
      <div
        className={`
          flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer
          ${isSelected 
            ? 'bg-blue-100 text-blue-900 font-medium' 
            : 'hover:bg-gray-100 text-gray-700'
          }
        `}
        style={{ paddingLeft: `${level * 1.5 + 0.5}rem` }}
        onClick={() => {
          if (hasContent) {
            setIsExpanded(!isExpanded)
          }
          if (onSelectFolder) {
            onSelectFolder(isSelected ? null : node.folder.id)
          }
        }}
      >
        {hasContent ? (
          <span className="text-gray-400 text-xs w-4">
            {isExpanded ? '▼' : '▶'}
          </span>
        ) : (
          <span className="w-4" />
        )}
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
              className="px-2 py-1 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          ) : (
            node.folder.name
          )}
        </span>
        {displayDocs.length > 0 && (
          <span className="text-xs text-gray-500">({displayDocs.length})</span>
        )}
        {isSelected && (
          <span className="text-xs text-blue-600">✓</span>
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
              className="px-1.5 py-0.5 text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
              title="Crear subcarpeta"
            >
              ➕
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setIsEditing(true)
                setEditFolderName(node.folder.name)
                setCrudError(null)
              }}
              className="px-1.5 py-0.5 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded"
              title="Renombrar"
            >
              ✏️
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleDeleteFolder()
              }}
              className="px-1.5 py-0.5 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded"
              title="Eliminar"
            >
              🗑️
            </button>
          </div>
        )}
      </div>
      {crudError && (
        <div className="text-xs text-red-600 px-2 py-1" style={{ paddingLeft: `${level * 1.5 + 0.5}rem` }}>
          {crudError}
        </div>
      )}
      {isCreatingSubfolder && (
        <div className="px-2 py-2 bg-gray-50 border border-gray-200 rounded-md mx-2 my-1" style={{ marginLeft: `${(level + 1) * 1.5 + 0.5}rem` }}>
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
            className="w-full px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            autoFocus
          />
          <div className="flex gap-1 mt-1">
            <button
              onClick={handleCreateSubfolder}
              className="flex-1 px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Crear
            </button>
            <button
              onClick={() => {
                setIsCreatingSubfolder(false)
                setNewSubfolderName('')
                setCrudError(null)
              }}
              className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50"
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
            />
          ))}
          {/* Documentos dentro de esta carpeta (solo si showDocuments es true) */}
          {showDocuments && (
            <>
              {loadingDocs ? (
                <div className="text-xs text-gray-400 px-2 py-1" style={{ paddingLeft: `${(level + 1) * 1.5 + 0.5}rem` }}>
                  Cargando...
                </div>
              ) : displayDocs.length > 0 ? (
                displayDocs.map(doc => (
                  <a
                    key={doc.id}
                    href={`/documents/${doc.id}`}
                    className="flex items-center gap-2 py-1 px-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-blue-600 cursor-pointer"
                    style={{ paddingLeft: `${(level + 1) * 1.5 + 0.5}rem` }}
                    title={doc.description || doc.name}
                  >
                    <span className="w-4">📄</span>
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
                className="flex items-center gap-2 py-1 px-2 text-xs text-gray-400 cursor-default"
                style={{ paddingLeft: `${(level + 1) * 1.5 + 0.5}rem` }}
                title={doc.description || doc.name}
                onClick={(e) => e.stopPropagation()}
              >
                <span className="w-4">📄</span>
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
  showDocuments = true
}: FolderTreeProps) {
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
      console.log('Cargando carpetas para workspace:', workspaceId)
      const [foldersData, docsData] = await Promise.all([
        listFolders(workspaceId),
        listDocuments(workspaceId, undefined, 'process').catch(() => [])
      ])
      console.log('Carpetas cargadas:', foldersData)
      console.log('Documentos cargados:', docsData)
      setFolders(foldersData)
      setDocuments(docsData)
    } catch (err) {
      console.error('Error cargando carpetas:', err)
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setFolders([])
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFolders()
  }, [workspaceId])

  if (!workspaceId) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-sm text-gray-500">Seleccioná un workspace para ver las carpetas</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
        <div className="animate-pulse text-sm text-gray-500">Cargando estructura de carpetas...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 rounded-lg border border-red-200">
        <p className="text-sm text-red-700">Error: {error}</p>
      </div>
    )
  }

  const tree = folders.length > 0 ? buildTree(folders) : []

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900">
          {showCrud ? 'Gestión de Carpetas' : 'Estructura de Carpetas'}
        </h3>
        {selectedFolderId && showSelectable && !showCrud && (
          <button
            onClick={() => onSelectFolder?.(null)}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            Limpiar selección
          </button>
        )}
      </div>


      {folders.length === 0 ? (
        <div className="p-4 bg-gray-50 rounded-md">
          <p className="text-sm text-gray-500 text-center">
            Cargando estructura de carpetas...
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
              />
            ))}
            {/* Documentos sin carpeta */}
            {documents.filter(d => !d.folder_id).length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-200">
                <div className="text-xs text-gray-500 px-2 py-1 mb-1">Sin carpeta</div>
                {documents.filter(d => !d.folder_id).map(doc => (
                  showDocuments ? (
                    <a
                      key={doc.id}
                      href={`/documents/${doc.id}`}
                      className="flex items-center gap-2 py-1 px-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-blue-600 cursor-pointer"
                      style={{ paddingLeft: '0.5rem' }}
                      title={doc.description || doc.name}
                    >
                      <span className="w-4">📄</span>
                      <span className="flex-1 truncate">{doc.name}</span>
                    </a>
                  ) : (
                    <div
                      key={doc.id}
                      className="flex items-center gap-2 py-1 px-2 text-xs text-gray-400 cursor-default"
                      style={{ paddingLeft: '0.5rem' }}
                      title={doc.description || doc.name}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span className="w-4">📄</span>
                      <span className="flex-1 truncate">{doc.name}</span>
                    </div>
                  )
                ))}
              </div>
            )}
          </div>
          {selectedFolderId && showSelectable && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-xs text-gray-600">
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

