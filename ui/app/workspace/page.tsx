'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Plus, Upload, ChevronDown } from 'lucide-react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { listDocuments, Document } from '@/lib/api'
import { useUserRole } from '@/hooks/useUserRole'
import { useCanEditWorkspace } from '@/hooks/useHasPermission'
import { useWorkspaceProfileIncomplete } from '@/hooks/useWorkspaceProfileIncomplete'
import WorkspaceProfileBanner from '@/components/workspace/WorkspaceProfileBanner'
import FileImportModal from '@/components/processes/FileImportModal'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import BibliotecaFolderTree from '@/components/biblioteca/BibliotecaFolderTree'
import { StatusBadge, VersionPill, ESTADO_LABEL, Chip } from '@/shared/ui/components'
import type { DocumentEstado } from '@/shared/ui/components'

// ---- Tipos de vista y densidad ----
type TabView = 'lista' | 'carpetas' | 'recientes' | 'pendientes'
type Density = 'detallada' | 'compacta'

const ESTADOS = ['Todos', 'Aprobado', 'Pendiente', 'Borrador', 'Archivado'] as const
type EstadoFilter = (typeof ESTADOS)[number]

const EXTRA_FILTERS = ['Tipo documental', 'Responsable', 'Autor', 'Aprobador', 'Fecha', 'Consultas IA']

// ---- Helpers ----

/** Convierte el status de API al nombre visible */
function toEstado(status: string): DocumentEstado {
  return ESTADO_LABEL[status] ?? 'Borrador'
}

/** Etiqueta de versión inline según estado */
function versionLabel(status: string): string {
  const e = toEstado(status)
  switch (e) {
    case 'Aprobado': return 'v1 · Oficial'
    case 'Pendiente': return 'En revisión'
    case 'Archivado': return 'Archivado'
    default: return 'Sin versión aún'
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
  dense:  'M4 7h16M4 12h16M4 17h10',
  sparse: 'M4 5h16M4 9h16M4 13h16M4 17h16',
}

// ---- Menú contextual por fila ----
function RowMenu({
  status,
  docId,
  onClose,
  onOpen,
}: {
  status: string
  docId: string
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
function EmptyState({
  canCreate,
  onImport,
}: {
  canCreate: boolean
  onImport: () => void
}) {
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
            href="/processes/new"
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
  const { incomplete: profileIncomplete, loading: profileCheckLoading } =
    useWorkspaceProfileIncomplete(selectedWorkspace, workspaceRole, platformRoles)

  const router = useRouter()

  const { hasPermission: canCreateDocuments } = useCanEditWorkspace()

  const { ModalComponent } = usePdfViewer()

  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [estadoFilter, setEstadoFilter] = useState<EstadoFilter>('Todos')
  const [tab, setTab] = useState<TabView>('lista')
  const [density, setDensity] = useState<Density>('detallada')
  const [menuId, setMenuId] = useState<string | null>(null)
  const [importOpen, setImportOpen] = useState(false)

  // Redirigir viewers a su página dedicada
  useEffect(() => {
    if (!roleLoading && role === 'viewer') {
      router.replace('/dashboard/view')
    }
  }, [role, roleLoading, router])

  // Al cambiar de tenant, limpiar selección
  useEffect(() => {
    setSelectedFolderId(null)
  }, [activeTenantId])

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

  // Early return para viewers
  if (!roleLoading && role === 'viewer') return null

  // ---- Filtrado ----
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    return documents.filter((d) => {
      const est = toEstado(d.status)
      const estOk =
        tab === 'pendientes'
          ? est === 'Pendiente'
          : estadoFilter === 'Todos' || est === estadoFilter
      const folderOk = selectedFolderId === null || d.folder_id === selectedFolderId
      const queryOk = !q || d.name.toLowerCase().includes(q) || d.description?.toLowerCase().includes(q)
      return estOk && folderOk && queryOk
    })
  }, [documents, query, estadoFilter, tab, selectedFolderId])

  const counts = useMemo(() => ({
    apr: filtered.filter((d) => toEstado(d.status) === 'Aprobado').length,
    pen: filtered.filter((d) => toEstado(d.status) === 'Pendiente').length,
    bor: filtered.filter((d) => toEstado(d.status) === 'Borrador').length,
  }), [filtered])

  const compact = density === 'compacta'

  // ---- Sin workspace seleccionado ----
  if (!selectedWorkspaceId) {
    return (
      <div className="flex min-h-full items-start justify-center p-12">
        <p className="text-sm text-ink-500">Seleccioná un espacio de trabajo para continuar.</p>
      </div>
    )
  }

  // ---- Layout principal ----
  return (
    <div className="flex min-h-full items-stretch">

      {/* Panel de árbol de carpetas */}
      <BibliotecaFolderTree
        workspaceId={selectedWorkspaceId}
        selectedFolderId={selectedFolderId}
        onSelect={setSelectedFolderId}
        allDocuments={documents}
        totalCount={documents.length}
      />

      {/* Área de contenido */}
      <div className="min-w-0 max-w-[940px] flex-1 px-8 pb-[50px] pt-7">

        {/* Banner de perfil incompleto */}
        {!profileCheckLoading && profileIncomplete && (
          <WorkspaceProfileBanner
            workspaceId={selectedWorkspaceId}
            canEditSettings={
              platformRoles.includes('superadmin') ||
              workspaceRole === 'owner' ||
              workspaceRole === 'creator' ||
              workspaceRole === 'admin'
            }
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
                  href="/processes/new"
                  className="inline-flex h-[38px] items-center gap-2 rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white hover:bg-ink-900"
                >
                  <Plus size={15} aria-hidden="true" />
                  Nuevo
                </a>
              </div>
            )}
          </div>
        </div>

        {/* Tabs de vista */}
        <div className="mb-[18px] inline-flex items-center gap-0.5 rounded-[10px] bg-surface-track p-[3px]">
          {(['lista', 'carpetas', 'recientes', 'pendientes'] as TabView[]).map((v) => (
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
          <Search
            size={16}
            className="absolute left-3.5 top-3.5 text-ink-300"
            aria-hidden="true"
          />
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

        {/* Filtros extra (placeholders sin acción real por ahora) */}
        <div className="mb-[18px] flex flex-wrap items-center gap-2">
          <span className="mr-0.5 text-[11px] text-ink-300">Filtros:</span>
          {EXTRA_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              className="inline-flex h-[30px] items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 text-[11.5px] font-semibold text-ink-500 hover:bg-surface-hover"
              aria-label={`Filtrar por ${f}`}
            >
              {f}
              <ChevronDown size={11} className="text-ink-300" aria-hidden="true" />
            </button>
          ))}
        </div>

        {/* Resumen + toggle densidad */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-[11.5px] text-ink-400">
            Mostrando {filtered.length} de {documents.length} documentos
            <span className="text-ink-200"> · </span>
            <span className="font-bold text-success-fg">{counts.apr} aprobados</span>
            <span className="text-ink-200"> · </span>
            <span className="font-bold text-warning">{counts.pen} pendientes</span>
            <span className="text-ink-200"> · </span>
            <span className="font-bold text-info">{counts.bor} borradores</span>
          </div>
          <div className="inline-flex items-center gap-0.5 rounded-lg bg-surface-track p-0.5">
            {(
              [
                ['detallada', ICON.dense],
                ['compacta', ICON.sparse],
              ] as const
            ).map(([k, d]) => (
              <button
                key={k}
                type="button"
                onClick={() => setDensity(k)}
                title={`Vista ${k}`}
                aria-label={`Vista ${k}`}
                aria-pressed={density === k}
                className={
                  'grid h-[26px] w-[30px] place-items-center rounded-md transition-all ' +
                  (density === k ? 'bg-surface text-ink-800 shadow-card' : 'text-ink-300 hover:text-ink-500')
                }
              >
                <SvgIcon d={d} size={15} />
              </button>
            ))}
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
          <div className={'flex flex-col ' + (compact ? 'gap-1.5' : 'gap-[9px]')}>
            {filtered.map((doc) => {
              const estado = toEstado(doc.status)
              const vlabel = versionLabel(doc.status)
              const isMenuOpen = menuId === doc.id
              const handleOpen = () => { window.location.href = `/documents/${doc.id}` }

              return (
                <div
                  key={doc.id}
                  className={
                    'relative flex items-center border border-line bg-surface ' +
                    (compact
                      ? 'gap-3 rounded-[11px] px-4 py-[9px]'
                      : 'gap-[15px] rounded-[13px] px-[18px] py-3.5')
                  }
                >
                  {/* Ícono del documento */}
                  <span
                    className={
                      'grid flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo ' +
                      (compact ? 'h-[30px] w-[30px]' : 'h-10 w-10')
                    }
                    aria-hidden="true"
                  >
                    <SvgIcon d={ICON.doc} size={compact ? 16 : 19} />
                  </span>

                  {/* Cuerpo */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={
                          'truncate font-bold text-ink-900 ' + (compact ? 'text-[13px]' : 'text-sm')
                        }
                      >
                        {doc.name}
                      </span>
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

                    {!compact && (
                      <>
                        <div className="mt-1.5">
                          <VersionPill estado={estado} label={vlabel} />
                        </div>
                        <div className="mt-1.5 text-[11px] text-ink-300">
                          {relDate(doc.created_at)}
                        </div>
                      </>
                    )}

                    {compact && (
                      <div className="mt-0.5 flex items-center gap-[7px] truncate text-[11px] text-ink-300">
                        <VersionPill estado={estado} label={vlabel} />
                        <span>·</span>
                        <span>{relDate(doc.created_at)}</span>
                      </div>
                    )}
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

                  {/* Menú contextual (tres puntos) */}
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
                      docId={doc.id}
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
