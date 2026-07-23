'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Plus, Upload, ChevronDown, X } from 'lucide-react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { listDocuments, getDocumentTypes, Document, Folder, CatalogOption } from '@/lib/api'
import { useUserRole } from '@/hooks/useUserRole'
import { useCanEditWorkspace } from '@/hooks/useHasPermission'
import { useWorkspaceProfileIncomplete } from '@/hooks/useWorkspaceProfileIncomplete'
import { canAdministerWorkspace } from '@/lib/adminGating'
import WorkspaceProfileBanner from '@/components/workspace/WorkspaceProfileBanner'
import FileImportModal from '@/components/processes/FileImportModal'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import BibliotecaFolderTree from '@/components/biblioteca/BibliotecaFolderTree'
import { StatusBadge, VersionPill, ESTADO_LABEL, Chip } from '@/shared/ui/components'
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
function RowMenu({
  status,
  onClose,
  onOpen,
}: {
  status: string
  onClose: () => void
  onOpen: () => void
}) {
  const e = toEstado(status)
  const groups: { label: string; danger?: boolean; action?: () => void }[][] = [
    [
      { label: 'Abrir documento', action: onOpen },
      { label: 'Ver historial' },
    ],
    [
      ...((e === 'Aprobado' || e === 'Pendiente') ? [{ label: 'Crear nueva versión' }] : []),
      { label: 'Copiar enlace' },
    ],
    [
      { label: 'Mover' },
      { label: 'Archivar' },
      ...(e === 'Borrador' ? [{ label: 'Eliminar', danger: true }] : []),
    ],
  ]

  return (
    <div
      className="absolute right-3.5 top-[calc(100%-4px)] z-20 w-[212px] rounded-[11px] border border-line bg-surface p-1.5 shadow-menu"
      onMouseLeave={onClose}
    >
      {groups.map((g, gi) => (
        <div key={gi}>
          {gi > 0 && <div className="mx-2 my-[5px] h-px bg-line-soft" />}
          {g.map((a) => (
            <button
              key={a.label}
              type="button"
              onClick={() => { a.action?.(); onClose() }}
              className={
                'w-full rounded-md px-2.5 py-2 text-left text-[12.5px] font-semibold ' +
                (a.danger ? 'text-danger' : 'text-ink-800 hover:bg-surface-hover')
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

// ---- Skeleton de fila ----
function RowSkeleton() {
  return (
    <div className="flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-3.5">
      <div className="h-10 w-10 flex-shrink-0 animate-pulse rounded-[10px] bg-ink-100" />
      <div className="flex-1 space-y-2">
        <div className="h-4 w-1/2 animate-pulse rounded bg-ink-100" />
        <div className="h-3 w-1/3 animate-pulse rounded bg-ink-100" />
      </div>
      <div className="h-7 w-20 animate-pulse rounded-pill bg-ink-100" />
      <div className="h-[34px] w-16 animate-pulse rounded-[9px] bg-ink-100" />
    </div>
  )
}

// ---- Empty state ----
function EmptyState({ canCreate, onImport }: { canCreate: boolean; onImport: () => void }) {
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
          <a
            href="/documents/new"
            className="inline-flex h-[42px] items-center gap-2 rounded-[10px] bg-ink-800 px-[18px] text-[13.5px] font-bold text-white hover:bg-ink-900"
          >
            <SvgIcon d={ICON.plus} size={16} />
            Crear documento
          </a>
          <button
            type="button"
            onClick={onImport}
            className="inline-flex h-[42px] items-center gap-2 rounded-[10px] border border-line-input bg-surface px-[18px] text-[13.5px] font-bold text-ink-700 hover:bg-surface-hover"
          >
            <SvgIcon d={ICON.upload} size={16} />
            Importar documentación
          </button>
        </div>
      )}
    </div>
  )
}

// ---- Pantalla principal ----
export default function WorkspacePage() {
  const { selectedWorkspaceId, selectedWorkspace, activeTenantId, platformRoles } = useWorkspace()
  const { role, loading: roleLoading } = useUserRole()
  const workspaceRole = selectedWorkspace?.role ?? role
  const canAdminister = canAdministerWorkspace({ platformRoles, workspaceRole })
  const { incomplete: profileIncomplete, loading: profileCheckLoading } =
    useWorkspaceProfileIncomplete(selectedWorkspace, workspaceRole, platformRoles)

  const router = useRouter()
  const { hasPermission: canCreateDocuments } = useCanEditWorkspace()
  const { ModalComponent } = usePdfViewer()

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
  const [importOpen, setImportOpen] = useState(false)

  // Opciones de tipo documental
  const [tipoOptions, setTipoOptions] = useState<CatalogOption[]>([])

  // Redirigir viewers
  useEffect(() => {
    if (!roleLoading && role === 'viewer') {
      router.replace('/dashboard/view')
    }
  }, [role, roleLoading, router])

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

  useEffect(() => {
    if (role === 'viewer') return
    loadDocuments()
  }, [loadDocuments, role])

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

  // Early return para viewers
  if (!roleLoading && role === 'viewer') return null

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
                <button
                  type="button"
                  onClick={() => setImportOpen(true)}
                  className="inline-flex h-[38px] items-center gap-2 rounded-[10px] border border-line bg-surface px-4 text-[13px] font-bold text-ink-700 hover:bg-surface-hover"
                >
                  <Upload size={15} aria-hidden="true" />
                  Importar
                </button>
                <a
                  href="/documents/new"
                  className="inline-flex h-[38px] items-center gap-2 rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white hover:bg-ink-900"
                >
                  <Plus size={15} aria-hidden="true" />
                  Nuevo
                </a>
              </div>
            )}
          </div>
        </div>

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
          <EmptyState canCreate={canCreateDocuments} onImport={() => setImportOpen(true)} />
        ) : (
          <div className="flex flex-col gap-[9px]">
            {filtered.map((doc) => {
              const estado = toEstado(doc.status)
              const vlabel = versionLabel(doc.status, doc.version_number)
              const isMenuOpen = menuId === doc.id
              const handleOpen = () => { window.location.href = `/documents/${doc.id}` }

              return (
                <div
                  key={doc.id}
                  className="relative flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-3.5"
                >
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
                    onClick={handleOpen}
                    className="inline-flex h-[34px] flex-shrink-0 items-center gap-[7px] rounded-[9px] border border-line bg-surface px-4 text-[12.5px] font-bold text-ink-700 hover:bg-surface-hover"
                  >
                    Abrir
                  </button>

                  {/* Menú contextual */}
                  <button
                    type="button"
                    aria-label="Más opciones"
                    aria-expanded={isMenuOpen}
                    onClick={() => setMenuId(isMenuOpen ? null : doc.id)}
                    className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] border border-line bg-surface text-ink-500 hover:bg-surface-hover"
                  >
                    <SvgIcon d={ICON.dots} size={16} strokeWidth={2.4} />
                  </button>

                  {isMenuOpen && (
                    <RowMenu
                      status={doc.status}
                      onClose={() => setMenuId(null)}
                      onOpen={handleOpen}
                    />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <ModalComponent />

      {selectedWorkspaceId && (
        <FileImportModal
          workspaceId={selectedWorkspaceId}
          defaultFolderId={selectedFolderId}
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onImported={loadDocuments}
        />
      )}
    </div>
  )
}
