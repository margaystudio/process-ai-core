'use client'

import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { ChevronRight, Folder as FolderIcon, Plus } from 'lucide-react'
import {
  getDocumentTypes,
  getFolderGovernance,
  getFolderPermissions,
  getFolderStats,
  listDocuments,
  listFolders,
  listOperationalRoles,
  updateFolderPermissions,
  type Document,
  type DocumentType,
  type Folder,
  type FolderGovernance,
  type FolderGovernanceOrigin,
  type FolderPermissionsResponse,
  type FolderStats,
  type OperationalRoleResponse,
} from '@/lib/api'
import { useAsync } from '@/hooks/useAsync'
import { useFolderCrud } from '@/hooks/useFolderCrud'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { Dialog, InheritancePill, Switch, Tabs, TabsContent, type InheritanceKind, type TabItem } from '@/shared/ui/components'

type FolderNode = Folder & {
  children: FolderNode[]
  docs: number
}

const DEFAULT_FOLDER_COLOR = '#48569C'
const FOLDER_COLORS = ['#48569C', '#2F9E62', '#C99A2E', '#2E8B8B', '#CB4242', '#8B5CF6']
const FOLDER_ICONS = ['folder', 'archive', 'book', 'briefcase', 'clipboard', 'file-text']
const FOLDER_TABS: TabItem[] = [
  { value: 'resumen', label: 'Resumen' },
  { value: 'general', label: 'General' },
  { value: 'gobierno', label: 'Gobierno' },
  { value: 'tyto', label: 'Tyto' },
  { value: 'permisos', label: 'Permisos' },
  { value: 'actividad', label: 'Actividad' },
]

function buildTree(folders: Folder[], docCounts: Map<string, number>): FolderNode[] {
  const nodes = new Map<string, FolderNode>()
  folders.forEach((folder) => {
    nodes.set(folder.id, {
      ...folder,
      children: [],
      docs: docCounts.get(folder.id) ?? 0,
    })
  })

  const roots: FolderNode[] = []
  nodes.forEach((node) => {
    if (node.parent_id && nodes.has(node.parent_id)) {
      nodes.get(node.parent_id)?.children.push(node)
    } else {
      roots.push(node)
    }
  })

  const sortNodes = (items: FolderNode[]) => {
    items.sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))
    items.forEach((item) => sortNodes(item.children))
  }
  sortNodes(roots)
  return roots
}

function countDocumentsByFolder(documents: Document[]): Map<string, number> {
  const counts = new Map<string, number>()
  documents.forEach((doc) => {
    if (!doc.folder_id) return
    counts.set(doc.folder_id, (counts.get(doc.folder_id) ?? 0) + 1)
  })
  return counts
}

function findNode(nodes: FolderNode[], id: string | null): FolderNode | null {
  if (!id) return null
  for (const node of nodes) {
    if (node.id === id) return node
    const child = findNode(node.children, id)
    if (child) return child
  }
  return null
}

function flatten(nodes: FolderNode[]): FolderNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)])
}

function folderColor(folder: Folder | null): string {
  return folder?.color || DEFAULT_FOLDER_COLOR
}

function folderDescription(folder: Folder | null): string {
  return folder?.metadata?.description || 'Dominio de conocimiento documental con configuracion propia.'
}

function buildUpdatedPath(folder: Folder, nextName: string, folders: Folder[]): string {
  if (!folder.parent_id) return nextName
  const parent = folders.find((item) => item.id === folder.parent_id)
  const parentPath = parent?.path || parent?.name
  return parentPath ? `${parentPath}/${nextName}` : nextName
}

function formatConfidence(value: number | null | undefined): string {
  if (value == null) return '-'
  return `${Math.round(value * 100)}%`
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'Borrador',
    pending_validation: 'Pendiente',
    approved: 'Aprobado',
    rejected: 'Rechazado',
    archived: 'Archivado',
  }
  return labels[status] ?? status
}

function governancePillKind(origin: FolderGovernanceOrigin): InheritanceKind {
  if (origin === 'heredado') return 'inherited'
  if (origin === 'personalizado') return 'custom'
  return 'base'
}

function documentTypeLabel(value: string | null | undefined, documentTypes: DocumentType[]): string {
  if (!value) return 'Configuracion base'
  return documentTypes.find((type) => type.key === value)?.label ?? value
}

function StatsStrip({
  stats,
  status,
  error,
  onRetry,
}: {
  stats: FolderStats | null | undefined
  status: 'idle' | 'loading' | 'success' | 'error'
  error: string | null
  onRetry: () => void
}) {
  if (status === 'idle' || status === 'loading') {
    return (
      <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3 rounded-[13px] border border-line bg-surface px-5 py-4 shadow-card">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="w-[84px] space-y-2">
            <div className="h-5 w-10 animate-pulse rounded bg-ink-100" />
            <div className="h-3 w-20 animate-pulse rounded bg-ink-100" />
          </div>
        ))}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="mt-5 rounded-[13px] border border-danger-bd bg-danger-bg px-5 py-4">
        <p className="text-[12.5px] font-semibold text-danger">{error}</p>
        <button type="button" onClick={onRetry} className="mt-2 text-[12px] font-bold text-ink-700 underline">
          Reintentar metricas
        </button>
      </div>
    )
  }

  const items = [
    ['Documentos', stats?.documentos ?? 0],
    ['Aprobados', stats?.aprobados ?? 0],
    ['Borradores', stats?.borradores ?? 0],
    ['Pendientes', stats?.pendientes ?? 0],
    ['Relaciones nuevas', stats?.relaciones_nuevas ?? 0],
    ['Confianza prom.', formatConfidence(stats?.confianza_prom)],
  ]

  return (
    <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3 rounded-[13px] border border-line bg-surface px-5 py-4 shadow-card">
      {items.map(([label, value]) => (
        <div key={label}>
          <div className="text-lg font-extrabold text-ink-900">{value}</div>
          <div className="text-[11px] text-ink-400">{label}</div>
        </div>
      ))}
    </div>
  )
}

function SummaryTab({
  workspaceId,
  folder,
  stats,
}: {
  workspaceId: string
  folder: Folder
  stats: FolderStats | null | undefined
}) {
  const { status, data, error, reload } = useAsync(async () => {
    if (!workspaceId || !folder.id) return []
    return listDocuments(workspaceId, folder.id, 'process')
  }, [workspaceId, folder.id])

  const recentDocuments = (data ?? []).slice(0, 5)
  const cards = [
    ['Documentos', stats?.documentos ?? 0],
    ['Aprobados', stats?.aprobados ?? 0],
    ['Borradores', stats?.borradores ?? 0],
    ['Pendientes', stats?.pendientes ?? 0],
    ['Archivados', stats?.archivados ?? 0],
    ['Relaciones nuevas', stats?.relaciones_nuevas ?? 0],
  ]

  return (
    <div className="mt-6 space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map(([label, value]) => (
          <div key={label} className="rounded-[12px] border border-line bg-surface px-4 py-3 shadow-card">
            <div className="text-xl font-extrabold text-ink-900">{value}</div>
            <div className="text-[11.5px] font-semibold text-ink-400">{label}</div>
          </div>
        ))}
      </div>

      <div className="rounded-[13px] border border-line bg-surface shadow-card">
        <div className="border-b border-line px-5 py-3">
          <h2 className="text-[13px] font-extrabold text-ink-900">Documentos recientes</h2>
        </div>
        {status === 'idle' || status === 'loading' ? (
          <div className="space-y-2 px-5 py-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded-lg bg-ink-100" />
            ))}
          </div>
        ) : null}
        {status === 'error' ? (
          <div className="px-5 py-4">
            <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
              {error}
            </div>
            <button type="button" onClick={reload} className="mt-2 text-[12px] font-bold text-ink-700 underline">
              Reintentar
            </button>
          </div>
        ) : null}
        {status === 'success' && recentDocuments.length === 0 ? (
          <div className="px-5 py-8 text-center text-[13px] text-ink-400">
            Esta carpeta todavia no tiene documentos.
          </div>
        ) : null}
        {status === 'success' && recentDocuments.length > 0 ? (
          <div className="divide-y divide-line-soft">
            {recentDocuments.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-bold text-ink-800">{doc.name}</div>
                  <div className="text-[11.5px] text-ink-400">{statusLabel(doc.status)}</div>
                </div>
                <div className="text-[11px] text-ink-300">{new Date(doc.created_at).toLocaleDateString()}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function GeneralTab({
  folder,
  folders,
  saving,
  error,
  onSave,
}: {
  folder: Folder
  folders: Folder[]
  saving: boolean
  error: string | null
  onSave: (fields: {
    name: string
    path: string
    color: string
    icon: string
    description: string
  }) => Promise<void>
}) {
  const [name, setName] = useState(folder.name)
  const [description, setDescription] = useState(folderDescription(folder))
  const [color, setColor] = useState(folderColor(folder))
  const [icon, setIcon] = useState(folder.icon || 'folder')
  const [localError, setLocalError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setName(folder.name)
    setDescription(folderDescription(folder))
    setColor(folderColor(folder))
    setIcon(folder.icon || 'folder')
    setLocalError(null)
    setSaved(false)
  }, [folder])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextName = name.trim()
    if (!nextName) {
      setLocalError('El nombre es requerido')
      return
    }

    try {
      setLocalError(null)
      setSaved(false)
      await onSave({
        name: nextName,
        path: buildUpdatedPath(folder, nextName, folders),
        color,
        icon,
        description: description.trim(),
      })
      setSaved(true)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Error al guardar la carpeta')
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 max-w-[620px] space-y-4">
      <label className="block">
        <span className="mb-1.5 block text-[13px] font-bold text-ink-900">Nombre</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="h-[42px] w-full rounded-[10px] border border-line-input px-3.5 text-sm outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
        />
      </label>

      <label className="block">
        <span className="mb-1.5 block text-[13px] font-bold text-ink-900">Descripcion</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="min-h-[96px] w-full resize-none rounded-[10px] border border-line-input px-3.5 py-2 text-sm outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
        />
      </label>

      <div>
        <span className="mb-2 block text-[13px] font-bold text-ink-900">Color</span>
        <div className="flex flex-wrap gap-2">
          {FOLDER_COLORS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setColor(option)}
              aria-label={`Color ${option}`}
              aria-pressed={color === option}
              className={
                'h-7 w-7 rounded-full border-2 transition ' +
                (color === option ? 'scale-110 border-ink-900' : 'border-transparent hover:scale-105')
              }
              style={{ backgroundColor: option }}
            />
          ))}
        </div>
      </div>

      <label className="block">
        <span className="mb-1.5 block text-[13px] font-bold text-ink-900">Icono</span>
        <select
          value={icon}
          onChange={(event) => setIcon(event.target.value)}
          className="h-[42px] w-full rounded-[10px] border border-line-input px-3 text-sm outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
        >
          {FOLDER_ICONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      {(localError || error) ? (
        <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
          {localError || error}
        </div>
      ) : null}
      {saved ? (
        <div className="rounded-[10px] border border-green-border bg-green-bg px-3 py-2 text-[12.5px] font-semibold text-green-text">
          Cambios guardados
        </div>
      ) : null}

      <button
        type="submit"
        disabled={saving}
        className="h-[40px] rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white disabled:opacity-60"
      >
        {saving ? 'Guardando...' : 'Guardar cambios'}
      </button>
    </form>
  )
}

function GovernanceBlock({
  title,
  pill,
  children,
}: {
  title: string
  pill: ReactNode
  children: ReactNode
}) {
  return (
    <div className="rounded-[13px] border border-line bg-surface p-5 shadow-card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[13px] font-extrabold text-ink-900">{title}</h2>
        {pill}
      </div>
      {children}
    </div>
  )
}

function GovernanceTab({
  governance,
  status,
  error,
  onRetry,
  documentTypes,
  documentTypesStatus,
  saving,
  mutationError,
  onSave,
}: {
  governance: FolderGovernance | null | undefined
  status: 'idle' | 'loading' | 'success' | 'error'
  error: string | null
  onRetry: () => void
  documentTypes: DocumentType[]
  documentTypesStatus: 'idle' | 'loading' | 'success' | 'error'
  saving: boolean
  mutationError: string | null
  onSave: (fields: {
    default_document_type?: string | null
    allow_document_override?: boolean
  }) => Promise<void>
}) {
  const [defaultType, setDefaultType] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  useEffect(() => {
    setDefaultType(governance?.default_document_type.value ?? documentTypes[0]?.key ?? '')
    setLocalError(null)
  }, [governance, documentTypes])

  async function persist(fields: {
    default_document_type?: string | null
    allow_document_override?: boolean
  }) {
    try {
      setLocalError(null)
      await onSave(fields)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Error al guardar gobierno')
    }
  }

  if (status === 'idle' || status === 'loading') {
    return (
      <div className="mt-6 space-y-3.5">
        {[0, 1].map((item) => (
          <div key={item} className="h-[118px] animate-pulse rounded-[13px] border border-line bg-surface" />
        ))}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="mt-6 rounded-[13px] border border-danger-bd bg-danger-bg px-5 py-4">
        <p className="text-[12.5px] font-semibold text-danger">{error}</p>
        <button type="button" onClick={onRetry} className="mt-2 text-[12px] font-bold text-ink-700 underline">
          Reintentar gobierno
        </button>
      </div>
    )
  }

  const defaultDocument = governance?.default_document_type
  const overrideValue = governance?.allow_document_override.value ?? true

  return (
    <div className="mt-6 max-w-[760px] space-y-3.5">
      {(localError || mutationError) ? (
        <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
          {localError || mutationError}
        </div>
      ) : null}

      <GovernanceBlock
        title="Tipo documental por defecto"
        pill={
          <InheritancePill
            kind={governancePillKind(defaultDocument?.origin ?? 'base')}
            from={defaultDocument?.from ?? undefined}
          />
        }
      >
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[260px] flex-1">
            <span className="mb-1.5 block text-[12px] font-bold text-ink-400">Valor efectivo</span>
            <select
              value={defaultType}
              onChange={(event) => setDefaultType(event.target.value)}
              disabled={saving || documentTypesStatus === 'loading' || documentTypes.length === 0}
              className="h-[42px] w-full rounded-[10px] border border-line-input px-3 text-sm font-semibold text-ink-800 outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10 disabled:opacity-60"
            >
              {documentTypes.length === 0 ? (
                <option value="">{documentTypeLabel(defaultDocument?.value, documentTypes)}</option>
              ) : (
                documentTypes.map((type) => (
                  <option key={type.key} value={type.key}>
                    {type.label}
                  </option>
                ))
              )}
            </select>
          </label>
          <button
            type="button"
            onClick={() => void persist({ default_document_type: defaultType })}
            disabled={saving || !defaultType}
            className="h-[40px] rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white disabled:opacity-60"
          >
            Personalizar
          </button>
          {defaultDocument?.origin === 'personalizado' ? (
            <button
              type="button"
              onClick={() => void persist({ default_document_type: null })}
              disabled={saving}
              className="h-[40px] rounded-[10px] border border-line px-4 text-[13px] font-bold text-ink-500 hover:bg-surface-hover disabled:opacity-60"
            >
              Heredar
            </button>
          ) : null}
        </div>
        <div className="mt-2 text-[12.5px] text-ink-400">
          Actual: {documentTypeLabel(defaultDocument?.value, documentTypes)}
        </div>
      </GovernanceBlock>

      <GovernanceBlock title="Permitir sobrescribir por documento" pill={<InheritancePill kind="custom" />}>
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-[13px] font-bold text-ink-800">Los autores pueden ajustar cada documento</div>
            <div className="mt-1 text-[12.5px] text-ink-400">
              Este ajuste es propio de la carpeta en el MVP.
            </div>
          </div>
          <Switch
            checked={overrideValue}
            onCheckedChange={(checked) => void persist({ allow_document_override: checked })}
            disabled={saving}
            aria-label="Permitir sobrescribir por documento"
          />
        </div>
      </GovernanceBlock>
    </div>
  )
}

function TytoTab({
  governance,
  status,
  error,
  onRetry,
  saving,
  mutationError,
  onSave,
}: {
  governance: FolderGovernance | null | undefined
  status: 'idle' | 'loading' | 'success' | 'error'
  error: string | null
  onRetry: () => void
  saving: boolean
  mutationError: string | null
  onSave: (fields: { tyto_enabled?: boolean | null }) => Promise<void>
}) {
  const [localError, setLocalError] = useState<string | null>(null)

  async function persist(fields: { tyto_enabled?: boolean | null }) {
    try {
      setLocalError(null)
      await onSave(fields)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : 'Error al guardar Tyto')
    }
  }

  if (status === 'idle' || status === 'loading') {
    return (
      <div className="mt-6 h-[118px] animate-pulse rounded-[13px] border border-line bg-surface" />
    )
  }

  if (status === 'error') {
    return (
      <div className="mt-6 rounded-[13px] border border-danger-bd bg-danger-bg px-5 py-4">
        <p className="text-[12.5px] font-semibold text-danger">{error}</p>
        <button type="button" onClick={onRetry} className="mt-2 text-[12px] font-bold text-ink-700 underline">
          Reintentar Tyto
        </button>
      </div>
    )
  }

  const tyto = governance?.tyto_enabled
  const enabled = Boolean(tyto?.value)

  return (
    <div className="mt-6 max-w-[760px] space-y-3.5">
      {(localError || mutationError) ? (
        <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
          {localError || mutationError}
        </div>
      ) : null}

      <GovernanceBlock
        title="Disponible para consultas"
        pill={
          <InheritancePill
            kind={governancePillKind(tyto?.origin ?? 'base')}
            from={tyto?.from ?? undefined}
          />
        }
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-[13px] font-bold text-ink-800">
              Tyto puede usar esta carpeta para responder consultas
            </div>
            <div className="mt-1 text-[12.5px] text-ink-400">
              Si esta en base o heredado, el valor viene de la jerarquia.
            </div>
          </div>
          <Switch
            checked={enabled}
            onCheckedChange={(checked) => void persist({ tyto_enabled: checked })}
            disabled={saving}
            aria-label="Disponible para consultas Tyto"
          />
        </div>
        {tyto?.origin === 'personalizado' ? (
          <button
            type="button"
            onClick={() => void persist({ tyto_enabled: null })}
            disabled={saving}
            className="mt-4 h-[38px] rounded-[10px] border border-line px-4 text-[13px] font-bold text-ink-500 hover:bg-surface-hover disabled:opacity-60"
          >
            Heredar configuracion
          </button>
        ) : null}
      </GovernanceBlock>
    </div>
  )
}

type FolderPermissionsData = {
  permissions: FolderPermissionsResponse
  roles: OperationalRoleResponse[]
}

function PermissionsTab({ workspaceId, folder }: { workspaceId: string; folder: Folder }) {
  const { status, data, error, reload } = useAsync<FolderPermissionsData>(async () => {
    if (!workspaceId || !folder.id) return undefined
    const [permissions, roles] = await Promise.all([
      getFolderPermissions(folder.id),
      listOperationalRoles(workspaceId),
    ])
    return { permissions, roles }
  }, [workspaceId, folder.id])

  const [inheritsPermissions, setInheritsPermissions] = useState(true)
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [mutationError, setMutationError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!data) return
    setInheritsPermissions(data.permissions.inherits_permissions)
    setSelectedRoleIds(data.permissions.operational_role_ids)
    setMutationError(null)
  }, [data])

  useEffect(() => {
    setSaved(false)
    setMutationError(null)
  }, [folder.id])

  async function handleInheritanceChange(checked: boolean) {
    const previousValue = inheritsPermissions
    setInheritsPermissions(checked)
    setSaving(true)
    setMutationError(null)
    setSaved(false)
    try {
      await updateFolderPermissions(folder.id, { inherits_permissions: checked })
      reload()
    } catch (err) {
      setInheritsPermissions(previousValue)
      setMutationError(err instanceof Error ? err.message : 'Error al actualizar la herencia')
    } finally {
      setSaving(false)
    }
  }

  function toggleRole(roleId: string) {
    setSaved(false)
    setSelectedRoleIds((current) =>
      current.includes(roleId)
        ? current.filter((id) => id !== roleId)
        : [...current, roleId],
    )
  }

  async function saveRoleAccess() {
    setSaving(true)
    setMutationError(null)
    setSaved(false)
    try {
      await updateFolderPermissions(folder.id, {
        inherits_permissions: false,
        operational_role_ids: selectedRoleIds,
      })
      setSaved(true)
      reload()
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : 'Error al guardar los permisos')
    } finally {
      setSaving(false)
    }
  }

  if ((status === 'idle' || status === 'loading') && !data) {
    return (
      <div className="mt-6 max-w-[760px] space-y-3.5">
        <div className="h-[92px] animate-pulse rounded-[13px] border border-line bg-surface" />
        <div className="h-[220px] animate-pulse rounded-[13px] border border-line bg-surface" />
      </div>
    )
  }

  if (status === 'error' && !data) {
    return (
      <div className="mt-6 max-w-[760px] rounded-[13px] border border-danger-bd bg-danger-bg px-5 py-4">
        <p className="text-[12.5px] font-semibold text-danger">{error}</p>
        <button type="button" onClick={reload} className="mt-2 text-[12px] font-bold text-ink-700 underline">
          Reintentar permisos
        </button>
      </div>
    )
  }

  if (!data) return null

  const { permissions, roles } = data
  const effectiveRoles = permissions.operational_role_ids.map((roleId) => {
    const fullRole = roles.find((role) => role.id === roleId)
    const responseRole = permissions.operational_roles.find((role) => role.id === roleId)
    return {
      id: roleId,
      name: fullRole?.name ?? responseRole?.name ?? roleId,
      description: fullRole?.description ?? '',
    }
  })
  const persistedIds = [...permissions.operational_role_ids].sort()
  const selectedIds = [...selectedRoleIds].sort()
  const hasRoleChanges = persistedIds.join('|') !== selectedIds.join('|')

  return (
    <div className="mt-6 max-w-[760px] space-y-3.5">
      {mutationError || (status === 'error' && error) ? (
        <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
          {mutationError || error}
        </div>
      ) : null}

      <div className="rounded-[13px] border border-line bg-surface px-5 py-4 shadow-card">
        <div className="flex items-center justify-between gap-5">
          <div>
            <div className="text-[13px] font-extrabold text-ink-900">Heredar permisos de la carpeta padre</div>
            <div className="mt-1 text-[12.5px] leading-relaxed text-ink-400">
              Usa automáticamente los roles operativos con acceso definidos en la jerarquía.
            </div>
          </div>
          <Switch
            checked={inheritsPermissions}
            onCheckedChange={(checked) => void handleInheritanceChange(checked)}
            disabled={saving}
            aria-label="Heredar permisos de la carpeta padre"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-[13px] border border-line bg-surface shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft bg-surface-hover px-5 py-3.5">
          <div>
            <h2 className="text-[13px] font-extrabold text-ink-900">Roles operativos con acceso</h2>
            <p className="mt-0.5 text-[11.5px] text-ink-400">
              {inheritsPermissions ? 'Acceso efectivo en modo lectura.' : 'Seleccioná los roles que pueden acceder a esta carpeta.'}
            </p>
          </div>
          <InheritancePill
            kind={inheritsPermissions ? 'inherited' : 'custom'}
            from={inheritsPermissions ? permissions.from ?? undefined : undefined}
          />
        </div>

        {inheritsPermissions ? (
          effectiveRoles.length > 0 ? (
            <div className="divide-y divide-line-softer">
              {effectiveRoles.map((role) => (
                <div key={role.id} className="flex items-center gap-3 px-5 py-3.5">
                  <input
                    type="checkbox"
                    checked
                    disabled
                    readOnly
                    aria-label={`Acceso del rol ${role.name}`}
                    className="h-[18px] w-[18px] rounded border-line-input accent-indigo"
                  />
                  <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full bg-indigo-tint text-[11px] font-extrabold uppercase text-indigo">
                    {role.name.slice(0, 2)}
                  </span>
                  <div className="min-w-0">
                    <div className="text-[13px] font-bold text-ink-800">{role.name}</div>
                    {role.description ? (
                      <div className="mt-0.5 truncate text-[11.5px] text-ink-400">{role.description}</div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-5 py-7 text-center text-[12.5px] text-ink-400">
              No hay una restricción por rol operativo heredada.
            </div>
          )
        ) : roles.length > 0 ? (
          <div className="divide-y divide-line-softer">
            {roles.map((role) => {
              const checked = selectedRoleIds.includes(role.id)
              return (
                <label
                  key={role.id}
                  className="flex cursor-pointer items-center gap-3 px-5 py-3.5 transition-colors hover:bg-surface-hover"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleRole(role.id)}
                    disabled={saving}
                    aria-label={`Acceso del rol ${role.name}`}
                    className="h-[18px] w-[18px] rounded border-line-input accent-indigo"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-bold text-ink-800">{role.name}</span>
                    {role.description ? (
                      <span className="mt-0.5 block truncate text-[11.5px] text-ink-400">{role.description}</span>
                    ) : null}
                  </span>
                  <span className="text-[11px] font-semibold text-ink-300">{checked ? 'Con acceso' : 'Sin acceso'}</span>
                </label>
              )
            })}
          </div>
        ) : (
          <div className="px-5 py-7 text-center text-[12.5px] text-ink-400">
            Todavía no hay roles operativos configurados en el workspace.
          </div>
        )}

        {!inheritsPermissions ? (
          <div className="flex items-center justify-between gap-3 border-t border-line-soft px-5 py-3.5">
            <span className="text-[11.5px] font-semibold text-success-fg">{saved ? 'Permisos guardados.' : ''}</span>
            <button
              type="button"
              onClick={() => void saveRoleAccess()}
              disabled={saving || !hasRoleChanges}
              className="h-[40px] rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white disabled:opacity-60"
            >
              {saving ? 'Guardando...' : 'Guardar permisos'}
            </button>
          </div>
        ) : null}
      </div>

      <div className="rounded-[12px] border border-indigo-border bg-indigo-tint px-4 py-3 text-[12.5px] leading-relaxed text-indigo">
        Las capacidades de ver, crear, editar o aprobar dependen del rol de aplicación de cada usuario. En esta carpeta
        solo se define el acceso por rol operativo.
      </div>
    </div>
  )
}

function FolderTreeRow({
  node,
  depth,
  selectedId,
  expanded,
  draggedId,
  dropTargetId,
  onSelect,
  onToggle,
  onDragStart,
  onDragTarget,
  onDropOn,
  onDragEnd,
}: {
  node: FolderNode
  depth: number
  selectedId: string | null
  expanded: Record<string, boolean>
  draggedId: string | null
  dropTargetId: string | null
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onDragStart: (id: string) => void
  onDragTarget: (id: string | null) => void
  onDropOn: (id: string) => void
  onDragEnd: () => void
}) {
  const isOpen = expanded[node.id] ?? depth < 1
  const isSelected = selectedId === node.id
  const hasChildren = node.children.length > 0
  const color = folderColor(node)

  return (
    <>
      <div
        className={
          'flex w-full items-center gap-px rounded-lg ' +
          (dropTargetId === node.id && draggedId !== node.id ? 'bg-indigo-tint/70' : '')
        }
        style={{ paddingLeft: depth * 14 }}
        draggable
        onDragStart={(event) => {
          event.dataTransfer.effectAllowed = 'move'
          event.dataTransfer.setData('text/plain', node.id)
          onDragStart(node.id)
        }}
        onDragOver={(event) => {
          if (!draggedId || draggedId === node.id) return
          event.preventDefault()
          event.dataTransfer.dropEffect = 'move'
          onDragTarget(node.id)
        }}
        onDragEnter={(event) => {
          if (!draggedId || draggedId === node.id) return
          event.preventDefault()
          onDragTarget(node.id)
        }}
        onDrop={(event) => {
          event.preventDefault()
          event.stopPropagation()
          const sourceId = event.dataTransfer.getData('text/plain') || draggedId
          if (!sourceId || sourceId === node.id) return
          onDropOn(node.id)
        }}
        onDragEnd={onDragEnd}
      >
        <button
          type="button"
          onClick={() => hasChildren && onToggle(node.id)}
          disabled={!hasChildren}
          aria-label={isOpen ? `Contraer ${node.name}` : `Expandir ${node.name}`}
          className={
            'grid h-7 w-[18px] flex-shrink-0 place-items-center text-ink-400 transition ' +
            (hasChildren ? 'cursor-pointer hover:text-ink-700' : 'pointer-events-none opacity-0')
          }
        >
          <ChevronRight size={13} strokeWidth={2.6} className={isOpen ? 'rotate-90 transition' : 'transition'} />
        </button>
        <button
          type="button"
          onClick={() => onSelect(node.id)}
          className={
            'flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-[7px] text-[12.5px] transition-colors ' +
            (isSelected
              ? 'bg-indigo-tint font-bold text-ink-800'
              : 'font-semibold text-ink-700 hover:bg-surface-hover')
          }
        >
          <span className="grid h-6 w-6 flex-shrink-0 place-items-center rounded-md" style={{ color, background: `${color}1f` }}>
            <FolderIcon size={14} />
          </span>
          <span className="min-w-0 flex-1 truncate text-left">{node.name}</span>
          <span className="text-[10.5px] font-bold text-ink-300">{node.docs}</span>
        </button>
      </div>
      {isOpen
        ? node.children.map((child) => (
            <FolderTreeRow
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              expanded={expanded}
              draggedId={draggedId}
              dropTargetId={dropTargetId}
              onSelect={onSelect}
              onToggle={onToggle}
              onDragStart={onDragStart}
              onDragTarget={onDragTarget}
              onDropOn={onDropOn}
              onDragEnd={onDragEnd}
            />
          ))
        : null}
    </>
  )
}

export default function FoldersPage() {
  const { selectedWorkspaceId } = useWorkspace()
  const workspaceId = selectedWorkspaceId ?? ''
  const crud = useFolderCrud(workspaceId)
  const { status, data, error, reload } = useAsync(async () => {
    if (!workspaceId) return { folders: [], documents: [] }
    const [folders, documents] = await Promise.all([
      listFolders(workspaceId),
      listDocuments(workspaceId, undefined, 'process'),
    ])
    return { folders, documents }
  }, [workspaceId])

  const folders = data?.folders ?? []
  const documents = data?.documents ?? []
  const tree = useMemo(() => buildTree(folders, countDocumentsByFolder(documents)), [folders, documents])
  const allNodes = useMemo(() => flatten(tree), [tree])

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newParentId, setNewParentId] = useState<string>('')
  const [newColor, setNewColor] = useState(DEFAULT_FOLDER_COLOR)
  const [createError, setCreateError] = useState<string | null>(null)
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)
  const [moveError, setMoveError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('resumen')

  useEffect(() => {
    if (selectedId && allNodes.some((node) => node.id === selectedId)) return
    setSelectedId(allNodes[0]?.id ?? null)
  }, [allNodes, selectedId])

  const selected = useMemo(() => findNode(tree, selectedId), [tree, selectedId])
  const selectedPath = selected?.path?.split('/').join(' > ') || selected?.name || ''
  const isLoading = status === 'idle' || status === 'loading'
  const {
    status: statsStatus,
    data: stats,
    error: statsError,
    reload: reloadStats,
  } = useAsync(async () => {
    if (!selectedId) return undefined
    return getFolderStats(selectedId)
  }, [selectedId])
  const {
    status: governanceStatus,
    data: governance,
    error: governanceError,
    reload: reloadGovernance,
  } = useAsync(async () => {
    if (!selectedId) return undefined
    return getFolderGovernance(selectedId)
  }, [selectedId])
  const {
    status: documentTypesStatus,
    data: documentTypes,
  } = useAsync(async () => {
    if (!workspaceId) return []
    return getDocumentTypes(false)
  }, [workspaceId])

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!newName.trim()) {
      setCreateError('El nombre es requerido')
      return
    }

    try {
      setCreateError(null)
      const created = await crud.createFolder({
        name: newName,
        parentId: newParentId || null,
        color: newColor,
        sortOrder: allNodes.length,
        allFolders: folders,
      })
      setCreateOpen(false)
      setNewName('')
      setNewParentId('')
      setNewColor(DEFAULT_FOLDER_COLOR)
      setSelectedId(created.id)
      await reload()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Error al crear carpeta')
    }
  }

  async function handleDropOn(targetId: string) {
    if (!draggedId || draggedId === targetId) return

    try {
      setMoveError(null)
      await crud.reparentFolder(draggedId, targetId)
      setExpanded((current) => ({ ...current, [targetId]: true }))
      setSelectedId(draggedId)
      await reload()
    } catch {
      setMoveError('No se puede mover la carpeta ahi')
    } finally {
      setDraggedId(null)
      setDropTargetId(null)
    }
  }

  function clearDragState() {
    setDraggedId(null)
    setDropTargetId(null)
  }

  async function handleSaveGeneral(fields: {
    name: string
    path: string
    color: string
    icon: string
    description: string
  }) {
    if (!selected) return
    const updated = await crud.updateFolder(selected.id, {
      name: fields.name,
      path: fields.path,
      color: fields.color,
      icon: fields.icon,
      metadata: { description: fields.description },
    })
    setSelectedId(updated.id)
    await reload()
  }

  async function handleSaveGovernance(fields: {
    default_document_type?: string | null
    tyto_enabled?: boolean | null
    allow_document_override?: boolean
  }) {
    if (!selected) return
    const updated = await crud.updateFolder(selected.id, fields)
    setSelectedId(updated.id)
    await reload()
    reloadGovernance()
  }

  return (
    <div className="flex min-h-full items-stretch">
      <aside className="sticky top-0 max-h-screen w-[280px] flex-shrink-0 self-start overflow-y-auto border-r border-line bg-surface p-3 pt-[22px]">
        <div className="mb-3 flex items-center justify-between px-2">
          <span className="text-[11px] font-bold uppercase tracking-[.08em] text-ink-400">Estructura</span>
          <button
            type="button"
            onClick={() => {
              setCreateError(null)
              setCreateOpen(true)
            }}
            className="grid h-7 w-7 place-items-center rounded-md text-ink-400 hover:bg-surface-hover hover:text-ink-700"
            aria-label="Nueva carpeta"
          >
            <Plus size={15} />
          </button>
        </div>

        {isLoading ? (
          <div className="space-y-2 px-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-ink-100" />
            ))}
          </div>
        ) : null}

        {status === 'error' ? (
          <div className="mx-2 rounded-[11px] border border-danger-bd bg-danger-bg px-3 py-3">
            <p className="text-[12.5px] font-semibold text-danger">{error}</p>
            <button type="button" onClick={reload} className="mt-2 text-[12px] font-bold text-ink-700 underline">
              Reintentar
            </button>
          </div>
        ) : null}

        {moveError ? (
          <div className="mx-2 mb-2 rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
            {moveError}
          </div>
        ) : null}

        {status === 'success' && tree.length === 0 ? (
          <div className="mx-2 rounded-[11px] border border-line bg-surface-hover px-3 py-4 text-[12.5px] text-ink-500">
            Todavia no hay carpetas configuradas.
          </div>
        ) : null}

        <div className="space-y-0.5">
          {tree.map((node) => (
            <FolderTreeRow
              key={node.id}
              node={node}
              depth={0}
              selectedId={selectedId}
              expanded={expanded}
              draggedId={draggedId}
              dropTargetId={dropTargetId}
              onSelect={setSelectedId}
              onToggle={(id) => setExpanded((current) => ({ ...current, [id]: !(current[id] ?? true) }))}
              onDragStart={(id) => {
                setMoveError(null)
                setDraggedId(id)
              }}
              onDragTarget={setDropTargetId}
              onDropOn={(targetId) => void handleDropOn(targetId)}
              onDragEnd={clearDragState}
            />
          ))}
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-8 pb-[50px] pt-7">
        {selected ? (
          <>
            <div className="flex items-start gap-3.5">
              <span
                className="grid h-12 w-12 flex-shrink-0 place-items-center rounded-[13px]"
                style={{ color: folderColor(selected), background: `${folderColor(selected)}1f` }}
              >
                <FolderIcon size={24} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-xs text-ink-400">{selectedPath}</div>
                <div className="flex items-center gap-2.5">
                  <h1 className="truncate text-[23px] font-extrabold text-ink-900">{selected.name}</h1>
                  <span className="inline-flex items-center gap-1.5 rounded-pill border border-green-border bg-green-bg px-2.5 py-[3px] text-[11px] font-bold text-green-text">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-bright" />
                    Activa
                  </span>
                </div>
                <div className="mt-1 text-[13px] text-ink-400">
                  {folderDescription(selected)}
                </div>
              </div>
            </div>

            <StatsStrip stats={stats} status={statsStatus} error={statsError} onRetry={reloadStats} />

            <Tabs
              id="folders-detail"
              value={activeTab}
              onValueChange={setActiveTab}
              items={FOLDER_TABS}
              className="mt-6"
              tablistClassName="border-line"
            >
              <TabsContent id="folders-detail" value="resumen" current={activeTab}>
                <SummaryTab workspaceId={workspaceId} folder={selected} stats={stats} />
              </TabsContent>
              <TabsContent id="folders-detail" value="general" current={activeTab}>
                <GeneralTab
                  folder={selected}
                  folders={folders}
                  saving={crud.saving}
                  error={crud.error}
                  onSave={handleSaveGeneral}
                />
              </TabsContent>
              <TabsContent id="folders-detail" value="gobierno" current={activeTab}>
                <GovernanceTab
                  governance={governance}
                  status={governanceStatus}
                  error={governanceError}
                  onRetry={reloadGovernance}
                  documentTypes={documentTypes ?? []}
                  documentTypesStatus={documentTypesStatus}
                  saving={crud.saving}
                  mutationError={crud.error}
                  onSave={handleSaveGovernance}
                />
              </TabsContent>
              <TabsContent id="folders-detail" value="tyto" current={activeTab}>
                <TytoTab
                  governance={governance}
                  status={governanceStatus}
                  error={governanceError}
                  onRetry={reloadGovernance}
                  saving={crud.saving}
                  mutationError={crud.error}
                  onSave={handleSaveGovernance}
                />
              </TabsContent>
              <TabsContent id="folders-detail" value="permisos" current={activeTab}>
                <PermissionsTab workspaceId={workspaceId} folder={selected} />
              </TabsContent>
              {FOLDER_TABS.filter((tab) => !['resumen', 'general', 'gobierno', 'tyto', 'permisos'].includes(tab.value)).map((tab) => (
                <TabsContent key={tab.value} id="folders-detail" value={tab.value} current={activeTab}>
                  <div className="mt-6 rounded-[13px] border border-dashed border-line-input bg-surface-hover px-6 py-10 text-center text-[13px] text-ink-400">
                    Contenido de {tab.label} se conectara en los siguientes tickets.
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </>
        ) : (
          <div className="rounded-[13px] border border-line bg-surface px-5 py-6 text-[13px] text-ink-500">
            Selecciona una carpeta para ver su configuracion.
          </div>
        )}
      </main>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="Nueva carpeta">
        <form onSubmit={handleCreate} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-bold text-ink-900">Nombre</span>
            <input
              value={newName}
              onChange={(event) => {
                setNewName(event.target.value)
                setCreateError(null)
              }}
              className="h-[42px] w-full rounded-[10px] border border-line-input px-3.5 text-sm outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
              autoComplete="off"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-[13px] font-bold text-ink-900">Carpeta padre</span>
            <select
              value={newParentId}
              onChange={(event) => setNewParentId(event.target.value)}
              className="h-[42px] w-full rounded-[10px] border border-line-input px-3 text-sm outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
            >
              <option value="">Raiz</option>
              {allNodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.path || node.name}
                </option>
              ))}
            </select>
          </label>

          <div>
            <span className="mb-2 block text-[13px] font-bold text-ink-900">Color</span>
            <div className="flex flex-wrap gap-2">
              {FOLDER_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setNewColor(color)}
                  aria-label={`Color ${color}`}
                  aria-pressed={newColor === color}
                  className={
                    'h-7 w-7 rounded-full border-2 transition ' +
                    (newColor === color ? 'scale-110 border-ink-900' : 'border-transparent hover:scale-105')
                  }
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>

          {(createError || crud.error) ? (
            <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
              {createError || crud.error}
            </div>
          ) : null}

          <div className="flex justify-end gap-2.5 pt-1">
            <button
              type="button"
              onClick={() => setCreateOpen(false)}
              disabled={crud.saving}
              className="h-[40px] rounded-[10px] border border-line px-4 text-[13px] font-bold text-ink-500 hover:bg-surface-hover disabled:opacity-60"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={crud.saving}
              className="h-[40px] rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white disabled:opacity-60"
            >
              {crud.saving ? 'Creando...' : 'Crear carpeta'}
            </button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
