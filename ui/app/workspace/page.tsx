'use client'

import { useState, useEffect, useLayoutEffect, useMemo, useCallback, useRef, memo } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Search, Plus, Upload, ChevronDown, X } from 'lucide-react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import {
  listDocuments,
  getDocumentTypes,
  deleteDocument,
  updateDocument,
  Document,
  Folder,
  CatalogOption,
} from '@/lib/api'
import { useCanEditWorkspace, useCanManageWorkspace, useHasPermission } from '@/hooks/useHasPermission'
import { useWorkspaceProfileIncomplete } from '@/hooks/useWorkspaceProfileIncomplete'
import WorkspaceProfileBanner from '@/components/workspace/WorkspaceProfileBanner'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import ArtifactViewerModal from '@/components/processes/ArtifactViewerModal'
import BibliotecaFolderTree from '@/components/biblioteca/BibliotecaFolderTree'
import { RowSkeleton } from '@/components/layout/ListSkeleton'
import { StatusBadge, VersionPill, ESTADO_LABEL, Chip, Dialog } from '@/shared/ui/components'
import type { DocumentEstado } from '@/shared/ui/components'

// ---- Tipos ----
type TabView = 'lista' | 'recientes' | 'pendientes'

const ESTADOS = ['Todos', 'Aprobado', 'Pendiente', 'Borrador', 'Archivado'] as const
type EstadoFilter = (typeof ESTADOS)[number]

// ---- Helpers ----

/** Convierte el status de API al nombre visible */
function toEstado(status: string): DocumentEstado {
  return ESTADO_LABEL[status] ?? 'Borrador'
}

/** Etiqueta de versión inline según estado y número de versión real */
function versionLabel(status: string, versionNumber?: number | null): string {
  const e = toEstado(status)
  switch (e) {
    case 'Aprobado':
      return versionNumber != null ? `v${versionNumber} · Oficial` : 'v1 · Oficial'
    case 'Pendiente':
      return 'En revisión'
    case 'Archivado':
      return 'Archivado'
    default:
      return 'Sin versión aún'
  }
}

/** Tiempo relativo simplificado */
function relDate(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 2) return 'recién'
  if (mins < 60) return `hace ${mins} min`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `hace ${hours} h`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'ayer'
  if (days < 7) return `hace ${days} días`
  return new Date(iso).toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })
}

/**
 * Calcula el set de IDs de una carpeta + todos sus descendientes.
 * Usa la lista plana de folders (cada uno tiene parent_id).
 */
function getDescendantIds(folderId: string, allFolders: Folder[]): Set<string> {
  const result = new Set<string>([folderId])
  // BFS / iterativo para evitar recursión profunda
  const queue = [folderId]
  while (queue.length > 0) {
    const current = queue.shift()!
    allFolders
      .filter((f) => f.parent_id === current)
      .forEach((f) => {
        if (!result.has(f.id)) {
          result.add(f.id)
          queue.push(f.id)
        }
      })
  }
  return result
}

// ---- Íconos SVG inline (feather-style, del prototipo) ----
function SvgIcon({
  d,
  size = 16,
  className = '',
  strokeWidth = 2,
}: {
  d: string
  size?: number
  className?: string
  strokeWidth?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {d.split('M').filter(Boolean).map((seg, i) => (
        <path key={i} d={'M' + seg} />
      ))}
    </svg>
  )
}

const ICON = {
  doc:    'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6',
  dots:   'M12 5m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0M12 19m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0',
  plus:   'M12 5v14M5 12h14',
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
  folder: 'M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-7l-2-2H5a2 2 0 0 0-2 2z',
  ia:     'M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0',
}

// ---- Dropdown de Tipo documental ----
function TipoDocumentalFilter({
  value,
  onChange,
  options,
}: {
  value: string | null
  onChange: (v: string | null) => void
  options: CatalogOption[]
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const activeLabel = options.find((o) => o.value === value)?.label ?? 'Tipo documental'
  const isActive = value !== null

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={
          'inline-flex h-[30px] items-center gap-1.5 rounded-lg border px-2.5 text-[11.5px] font-semibold transition-colors ' +
          (isActive
            ? 'border-indigo-light bg-indigo-tint text-indigo'
            : 'border-line bg-surface text-ink-500 hover:bg-surface-hover')
        }
      >
        {activeLabel}
        {isActive ? (
          <button
            type="button"
            aria-label="Limpiar filtro de tipo"
            onClick={(e) => { e.stopPropagation(); onChange(null) }}
            className="ml-0.5 text-indigo hover:text-ink-800"
          >
            <X size={11} aria-hidden="true" />
          </button>
        ) : (
          <ChevronDown size={11} className="text-ink-300" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div
          role="listbox"
          aria-label="Tipo de documento"
          className="absolute left-0 z-30 mt-1 min-w-[180px] rounded-[11px] border border-line bg-surface p-1 shadow-menu"
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="option"
              aria-selected={value === o.value}
              onClick={() => { onChange(o.value === value ? null : o.value); setOpen(false) }}
              className={
                'w-full rounded-md px-2.5 py-2 text-left text-[12.5px] font-semibold ' +
                (value === o.value
                  ? 'bg-indigo-tint text-indigo'
                  : 'text-ink-800 hover:bg-surface-hover')
              }
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- Menú contextual por fila ----
/**
 * Acciones disponibles gateadas por permiso EFECTIVO (fail-closed: si el hook
 * de capacidades no cargó, no se muestra la acción — nunca mostramos algo que
 * el backend va a rechazar con 403).
 *
 * Archivar/Desarchivar usa el `status` CRUDO del documento (draft/archived),
 * no la etiqueta en español: "rejected" también se muestra como "Borrador"
 * (ver ESTADO_LABEL) pero el backend sólo permite la transición manual
 * archived ↔ draft. Gatear por la etiqueta habría mostrado "Archivar" en un
 * documento rechazado y el backend lo hubiera rechazado con 400.
 */
function RowMenu({
  doc,
  canDelete,
  canEdit,
  onClose,
  onOpen,
  onViewHistory,
  onCopyLink,
  onArchiveToggle,
  onDeleteRequest,
}: {
  doc: Document
  canDelete: boolean
  canEdit: boolean
  onClose: () => void
  onOpen: () => void
  onViewHistory: () => void
  onCopyLink: () => void
  onArchiveToggle: () => void
  onDeleteRequest: () => void
}) {
  const e = toEstado(doc.status)
  const canArchive = canEdit && doc.status === 'draft'
  const canUnarchive = canEdit && doc.status === 'archived'
  // Regla actual (sin cambios): eliminar solo se ofrece para borradores.
  const canDeleteItem = canDelete && e === 'Borrador'

  const groups: { label: string; danger?: boolean; action: () => void }[][] = [
    [
      { label: 'Abrir documento', action: onOpen },
      { label: 'Ver historial', action: onViewHistory },
    ],
    [
      { label: 'Copiar enlace', action: onCopyLink },
    ],
    [
      ...(canArchive ? [{ label: 'Archivar', action: onArchiveToggle }] : []),
      ...(canUnarchive ? [{ label: 'Desarchivar', action: onArchiveToggle }] : []),
      ...(canDeleteItem ? [{ label: 'Eliminar', danger: true, action: onDeleteRequest }] : []),
    ],
  ].filter((g) => g.length > 0)

  const panelRef = useRef<HTMLDivElement>(null)
  const [placement, setPlacement] = useState<'down' | 'up'>('down')

  // Medir contra el viewport ANTES del paint: si no entra hacia abajo, se abre
  // hacia arriba (evita que el menú de las últimas filas quede fuera de pantalla).
  useLayoutEffect(() => {
    const el = panelRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    if (rect.bottom > window.innerHeight - 8) {
      setPlacement('up')
    }
  }, [])

  return (
    <div
      ref={panelRef}
      role="menu"
      aria-label="Más opciones del documento"
      className={
        'absolute right-3.5 z-20 w-[212px] rounded-[11px] border border-line bg-surface p-1.5 shadow-menu ' +
        (placement === 'up' ? 'bottom-[calc(100%-4px)]' : 'top-[calc(100%-4px)]')
      }
    >
      {groups.map((g, gi) => (
        <div key={gi}>
          {gi > 0 && <div className="mx-2 my-[5px] h-px bg-line-soft" />}
          {g.map((a) => (
            <button
              key={a.label}
              type="button"
              role="menuitem"
              onClick={() => { a.action(); onClose() }}
              className={
                'w-full rounded-md px-2.5 py-2 text-left text-[12.5px] font-semibold ' +
                (a.danger ? 'text-danger hover:bg-danger-bg' : 'text-ink-800 hover:bg-surface-hover')
              }
            >
              {a.label}
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}

// ---- Empty state ----
function EmptyState({ canCreate }: { canCreate: boolean }) {
  return (
    <div className="rounded-2xl border-[1.5px] border-dashed border-line-input bg-surface-hover px-6 py-[54px] text-center">
      <span className="mx-auto mb-3.5 grid h-[54px] w-[54px] place-items-center rounded-2xl border border-line bg-surface text-ink-300">
        <SvgIcon d={ICON.folder} size={26} strokeWidth={1.6} />
      </span>
      <div className="mb-1 text-[15px] font-extrabold text-ink-800">
        Esta carpeta todavía no tiene documentos
      </div>
      <div className="mb-5 text-[13px] text-ink-400">
        Creá conocimiento desde cero o incorporá documentación existente.
      </div>
      {canCreate && (
        <div className="flex items-center justify-center gap-2.5">
          <Link
            href="/documents/new"
            className="inline-flex h-[42px] items-center gap-2 rounded-[10px] bg-ink-800 px-[18px] text-[13.5px] font-bold text-white hover:bg-ink-900"
          >
            <SvgIcon d={ICON.plus} size={16} />
            Crear documento
          </Link>
          <Link
            href="/import"
            className="inline-flex h-[42px] items-center gap-2 rounded-[10px] border border-line-input bg-surface px-[18px] text-[13.5px] font-bold text-ink-700 hover:bg-surface-hover"
          >
            <SvgIcon d={ICON.upload} size={16} />
            Importar documentación
          </Link>
        </div>
      )}
    </div>
  )
}

// ---- Pantalla principal ----
/**
 * Fila de documento de la Biblioteca, memoizada: sin memo, cada keystroke del
 * buscador (setQuery) re-renderizaba TODAS las filas de la lista.
 */
const DocumentRow = memo(function DocumentRow({
  doc,
  isMenuOpen,
  canDelete,
  canEdit,
  busy,
  onOpen,
  onToggleMenu,
  onViewHistory,
  onCopyLink,
  onArchiveToggle,
  onDeleteRequest,
}: {
  doc: Document
  isMenuOpen: boolean
  canDelete: boolean
  canEdit: boolean
  busy: boolean
  onOpen: (docId: string) => void
  onToggleMenu: (docId: string | null) => void
  onViewHistory: (docId: string) => void
  onCopyLink: (docId: string) => void
  onArchiveToggle: (doc: Document) => void
  onDeleteRequest: (doc: Document) => void
}) {
  const estado = toEstado(doc.status)
  const vlabel = versionLabel(doc.status, doc.version_number)
  const rowRef = useRef<HTMLDivElement>(null)

  // Cerrar al hacer click afuera o con Escape. Antes solo cerraba con
  // onMouseLeave, que no existe en touch — quedaba trabado abierto en mobile.
  // El ref cubre la fila entera (botón "…" + panel), así que un click en el
  // propio botón "…" para cerrar no dispara un cierre-y-reapertura fantasma.
  useEffect(() => {
    if (!isMenuOpen) return
    function onPointerDown(e: MouseEvent | TouchEvent) {
      if (rowRef.current && !rowRef.current.contains(e.target as Node)) {
        onToggleMenu(null)
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onToggleMenu(null)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('touchstart', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('touchstart', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [isMenuOpen, onToggleMenu])

  return (
    <div ref={rowRef} className="relative flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-3.5">
      {/* Ícono del documento */}
      <span
        className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo"
        aria-hidden="true"
      >
        <SvgIcon d={ICON.doc} size={19} />
      </span>

      {/* Cuerpo */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-bold text-ink-900">{doc.name}</span>
          {estado !== 'Archivado' && (
            <span
              className="inline-flex flex-shrink-0 items-center gap-[3px] rounded-[5px] border border-indigo-border bg-indigo-tint px-1.5 py-px text-[9.5px] font-extrabold text-indigo"
              title="Disponible para consultas inteligentes"
            >
              <SvgIcon d={ICON.ia} size={9} />
              IA
            </span>
          )}
        </div>
        <div className="mt-1.5">
          <VersionPill estado={estado} label={vlabel} />
        </div>
        <div className="mt-1.5 text-[11px] text-ink-300">
          {relDate(doc.created_at)}
        </div>
      </div>

      {/* Badge de estado */}
      <StatusBadge estado={estado} />

      {/* Botón Abrir */}
      <button
        type="button"
        onClick={() => onOpen(doc.id)}
        className="inline-flex h-[34px] flex-shrink-0 items-center gap-[7px] rounded-[9px] border border-line bg-surface px-4 text-[12.5px] font-bold text-ink-700 hover:bg-surface-hover"
      >
        Abrir
      </button>

      {/* Menú contextual */}
      <button
        type="button"
        aria-label="Más opciones"
        aria-expanded={isMenuOpen}
        aria-haspopup="menu"
        disabled={busy}
        onClick={() => onToggleMenu(isMenuOpen ? null : doc.id)}
        className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] border border-line bg-surface text-ink-500 hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        <SvgIcon d={ICON.dots} size={16} strokeWidth={2.4} />
      </button>

      {isMenuOpen && (
        <RowMenu
          doc={doc}
          canDelete={canDelete}
          canEdit={canEdit}
          onClose={() => onToggleMenu(null)}
          onOpen={() => onOpen(doc.id)}
          onViewHistory={() => onViewHistory(doc.id)}
          onCopyLink={() => onCopyLink(doc.id)}
          onArchiveToggle={() => onArchiveToggle(doc)}
          onDeleteRequest={() => onDeleteRequest(doc)}
        />
      )}
    </div>
  )
})

export default function WorkspacePage() {
  const { selectedWorkspaceId, selectedWorkspace, activeTenantId } = useWorkspace()
  const { canManage: canAdminister, loading: canAdministerLoading } = useCanManageWorkspace()
  const { incomplete: profileIncomplete, loading: profileCheckLoading } =
    useWorkspaceProfileIncomplete(selectedWorkspace, canAdminister, canAdministerLoading)

  const router = useRouter()
  const { hasPermission: canCreateDocuments } = useCanEditWorkspace()
  // Sin permiso de edición = solo lectura: esta pantalla (Biblioteca, con
  // acciones de crear/editar) no es para ellos — se los redirige a la vista
  // de solo lectura dedicada.
  const { hasPermission: canEditDocuments, loading: editPermLoading } = useHasPermission('documents.edit')
  const isReadOnly = !editPermLoading && !canEditDocuments
  // Fail-closed: mientras no cargó, false — el ítem "Eliminar" del menú no
  // aparece hasta confirmar el permiso (nunca mostramos algo que va a dar 403).
  const { hasPermission: canDeleteDocuments } = useHasPermission('documents.delete')
  const { modalProps } = usePdfViewer()

  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Folders planos recibidos del árbol (para calcular descendientes)
  const [allFolders, setAllFolders] = useState<Folder[]>([])

  // Filtros
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [estadoFilter, setEstadoFilter] = useState<EstadoFilter>('Todos')
  const [tab, setTab] = useState<TabView>('lista')
  const [tipoFilter, setTipoFilter] = useState<string | null>(null)
  const [menuId, setMenuId] = useState<string | null>(null)
  // Callback estable para las filas memoizadas (navegación SPA, sin recarga).
  const handleOpenDoc = useCallback((docId: string) => {
    router.push(`/documents/${docId}`)
  }, [router])
  const handleViewHistory = useCallback((docId: string) => {
    // El detalle del documento lee este query param para expandir el
    // historial y llevar el scroll a esa sección automáticamente.
    router.push(`/documents/${docId}?historial=1`)
  }, [router])

  // Opciones de tipo documental
  const [tipoOptions, setTipoOptions] = useState<CatalogOption[]>([])

  // ---- Feedback de acciones del menú contextual (copiar enlace / archivar / eliminar) ----
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyDocId, setBusyDocId] = useState<string | null>(null)
  const actionMessageTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (actionMessageTimeout.current) clearTimeout(actionMessageTimeout.current)
    }
  }, [])

  const showActionMessage = useCallback((message: string) => {
    setActionError(null)
    setActionMessage(message)
    if (actionMessageTimeout.current) clearTimeout(actionMessageTimeout.current)
    actionMessageTimeout.current = setTimeout(() => setActionMessage(null), 2800)
  }, [])

  const handleCopyLink = useCallback(async (docId: string) => {
    const url = `${window.location.origin}/documents/${docId}`
    try {
      await navigator.clipboard.writeText(url)
      showActionMessage('Enlace copiado al portapapeles.')
    } catch {
      setActionMessage(null)
      setActionError('No se pudo copiar el enlace. Copiálo manualmente desde la barra de direcciones.')
    }
  }, [showActionMessage])

  // ---- Eliminar (con confirmación) ----
  const [deleteTarget, setDeleteTarget] = useState<Document | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const handleDeleteRequest = useCallback((doc: Document) => {
    setDeleteError(null)
    setDeleteTarget(doc)
  }, [])

  // Redirigir a usuarios de solo lectura (sin documents.edit)
  useEffect(() => {
    if (isReadOnly) {
      router.replace('/dashboard/view')
    }
  }, [isReadOnly, router])

  // Al cambiar de tenant, limpiar selección de carpeta
  useEffect(() => {
    setSelectedFolderId(null)
  }, [activeTenantId])

  // Cargar documentos
  const loadDocuments = useCallback(async () => {
    if (!selectedWorkspaceId || !activeTenantId) {
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      setError(null)
      const docs = await listDocuments(selectedWorkspaceId, undefined, 'process')
      setDocuments(docs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspaceId, activeTenantId])

  const handleArchiveToggle = useCallback(async (doc: Document) => {
    const nextStatus = doc.status === 'archived' ? 'draft' : 'archived'
    setBusyDocId(doc.id)
    setActionError(null)
    try {
      await updateDocument(doc.id, { status: nextStatus })
      showActionMessage(nextStatus === 'archived' ? 'Documento archivado.' : 'Documento restaurado a borrador.')
      await loadDocuments()
    } catch (err) {
      setActionMessage(null)
      setActionError(err instanceof Error ? err.message : 'No se pudo actualizar el estado del documento.')
    } finally {
      setBusyDocId(null)
    }
  }, [loadDocuments, showActionMessage])

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await deleteDocument(deleteTarget.id)
      setDeleteTarget(null)
      showActionMessage('Documento eliminado.')
      await loadDocuments()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'No se pudo eliminar el documento.')
    } finally {
      setIsDeleting(false)
    }
  }, [deleteTarget, loadDocuments, showActionMessage])

  useEffect(() => {
    if (isReadOnly) return
    loadDocuments()
  }, [loadDocuments, isReadOnly])

  // Cargar opciones de tipo documental
  useEffect(() => {
    getDocumentTypes(false)
      .then((types) =>
        setTipoOptions(types.map((t) => ({ value: t.key, label: t.label, sort_order: t.sort_order })))
      )
      .catch(() => setTipoOptions([]))
  }, [])

  // ---- Set de IDs de carpeta seleccionada + descendientes ----
  // Nota: estos tres useMemo van ANTES de los early return de abajo (viewers /
  // sin workspace) a propósito — los hooks de React no pueden llamarse
  // condicionalmente. El cómputo es puro y su resultado se descarta en esos
  // casos (el componente igual retorna null / el mensaje de "sin workspace"),
  // así que esto no cambia qué se renderiza en ningún caso.
  const folderIdSet = useMemo<Set<string> | null>(() => {
    if (selectedFolderId === null) return null
    return getDescendantIds(selectedFolderId, allFolders)
  }, [selectedFolderId, allFolders])

  // ---- Filtrado + ordenamiento ----
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    let result = documents.filter((d) => {
      const est = toEstado(d.status)
      const estOk =
        tab === 'pendientes'
          ? est === 'Pendiente'
          : estadoFilter === 'Todos' || est === estadoFilter
      const folderOk = folderIdSet === null || (d.folder_id != null && folderIdSet.has(d.folder_id))
      const tipoOk = tipoFilter === null || d.document_type === tipoFilter
      const queryOk = !q || d.name.toLowerCase().includes(q) || d.description?.toLowerCase().includes(q)
      return estOk && folderOk && tipoOk && queryOk
    })
    // Tab "Recientes": ordenar por created_at descendente
    if (tab === 'recientes') {
      result = [...result].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
    }
    return result
  }, [documents, query, estadoFilter, tab, folderIdSet, tipoFilter])

  const counts = useMemo(() => ({
    apr: filtered.filter((d) => toEstado(d.status) === 'Aprobado').length,
    pen: filtered.filter((d) => toEstado(d.status) === 'Pendiente').length,
    bor: filtered.filter((d) => toEstado(d.status) === 'Borrador').length,
  }), [filtered])

  // Early return para usuarios de solo lectura (ya redirigidos arriba)
  if (isReadOnly) return null

  // ---- Sin workspace seleccionado ----
  if (!selectedWorkspaceId) {
    return (
      <div className="flex min-h-full items-start justify-center p-12">
        <p className="text-sm text-ink-500">Seleccioná un espacio de trabajo para continuar.</p>
      </div>
    )
  }

  // ---- Layout ----
  return (
    <div className="flex min-h-full items-stretch">

      {/* Panel de árbol de carpetas */}
      <BibliotecaFolderTree
        workspaceId={selectedWorkspaceId}
        selectedFolderId={selectedFolderId}
        onSelect={setSelectedFolderId}
        allDocuments={documents}
        totalCount={documents.length}
        onFoldersLoaded={setAllFolders}
      />

      {/* Área de contenido */}
      <div className="min-w-0 max-w-[940px] flex-1 px-8 pb-[50px] pt-7">

        {/* Banner de perfil incompleto */}
        {!profileCheckLoading && profileIncomplete && (
          <WorkspaceProfileBanner
            workspaceId={selectedWorkspaceId}
            canEditSettings={canAdminister}
            className="mb-6"
          />
        )}

        {/* Encabezado */}
        <div className="mb-[18px]">
          <div className="mb-1.5 text-xs font-bold uppercase tracking-[.1em] text-ink-400">
            Biblioteca
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-[25px] font-extrabold text-ink-900">Biblioteca</h1>
              <p className="mt-1.5 text-[13px] text-ink-400">
                Toda la documentación oficial de la organización. El documento oficial es la fuente de verdad.
              </p>
            </div>
            {canCreateDocuments && (
              <div className="flex flex-shrink-0 items-center gap-2 pt-1">
                <Link
                  href="/import"
                  className="inline-flex h-[38px] items-center gap-2 rounded-[10px] border border-line bg-surface px-4 text-[13px] font-bold text-ink-700 hover:bg-surface-hover"
                >
                  <Upload size={15} aria-hidden="true" />
                  Importar
                </Link>
                <Link
                  href="/documents/new"
                  className="inline-flex h-[38px] items-center gap-2 rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white hover:bg-ink-900"
                >
                  <Plus size={15} aria-hidden="true" />
                  Nuevo
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Feedback de acciones del menú contextual (copiar enlace / archivar / eliminar) */}
        {actionError && (
          <div
            role="alert"
            className="mb-3.5 rounded-[11px] border border-danger-bd bg-danger-bg px-4 py-3 text-[12.5px] font-semibold text-danger"
          >
            {actionError}
          </div>
        )}
        {actionMessage && (
          <div
            role="status"
            className="mb-3.5 rounded-[11px] border border-success-bd bg-success-bg px-4 py-3 text-[12.5px] font-semibold text-success-fg"
          >
            {actionMessage}
          </div>
        )}

        {/* Tabs (sin "Carpetas") */}
        <div className="mb-[18px] inline-flex items-center gap-0.5 rounded-[10px] bg-surface-track p-[3px]">
          {(['lista', 'recientes', 'pendientes'] as TabView[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setTab(v)}
              className={
                'h-8 rounded-lg px-[15px] text-[12.5px] font-bold capitalize transition-all ' +
                (tab === v ? 'bg-surface text-ink-800 shadow-card' : 'text-ink-400 hover:text-ink-700')
              }
              aria-pressed={tab === v}
            >
              {v}
            </button>
          ))}
        </div>

        {/* Búsqueda */}
        <div className="relative mb-3.5">
          <Search size={16} className="absolute left-3.5 top-3.5 text-ink-300" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar documentos…"
            className="h-[42px] w-full rounded-[10px] border border-line bg-surface pl-[38px] pr-3.5 text-[13.5px] text-ink-800 outline-none placeholder:text-ink-300 focus:border-indigo focus:ring-[3px] focus:ring-indigo-tint"
            aria-label="Buscar documentos"
          />
        </div>

        {/* Chips de estado */}
        <div className="mb-3 flex flex-wrap gap-[7px]">
          {ESTADOS.map((s) => (
            <Chip key={s} active={estadoFilter === s} onClick={() => setEstadoFilter(s)}>
              {s}
            </Chip>
          ))}
        </div>

        {/* Filtro de tipo documental */}
        {tipoOptions.length > 0 && (
          <div className="mb-[18px] flex flex-wrap items-center gap-2">
            <span className="mr-0.5 text-[11px] text-ink-300">Filtros:</span>
            <TipoDocumentalFilter
              value={tipoFilter}
              onChange={setTipoFilter}
              options={tipoOptions}
            />
          </div>
        )}

        {/* Resumen */}
        <div className="mb-3">
          <div className="text-[11.5px] text-ink-400">
            Mostrando {filtered.length} de {documents.length} documentos
            <span className="text-ink-200"> · </span>
            <span className="font-bold text-success-fg">{counts.apr} aprobados</span>
            <span className="text-ink-200"> · </span>
            <span className="font-bold text-warning">{counts.pen} pendientes</span>
            <span className="text-ink-200"> · </span>
            <span className="font-bold text-info">{counts.bor} borradores</span>
          </div>
        </div>

        {/* Lista / estados */}
        {loading ? (
          <div className="flex flex-col gap-[9px]">
            {[1, 2, 3, 4].map((i) => <RowSkeleton key={i} />)}
          </div>
        ) : error ? (
          <div className="rounded-[13px] border border-danger-bd bg-danger-bg px-[18px] py-4">
            <p className="text-[13px] text-danger">Error cargando documentos: {error}</p>
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState canCreate={canCreateDocuments} />
        ) : (
          <div className="flex flex-col gap-[9px]">
            {filtered.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                isMenuOpen={menuId === doc.id}
                canDelete={canDeleteDocuments}
                canEdit={canEditDocuments}
                busy={busyDocId === doc.id}
                onOpen={handleOpenDoc}
                onToggleMenu={setMenuId}
                onViewHistory={handleViewHistory}
                onCopyLink={handleCopyLink}
                onArchiveToggle={handleArchiveToggle}
                onDeleteRequest={handleDeleteRequest}
              />
            ))}
          </div>
        )}
      </div>

      <ArtifactViewerModal {...modalProps} />

      {/* Confirmación de eliminación */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => { if (!isDeleting) setDeleteTarget(null) }}
        title="Eliminar documento"
        maxWidth="max-w-md"
      >
        <p className="text-sm text-ink-700">
          ¿Querés eliminar &quot;{deleteTarget?.name}&quot;? Esta acción no se puede deshacer.
        </p>
        {deleteError && (
          <p role="alert" className="mt-3 rounded-[9px] border border-danger-bd bg-danger-bg px-3 py-2 text-xs font-semibold text-danger">
            {deleteError}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2.5">
          <button
            type="button"
            onClick={() => setDeleteTarget(null)}
            disabled={isDeleting}
            className="inline-flex h-10 items-center rounded-[10px] border border-line-input bg-surface px-4 text-[13px] font-bold text-ink-700 hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleDeleteConfirm}
            disabled={isDeleting}
            className="inline-flex h-10 items-center rounded-[10px] bg-danger px-4 text-[13px] font-bold text-white hover:bg-danger-press disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDeleting ? 'Eliminando…' : 'Eliminar'}
          </button>
        </div>
      </Dialog>

    </div>
  )
}
