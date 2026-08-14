// components/tyto/TytoConversationsPanel.tsx
// Lista de "mis conversaciones" con Tyto: buscador, retomar, renombrar, anclar y
// borrar. Estrictamente personal — este panel nunca recibe ni pinta el id de otro
// usuario; el backend ya acota la lista al usuario autenticado.
'use client'

import { useId, useState } from 'react'
import { Check, MessageSquareText, Pencil, Pin, PinOff, Search, Trash2, X } from 'lucide-react'
import { Button, Dialog, Skeleton } from '@/shared/ui/components'
import { cn } from '@/shared/ui/cn'
import type { TytoSessionSummary } from '@/lib/api'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'recién'
  if (mins < 60) return `hace ${mins} min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs} h`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `hace ${days} d`
  return new Date(iso).toLocaleDateString('es-UY', { day: '2-digit', month: 'short' })
}

function fallbackTitle(session: TytoSessionSummary): string {
  return session.title?.trim() || 'Conversación sin título'
}

function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 rounded-lg px-3 py-2.5" aria-hidden="true">
      <div className="min-w-0 flex-1 space-y-1.5">
        <Skeleton className="h-3.5 w-3/4" />
        <Skeleton className="h-3 w-1/3" />
      </div>
    </div>
  )
}

function TytoConversationRow({
  session,
  active,
  pending,
  onSelect,
  onRename,
  onTogglePin,
  onRequestDelete,
}: {
  session: TytoSessionSummary
  active: boolean
  pending: boolean
  onSelect: () => void
  onRename: (title: string) => void
  onTogglePin: () => void
  onRequestDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(session.title ?? '')

  function startEditing(e: React.MouseEvent) {
    e.stopPropagation()
    setDraft(session.title ?? '')
    setEditing(true)
  }

  function commitEditing() {
    const trimmed = draft.trim()
    setEditing(false)
    if (trimmed && trimmed !== (session.title ?? '')) onRename(trimmed)
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1.5 rounded-lg border border-action bg-white px-2.5 py-2">
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitEditing()
            if (e.key === 'Escape') setEditing(false)
          }}
          onClick={(e) => e.stopPropagation()}
          aria-label="Título de la conversación"
          className="h-7 min-w-0 flex-1 bg-transparent text-[13px] font-semibold text-ink-800 outline-none"
        />
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            commitEditing()
          }}
          aria-label="Guardar título"
          className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-800"
        >
          <Check size={14} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            setEditing(false)
          }}
          aria-label="Cancelar"
          className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-800"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'group relative flex items-center gap-2 rounded-lg px-2.5 py-2 transition-colors',
        active ? 'bg-accent-tint' : 'hover:bg-ink-100',
        pending && 'pointer-events-none opacity-50'
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? 'true' : undefined}
        className="min-w-0 flex-1 text-left focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
      >
        <div className="flex items-center gap-1.5">
          {session.pinned && (
            <Pin size={11} className="flex-shrink-0 text-accent-ink" aria-hidden="true" />
          )}
          <span
            className={cn(
              'truncate text-[13px] font-bold',
              active ? 'text-accent-ink' : 'text-ink-800'
            )}
          >
            {fallbackTitle(session)}
          </span>
        </div>
        <div className="mt-0.5 truncate text-[11.5px] text-ink-400">
          {session.message_count} {session.message_count === 1 ? 'mensaje' : 'mensajes'} ·{' '}
          {relativeTime(session.updated_at)}
        </div>
      </button>

      {/* Acciones: siempre visibles en touch (sin hover), aparecen al hover/foco en desktop. */}
      <div className="flex flex-shrink-0 items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onTogglePin()
          }}
          aria-label={session.pinned ? 'Desanclar conversación' : 'Anclar conversación'}
          title={session.pinned ? 'Desanclar' : 'Anclar'}
          className="grid h-8 w-8 place-items-center rounded-md text-ink-400 hover:bg-ink-150 hover:text-ink-700"
        >
          {session.pinned ? <PinOff size={13} aria-hidden="true" /> : <Pin size={13} aria-hidden="true" />}
        </button>
        <button
          type="button"
          onClick={startEditing}
          aria-label="Renombrar conversación"
          title="Renombrar"
          className="grid h-8 w-8 place-items-center rounded-md text-ink-400 hover:bg-ink-150 hover:text-ink-700"
        >
          <Pencil size={13} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onRequestDelete()
          }}
          aria-label="Eliminar conversación"
          title="Eliminar"
          className="grid h-8 w-8 place-items-center rounded-md text-ink-400 hover:bg-danger-bg hover:text-danger"
        >
          <Trash2 size={13} aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

export function TytoConversationsPanel({
  sessions,
  loading,
  error,
  onRetry,
  searchValue,
  onSearchChange,
  activeSessionId,
  pendingIds,
  actionError,
  onDismissActionError,
  onSelect,
  onRename,
  onTogglePin,
  onDelete,
  className,
}: {
  sessions: TytoSessionSummary[]
  loading: boolean
  error: string | null
  onRetry: () => void
  searchValue: string
  onSearchChange: (value: string) => void
  activeSessionId: string | null
  /** Ids con una acción (renombrar/anclar/borrar) en vuelo — se muestran atenuados. */
  pendingIds: Set<string>
  actionError: string | null
  onDismissActionError: () => void
  onSelect: (session: TytoSessionSummary) => void
  onRename: (session: TytoSessionSummary, title: string) => void
  onTogglePin: (session: TytoSessionSummary) => void
  onDelete: (session: TytoSessionSummary) => void
  className?: string
}) {
  const [toDelete, setToDelete] = useState<TytoSessionSummary | null>(null)
  const isSearching = searchValue.trim().length > 0
  const searchInputId = useId()

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div className="flex-shrink-0 px-3 pb-2 pt-3">
        <div className="mb-2 px-1 text-[11px] font-extrabold uppercase tracking-[.06em] text-ink-400">
          Mis conversaciones
        </div>
        <div className="relative">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400"
            aria-hidden="true"
          />
          <label htmlFor={searchInputId} className="sr-only">
            Buscar en mis conversaciones
          </label>
          <input
            id={searchInputId}
            type="search"
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Buscar conversaciones…"
            className="h-9 w-full rounded-md border border-ink-200 bg-white pl-8 pr-8 text-[12.5px] text-ink-800 placeholder:text-ink-400 outline-none focus:border-action focus:ring-[3px] focus:ring-action-ring"
          />
          {isSearching && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              aria-label="Limpiar búsqueda"
              className="absolute right-1.5 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded text-ink-400 hover:bg-ink-100 hover:text-ink-700"
            >
              <X size={13} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="mx-3 mb-2 flex items-start justify-between gap-2 rounded-md border border-danger-bd bg-danger-bg px-2.5 py-2 text-[11.5px] text-danger">
          <span>{actionError}</span>
          <button
            type="button"
            onClick={onDismissActionError}
            aria-label="Descartar aviso"
            className="flex-shrink-0 hover:opacity-70"
          >
            <X size={12} aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {loading ? (
          <div className="flex flex-col gap-1">
            <RowSkeleton />
            <RowSkeleton />
            <RowSkeleton />
            <RowSkeleton />
          </div>
        ) : error ? (
          <div className="mx-1 rounded-lg border border-danger-bd bg-danger-bg p-3">
            <p className="mb-2 text-[12.5px] text-danger">{error}</p>
            <Button variant="danger" size="sm" onClick={onRetry}>
              Reintentar
            </Button>
          </div>
        ) : sessions.length === 0 ? (
          isSearching ? (
            <div className="mx-1 flex flex-col items-center gap-2 rounded-lg border border-dashed border-line-input px-4 py-8 text-center">
              <p className="text-[12.5px] leading-relaxed text-ink-500">
                No encontramos conversaciones que coincidan con &ldquo;{searchValue.trim()}&rdquo;.
              </p>
              <button
                type="button"
                onClick={() => onSearchChange('')}
                className="text-[12px] font-bold text-ink-700 underline underline-offset-2"
              >
                Ver todas mis conversaciones
              </button>
            </div>
          ) : (
            <div className="mx-1 flex flex-col items-center gap-2.5 rounded-lg px-4 py-10 text-center">
              <span className="grid h-10 w-10 place-items-center rounded-full bg-ink-100">
                <MessageSquareText size={18} className="text-ink-400" aria-hidden="true" />
              </span>
              <p className="text-[12.5px] leading-relaxed text-ink-500">
                Preguntale algo a Tyto y tus conversaciones van a aparecer acá.
              </p>
            </div>
          )
        ) : (
          <div className="flex flex-col gap-0.5">
            {sessions.map((session) => (
              <TytoConversationRow
                key={session.id}
                session={session}
                active={session.id === activeSessionId}
                pending={pendingIds.has(session.id)}
                onSelect={() => onSelect(session)}
                onRename={(title) => onRename(session, title)}
                onTogglePin={() => onTogglePin(session)}
                onRequestDelete={() => setToDelete(session)}
              />
            ))}
          </div>
        )}
      </div>

      <Dialog
        open={toDelete !== null}
        onClose={() => setToDelete(null)}
        title="Eliminar conversación"
        maxWidth="max-w-sm"
      >
        <p className="text-sm text-ink-700">
          ¿Eliminar &ldquo;{toDelete ? fallbackTitle(toDelete) : ''}&rdquo;? Esta acción no se puede
          deshacer.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" size="sm" onClick={() => setToDelete(null)}>
            Cancelar
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => {
              if (toDelete) onDelete(toDelete)
              setToDelete(null)
            }}
          >
            Eliminar
          </Button>
        </div>
      </Dialog>
    </div>
  )
}
