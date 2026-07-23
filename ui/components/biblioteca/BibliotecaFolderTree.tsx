'use client'

import { useState, useEffect } from 'react'
import { ChevronRight, BookOpen } from 'lucide-react'
import { listFolders, Folder, Document as DocType } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

// Paths SVG de íconos de carpeta (feather-style, igual al prototipo)
const FOLDER_ICON_PATHS: Record<string, string> = {
  flow:     'M5 3h6v6H5zM13 15h6v6h-6zM8 9v3a3 3 0 0 0 3 3h2',
  shield:   'M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z',
  box:      'M21 8l-9-5-9 5 9 5 9-5zM3 8v8l9 5 9-5V8',
  contract: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h4',
  folder:   'M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-7l-2-2H5a2 2 0 0 0-2 2z',
  chart:    'M3 3v18h18M7 14l4-4 3 3 5-6',
}

interface FolderNode {
  folder: Folder
  children: FolderNode[]
  docCount: number
}

function buildTree(folders: Folder[], docs: DocType[]): FolderNode[] {
  const countMap = new Map<string, number>()
  docs.forEach((d) => {
    if (d.folder_id) {
      countMap.set(d.folder_id, (countMap.get(d.folder_id) ?? 0) + 1)
    }
  })

  const nodeMap = new Map<string, FolderNode>()
  const roots: FolderNode[] = []

  folders.forEach((f) => {
    nodeMap.set(f.id, { folder: f, children: [], docCount: countMap.get(f.id) ?? 0 })
  })

  folders.forEach((f) => {
    const node = nodeMap.get(f.id)!
    if (f.parent_id && nodeMap.has(f.parent_id)) {
      nodeMap.get(f.parent_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  })

  const sort = (nodes: FolderNode[]) => {
    nodes.sort((a, b) => {
      if (a.folder.sort_order !== b.folder.sort_order)
        return a.folder.sort_order - b.folder.sort_order
      return a.folder.name.localeCompare(b.folder.name)
    })
    nodes.forEach((n) => sort(n.children))
  }
  sort(roots)
  return roots
}

// Mini SVG icon (feather-style path)
function FolderSvg({ d, size = 14, color }: { d: string; size?: number; color: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {d.split('M').filter(Boolean).map((seg, i) => (
        <path key={i} d={'M' + seg} />
      ))}
    </svg>
  )
}

function FolderRow({
  node,
  depth,
  selectedId,
  onSelect,
}: {
  node: FolderNode
  depth: number
  selectedId: string | null
  onSelect: (id: string | null) => void
}) {
  const [open, setOpen] = useState(depth < 1)
  const hasKids = node.children.length > 0
  const sel = selectedId === node.folder.id
  const folderColor = node.folder.color || 'var(--indigo)'

  return (
    <>
      <div
        className="flex w-full items-center gap-px"
        style={{ paddingLeft: depth * 14 }}
      >
        {/* chevron expand/collapse */}
        <button
          type="button"
          aria-label={open ? 'Colapsar carpeta' : 'Expandir carpeta'}
          onClick={() => hasKids && setOpen((v) => !v)}
          className={
            'grid h-7 w-[18px] flex-shrink-0 place-items-center transition-transform ' +
            (hasKids ? 'cursor-pointer' : 'pointer-events-none opacity-0')
          }
          style={{ transform: `rotate(${open ? 90 : 0}deg)` }}
          tabIndex={hasKids ? 0 : -1}
        >
          <ChevronRight
            size={11}
            className="text-ink-400"
            strokeWidth={2.6}
            aria-hidden="true"
          />
        </button>

        {/* folder row button */}
        <button
          type="button"
          onClick={() => onSelect(sel ? null : node.folder.id)}
          className={
            'flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-[7px] text-[12.5px] ' +
            (sel
              ? 'bg-indigo-tint font-bold text-ink-800'
              : 'font-semibold text-ink-700 hover:bg-surface-hover')
          }
        >
          <span className="flex-shrink-0" style={{ color: folderColor }}>
            <FolderSvg d={FOLDER_ICON_PATHS.folder} size={14} color={folderColor} />
          </span>
          <span className="min-w-0 flex-1 truncate text-left">{node.folder.name}</span>
          {node.docCount > 0 && (
            <span className="flex-shrink-0 text-[10.5px] font-bold text-ink-300">
              {node.docCount}
            </span>
          )}
        </button>
      </div>

      {open &&
        node.children.map((child) => (
          <FolderRow
            key={child.folder.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ))}
    </>
  )
}

interface Props {
  workspaceId: string
  selectedFolderId: string | null
  onSelect: (id: string | null) => void
  allDocuments: DocType[]
  totalCount: number
  /** Callback para que el padre conozca la lista plana de folders cargados */
  onFoldersLoaded?: (folders: Folder[]) => void
}

export default function BibliotecaFolderTree({
  workspaceId,
  selectedFolderId,
  onSelect,
  allDocuments,
  totalCount,
  onFoldersLoaded,
}: Props) {
  const { activeTenantId } = useWorkspace()
  const [folders, setFolders] = useState<Folder[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!workspaceId) {
      setLoading(false)
      return
    }
    setLoading(true)
    listFolders(workspaceId)
      .then((data) => {
        setFolders(data)
        onFoldersLoaded?.(data)
      })
      .catch(() => {
        setFolders([])
        onFoldersLoaded?.([])
      })
      .finally(() => setLoading(false))
    // onFoldersLoaded: en el único caller (app/workspace/page.tsx) es un setState
    // (setAllFolders) — identidad estable, agregarla no cambia cuándo corre esto.
  }, [workspaceId, activeTenantId, onFoldersLoaded])

  const tree = buildTree(folders, allDocuments)

  return (
    <div className="sticky top-0 max-h-screen w-[228px] flex-shrink-0 self-start overflow-y-auto border-r border-line bg-surface p-3 pt-[22px]">
      <div className="px-2 pb-3.5 text-[11px] font-bold uppercase tracking-[.08em] text-ink-400">
        Estructura
      </div>

      {/* Biblioteca completa */}
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={
          'mb-1 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] ' +
          (selectedFolderId === null
            ? 'bg-indigo-tint font-bold text-ink-800'
            : 'font-semibold text-ink-700 hover:bg-surface-hover')
        }
      >
        <BookOpen size={15} aria-hidden="true" />
        <span className="flex-1 text-left">Biblioteca completa</span>
        <span className="text-[10.5px] font-bold text-ink-300">{totalCount}</span>
      </button>

      {loading ? (
        <div className="space-y-2 px-2 pt-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-7 animate-pulse rounded-lg bg-ink-100" />
          ))}
        </div>
      ) : (
        tree.map((node) => (
          <FolderRow
            key={node.folder.id}
            node={node}
            depth={0}
            selectedId={selectedFolderId}
            onSelect={onSelect}
          />
        ))
      )}
    </div>
  )
}
