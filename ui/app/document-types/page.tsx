'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  FileText, Plus, X, Check,
  ClipboardList, BookOpen, FileCheck, FilePen,
  ScrollText, Layers, ShieldCheck, BarChart2,
  Wrench, HelpCircle, Receipt, FolderKanban,
  AlertCircle,
} from 'lucide-react'
import * as LucideIcons from 'lucide-react'
import {
  getDocumentTypes,
  updateDocumentType,
  createDocumentType,
  type DocumentType,
  type DocumentTypeBehaviors,
} from '@/lib/api'
import { useAsync } from '@/hooks/useAsync'
import { Switch, InheritancePill } from '@/shared/ui/components'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { canAdministerWorkspace } from '@/lib/adminGating'

// ---- Behaviors (allowlist de 5 keys) ----

type BehaviorKey = 'versionado' | 'aprobacion' | 'tyto' | 'relaciones' | 'metadatos'

interface BehaviorDef {
  key: BehaviorKey
  label: string
  description: string
}

const BEHAVIORS: BehaviorDef[] = [
  {
    key: 'versionado',
    label: 'Versionado',
    description: 'Permite mantener borradores, revisiones y versiones oficiales.',
  },
  {
    key: 'aprobacion',
    label: 'Aprobación',
    description: 'Exige flujo de revisión antes de publicar como oficial.',
  },
  {
    key: 'tyto',
    label: 'Disponible para Tyto',
    description: 'Habilita el tipo documental como fuente para consultas de IA.',
  },
  {
    key: 'relaciones',
    label: 'Relaciones',
    description: 'Permite detectar vínculos con otros documentos y entidades.',
  },
  {
    key: 'metadatos',
    label: 'Extraer metadatos',
    description: 'Activa extracción de atributos estructurados del documento.',
  },
]

// ---- Color palette (igual que en carpetas) ----

const COLOR_PALETTE = [
  '#48569C',
  '#2F9E62',
  '#C99A2E',
  '#2E8B8B',
  '#8B5CC2',
  '#CB4242',
]

const DEFAULT_COLOR = COLOR_PALETTE[0]

// ---- Icon registry ----
// Subset de iconos relevantes para tipos documentales.

const ICON_OPTIONS: { name: string; label: string }[] = [
  { name: 'FileText', label: 'Documento' },
  { name: 'ClipboardList', label: 'Lista' },
  { name: 'BookOpen', label: 'Manual' },
  { name: 'FileCheck', label: 'Aprobado' },
  { name: 'FilePen', label: 'Editable' },
  { name: 'ScrollText', label: 'Contrato' },
  { name: 'Layers', label: 'Versiones' },
  { name: 'ShieldCheck', label: 'Política' },
  { name: 'BarChart2', label: 'Análisis' },
  { name: 'Wrench', label: 'Técnico' },
  { name: 'HelpCircle', label: 'FAQ' },
  { name: 'Receipt', label: 'Presupuesto' },
  { name: 'FolderKanban', label: 'Proyecto' },
  { name: 'AlertCircle', label: 'Aviso' },
]

function resolveIcon(name: string | null, size: number, className?: string) {
  if (!name) return <FileText size={size} className={className} aria-hidden="true" />
  const Icon = (LucideIcons as unknown as Record<string, React.ComponentType<{ size?: number; className?: string; 'aria-hidden'?: string }>>)[name]
  if (!Icon) return <FileText size={size} className={className} aria-hidden="true" />
  return <Icon size={size} className={className} aria-hidden="true" />
}

// ---- Helpers ----

function resolveBehaviors(b: DocumentType['behaviors']): Record<BehaviorKey, boolean> {
  return {
    versionado: b?.versionado ?? false,
    aprobacion: b?.aprobacion ?? false,
    tyto: b?.tyto ?? false,
    relaciones: b?.relaciones ?? false,
    metadatos: b?.metadatos ?? false,
  }
}

function typeDisplayColor(type: DocumentType, index: number): string {
  return type.color ?? COLOR_PALETTE[index % COLOR_PALETTE.length]
}

function skeletonRows() {
  return [0, 1, 2, 3, 4].map((i) => (
    <div key={i} className="flex items-center gap-2.5 rounded-[10px] px-3 py-2.5">
      <div className="h-8 w-8 animate-pulse rounded-lg bg-ink-100" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="h-3.5 w-2/3 animate-pulse rounded bg-ink-100" />
        <div className="h-2.5 w-1/3 animate-pulse rounded bg-ink-100" />
      </div>
    </div>
  ))
}

// ---- Icon picker ----

function IconPicker({
  value,
  onChange,
}: {
  value: string | null
  onChange: (name: string) => void
}) {
  return (
    <div className="grid grid-cols-7 gap-1.5">
      {ICON_OPTIONS.map((opt) => {
        const selected = (value ?? 'FileText') === opt.name
        return (
          <button
            key={opt.name}
            type="button"
            title={opt.label}
            aria-label={opt.label}
            aria-pressed={selected}
            onClick={() => onChange(opt.name)}
            className={
              'grid h-8 w-8 place-items-center rounded-md border transition-colors ' +
              (selected
                ? 'border-indigo bg-indigo-tint text-indigo'
                : 'border-line bg-surface text-ink-500 hover:bg-surface-hover')
            }
          >
            {resolveIcon(opt.name, 15)}
          </button>
        )
      })}
    </div>
  )
}

// ---- Color picker ----

function ColorPicker({
  value,
  onChange,
}: {
  value: string | null
  onChange: (color: string) => void
}) {
  const current = value ?? DEFAULT_COLOR
  return (
    <div className="flex flex-wrap gap-2">
      {COLOR_PALETTE.map((hex) => {
        const selected = current === hex
        return (
          <button
            key={hex}
            type="button"
            aria-label={`Color ${hex}`}
            aria-pressed={selected}
            onClick={() => onChange(hex)}
            className="grid h-7 w-7 place-items-center rounded-full border-2 transition-all"
            style={{
              background: hex,
              borderColor: selected ? hex : 'transparent',
              boxShadow: selected ? `0 0 0 2px white, 0 0 0 4px ${hex}` : undefined,
            }}
          >
            {selected && <Check size={13} className="text-white" aria-hidden="true" />}
          </button>
        )
      })}
    </div>
  )
}

// ---- Nuevo tipo: inline form in sidebar ----

interface NewTypeFormProps {
  onSave: (type: DocumentType) => void
  onCancel: () => void
}

function NewTypeForm({ onSave, onCancel }: NewTypeFormProps) {
  const [label, setLabel] = useState('')
  const [icon, setIcon] = useState<string>('FileText')
  const [color, setColor] = useState<string>(DEFAULT_COLOR)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = label.trim()
    if (!trimmed) {
      setError('El nombre es obligatorio.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await createDocumentType({ label: trimmed, icon, color })
      onSave(created)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo crear el tipo.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mb-3 rounded-[11px] border border-indigo-border bg-indigo-tint px-3 py-3"
    >
      <div className="mb-2.5 text-[11.5px] font-extrabold uppercase tracking-[.08em] text-indigo">
        Nuevo tipo
      </div>

      <label className="mb-1 block text-[11px] font-semibold text-ink-600">
        Nombre
      </label>
      <input
        type="text"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Ej. Instrucción de trabajo"
        maxLength={80}
        autoFocus
        className="mb-3 h-8 w-full rounded-md border border-ink-300 bg-white px-2.5 text-[12.5px] text-ink-800 placeholder:text-ink-300 focus:border-indigo focus:outline-none focus:ring-[3px] focus:ring-indigo-tint"
      />

      <div className="mb-2 text-[11px] font-semibold text-ink-600">Icono</div>
      <div className="mb-3">
        <IconPicker value={icon} onChange={setIcon} />
      </div>

      <div className="mb-2 text-[11px] font-semibold text-ink-600">Color</div>
      <div className="mb-3">
        <ColorPicker value={color} onChange={setColor} />
      </div>

      {error && (
        <p className="mb-2 text-[11.5px] font-semibold text-danger">{error}</p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="flex h-8 flex-1 items-center justify-center rounded-md bg-action text-[12px] font-bold text-white transition-colors hover:bg-action-hover disabled:opacity-50"
        >
          {saving ? 'Guardando...' : 'Crear'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-surface text-ink-400 transition-colors hover:bg-surface-hover"
          aria-label="Cancelar"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>
    </form>
  )
}

// ---- Page ----

export default function DocumentTypesPage() {
  const { selectedWorkspace, platformRoles } = useWorkspace()
  const canAdminister = canAdministerWorkspace({
    platformRoles,
    workspaceRole: selectedWorkspace?.role,
  })

  const { status, data, error, reload } = useAsync(
    () => getDocumentTypes(true),
    []
  )

  const [types, setTypes] = useState<DocumentType[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [savingKey, setSavingKey] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [showNewForm, setShowNewForm] = useState(false)

  useEffect(() => {
    if (status !== 'success') return
    const nextTypes = data ?? []
    setTypes(nextTypes)
    setSelectedId((current) => {
      if (current && nextTypes.some((t) => t.id === current)) return current
      return nextTypes[0]?.id ?? null
    })
  }, [data, status])

  const selected = useMemo(
    () => types.find((t) => t.id === selectedId) ?? types[0] ?? null,
    [selectedId, types]
  )

  const selectedIndex = selected
    ? Math.max(0, types.findIndex((t) => t.id === selected.id))
    : 0

  async function toggleBehavior(type: DocumentType, key: BehaviorKey, checked: boolean) {
    const prev = types
    const nextBehaviors: DocumentTypeBehaviors = {
      ...resolveBehaviors(type.behaviors),
      [key]: checked,
    }
    setTypes((cur) =>
      cur.map((t) => (t.id === type.id ? { ...t, behaviors: nextBehaviors } : t))
    )
    setSavingKey(key)
    setSaveError(null)
    try {
      const updated = await updateDocumentType(type.id, { behaviors: nextBehaviors })
      setTypes((cur) => cur.map((t) => (t.id === type.id ? { ...t, ...updated } : t)))
    } catch (err) {
      setTypes(prev)
      setSaveError(err instanceof Error ? err.message : 'No se pudo guardar el cambio.')
    } finally {
      setSavingKey(null)
    }
  }

  async function toggleActive(type: DocumentType, checked: boolean) {
    const prev = types
    setTypes((cur) =>
      cur.map((t) => (t.id === type.id ? { ...t, is_active: checked } : t))
    )
    setSaveError(null)
    try {
      const updated = await updateDocumentType(type.id, { is_active: checked })
      setTypes((cur) => cur.map((t) => (t.id === type.id ? { ...t, ...updated } : t)))
    } catch (err) {
      setTypes(prev)
      setSaveError(err instanceof Error ? err.message : 'No se pudo guardar el cambio.')
    }
  }

  async function saveIconColor(type: DocumentType, icon: string | null, color: string | null) {
    const prev = types
    setTypes((cur) => cur.map((t) => (t.id === type.id ? { ...t, icon, color } : t)))
    setSaveError(null)
    try {
      const updated = await updateDocumentType(type.id, { icon, color })
      setTypes((cur) => cur.map((t) => (t.id === type.id ? { ...t, ...updated } : t)))
    } catch (err) {
      setTypes(prev)
      setSaveError(err instanceof Error ? err.message : 'No se pudo guardar el cambio.')
    }
  }

  const isLoading = status === 'idle' || status === 'loading'

  // Bloqueo si el usuario no puede administrar
  if (!canAdminister) {
    return (
      <div className="flex min-h-full items-center justify-center p-8">
        <p className="text-[13px] text-ink-500">
          No tenés permisos para gestionar tipos de documento.
        </p>
      </div>
    )
  }

  return (
    <div className="flex min-h-full items-stretch" data-module="process">
      {/* Sidebar */}
      <aside className="w-[300px] flex-shrink-0 border-r border-line bg-surface p-5">
        <div className="mb-1 text-xs font-bold uppercase tracking-[.08em] text-ink-400">
          Administración
        </div>
        <h1 className="mb-4 text-[19px] font-extrabold text-ink-900">
          Tipos de documento
        </h1>

        {showNewForm ? (
          <NewTypeForm
            onSave={(created) => {
              setTypes((cur) => [...cur, created])
              setSelectedId(created.id)
              setShowNewForm(false)
            }}
            onCancel={() => setShowNewForm(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setShowNewForm(true)}
            className="mb-3 flex w-full items-center justify-center gap-2 rounded-[10px] border border-dashed border-line-input bg-surface py-2.5 text-[12.5px] font-bold text-ink-400 transition-colors hover:border-indigo hover:text-indigo"
          >
            <Plus size={15} aria-hidden="true" />
            Nuevo tipo
          </button>
        )}

        <div className="flex flex-col gap-1">
          {isLoading ? skeletonRows() : null}

          {status === 'error' ? (
            <div className="rounded-[11px] border border-danger-bd bg-danger-bg px-3 py-3">
              <p className="text-[12.5px] font-semibold text-danger">{error}</p>
              <button
                type="button"
                onClick={reload}
                className="mt-2 text-[12px] font-bold text-ink-700 underline"
              >
                Reintentar
              </button>
            </div>
          ) : null}

          {status === 'success' && types.length === 0 ? (
            <div className="rounded-[11px] border border-line bg-surface-hover px-3 py-4 text-[12.5px] text-ink-500">
              Todavía no hay tipos documentales configurados.
            </div>
          ) : null}

          {types.map((type, index) => {
            const isActive = selected?.id === type.id
            const color = typeDisplayColor(type, index)
            return (
              <button
                key={type.id}
                type="button"
                onClick={() => {
                  setSelectedId(type.id)
                  setSaveError(null)
                }}
                className={
                  'flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-left transition-colors ' +
                  (isActive ? 'bg-indigo-tint' : 'hover:bg-surface-hover') +
                  (type.is_active ? '' : ' opacity-50')
                }
              >
                <span
                  className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg"
                  style={{ color, background: `${color}1f` }}
                  aria-hidden="true"
                >
                  {resolveIcon(type.icon, 16)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-bold text-ink-800">
                    {type.label}
                  </span>
                  <span className="block truncate text-[11px] text-ink-300">
                    {type.key}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      </aside>

      {/* Main panel */}
      <main className="min-w-0 max-w-[780px] flex-1 px-8 pb-[50px] pt-7">
        {selected ? (
          <SelectedTypePanel
            type={selected}
            index={selectedIndex}
            savingKey={savingKey}
            saveError={saveError}
            onToggleBehavior={(key, checked) => void toggleBehavior(selected, key, checked)}
            onToggleActive={(checked) => void toggleActive(selected, checked)}
            onSaveIconColor={(icon, color) => void saveIconColor(selected, icon, color)}
          />
        ) : (
          !isLoading && (
            <div className="rounded-[13px] border border-line bg-surface px-5 py-6 text-[13px] text-ink-500">
              Seleccioná un tipo documental para ver su configuración.
            </div>
          )
        )}
      </main>
    </div>
  )
}

// ---- Selected type panel ----

interface SelectedTypePanelProps {
  type: DocumentType
  index: number
  savingKey: string | null
  saveError: string | null
  onToggleBehavior: (key: BehaviorKey, checked: boolean) => void
  onToggleActive: (checked: boolean) => void
  onSaveIconColor: (icon: string | null, color: string | null) => void
}

function SelectedTypePanel({
  type,
  index,
  savingKey,
  saveError,
  onToggleBehavior,
  onToggleActive,
  onSaveIconColor,
}: SelectedTypePanelProps) {
  const color = typeDisplayColor(type, index)

  // Local icon/color state (saved on change)
  const [localIcon, setLocalIcon] = useState<string>(type.icon ?? 'FileText')
  const [localColor, setLocalColor] = useState<string>(type.color ?? DEFAULT_COLOR)

  // Sync when type changes (user selects another)
  useEffect(() => {
    setLocalIcon(type.icon ?? 'FileText')
    setLocalColor(type.color ?? DEFAULT_COLOR)
  }, [type.id, type.icon, type.color])

  const behaviors = resolveBehaviors(type.behaviors)

  const inheritancePillKind = type.origin === 'default' ? 'base' as const : 'custom' as const

  return (
    <>
      {/* Header */}
      <div className="flex items-center gap-3.5">
        <span
          className="grid h-12 w-12 flex-shrink-0 place-items-center rounded-[13px]"
          style={{ color, background: `${color}1f` }}
          aria-hidden="true"
        >
          {resolveIcon(type.icon, 24)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-[22px] font-extrabold text-ink-900">
              {type.label}
            </h2>
            <InheritancePill kind={inheritancePillKind} />
          </div>
          <div className="mt-0.5 font-mono text-[11.5px] text-ink-400">{type.key}</div>
        </div>
        {/* Active toggle */}
        <div className="flex flex-shrink-0 items-center gap-2">
          <span className="text-[11.5px] font-semibold text-ink-500">
            {type.is_active ? 'Activo' : 'Inactivo'}
          </span>
          <Switch
            checked={type.is_active}
            onCheckedChange={onToggleActive}
            aria-label={`${type.is_active ? 'Desactivar' : 'Activar'} tipo ${type.label}`}
          />
        </div>
      </div>

      {saveError && (
        <div className="mt-4 rounded-[11px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
          {saveError}
        </div>
      )}

      {/* Apariencia */}
      <div className="mt-7">
        <div className="mb-1 text-[13px] font-extrabold text-ink-900">Apariencia</div>
        <p className="mb-4 text-[12px] text-ink-400">
          El icono y color identifican visualmente el tipo en toda la plataforma.
        </p>
        <div className="rounded-[13px] border border-line bg-surface px-4 py-4">
          <div className="mb-3 flex items-center gap-3">
            <span
              className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-[11px]"
              style={{ color: localColor, background: `${localColor}1f` }}
              aria-hidden="true"
            >
              {resolveIcon(localIcon, 20)}
            </span>
            <span className="text-[13px] font-semibold text-ink-700">Vista previa</span>
          </div>

          <div className="mb-2 text-[11.5px] font-semibold text-ink-600">Icono</div>
          <div className="mb-4">
            <IconPicker
              value={localIcon}
              onChange={(name) => {
                setLocalIcon(name)
                onSaveIconColor(name, localColor)
              }}
            />
          </div>

          <div className="mb-2 text-[11.5px] font-semibold text-ink-600">Color</div>
          <ColorPicker
            value={localColor}
            onChange={(hex) => {
              setLocalColor(hex)
              onSaveIconColor(localIcon, hex)
            }}
          />
        </div>
      </div>

      {/* Comportamiento */}
      <div className="mt-7">
        <div className="mb-1 text-[13px] font-extrabold text-ink-900">Comportamiento</div>
        <p className="mb-4 text-[12px] text-ink-400">
          Cada tipo activa funciones específicas del modelo documental.
        </p>

        <div className="grid gap-2.5 sm:grid-cols-2">
          {BEHAVIORS.map((beh) => {
            const checked = behaviors[beh.key]
            const isSaving = savingKey === beh.key
            const disabled = Boolean(savingKey)
            return (
              <div
                key={beh.key}
                className={
                  'flex min-h-[76px] items-center justify-between gap-4 rounded-[12px] border px-4 py-3 transition-colors ' +
                  (checked
                    ? 'border-indigo-light bg-indigo-tint'
                    : 'border-line bg-surface')
                }
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={
                        'text-[13px] font-bold ' +
                        (checked ? 'text-indigo' : 'text-ink-700')
                      }
                    >
                      {beh.label}
                    </span>
                    {isSaving && (
                      <span className="text-[10.5px] font-bold text-ink-400">
                        guardando
                      </span>
                    )}
                  </div>
                  <p className="mt-1 line-clamp-2 text-[11.5px] text-ink-400">
                    {beh.description}
                  </p>
                </div>
                <Switch
                  checked={checked}
                  disabled={disabled}
                  onCheckedChange={(next) => onToggleBehavior(beh.key, next)}
                  aria-label={`${beh.label} para ${type.label}`}
                />
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}
