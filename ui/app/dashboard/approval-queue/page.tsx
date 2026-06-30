'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { FileText, ChevronRight, RefreshCw, Inbox } from 'lucide-react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserRole } from '@/hooks/useUserRole'
import { useUserId } from '@/hooks/useUserId'
import { Button } from '@/shared/ui/components'
import {
  listDocumentsPendingApproval,
  Document,
  listFolders,
  Folder,
} from '@/lib/api'

// ── Helpers ──────────────────────────────────────────────────────────────────

function folderPath(folders: Folder[], folderId: string | undefined): string {
  if (!folderId) return 'Sin carpeta'
  const folder = folders.find((f) => f.id === folderId)
  return folder ? folder.name : 'Sin carpeta'
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `hace ${mins} min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs} h`
  const days = Math.floor(hrs / 24)
  return `hace ${days} d`
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-[15px]">
      <div className="h-11 w-11 flex-shrink-0 animate-pulse rounded-[11px] bg-ink-100" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 w-2/5 animate-pulse rounded bg-ink-100" />
        <div className="h-3 w-3/5 animate-pulse rounded bg-ink-100" />
      </div>
      <div className="h-6 w-20 animate-pulse rounded-pill bg-ink-100" />
    </div>
  )
}

// ── Badge "Esperando" ─────────────────────────────────────────────────────────

function EsperandoBadge() {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-pill border border-amber-border bg-amber-bg px-3 py-[5px] text-[11px] font-extrabold text-amber"
      aria-label="Estado: esperando aprobación"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-amber" aria-hidden="true" />
      Esperando
    </span>
  )
}

// ── Document type label ───────────────────────────────────────────────────────

function typeLabel(raw: string | undefined): string {
  if (!raw) return ''
  const map: Record<string, string> = {
    process: 'Procedimiento',
    policy: 'Política',
    recipe: 'Receta',
  }
  return map[raw] ?? raw
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ApprovalQueuePage() {
  const router = useRouter()
  const { selectedWorkspaceId } = useWorkspace()
  const { role } = useUserRole()
  const userId = useUserId()

  const [documents, setDocuments] = useState<Document[]>([])
  const [folders, setFolders] = useState<Folder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!selectedWorkspaceId || !userId) {
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      setError(null)
      const [docs, fols] = await Promise.all([
        listDocumentsPendingApproval(selectedWorkspaceId, userId),
        listFolders(selectedWorkspaceId),
      ])
      setDocuments(docs)
      setFolders(fols)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }, [selectedWorkspaceId, userId])

  useEffect(() => {
    load()
  }, [load])

  // ── Guard: permisos ───────────────────────────────────────────────────────
  const allowedRoles = ['owner', 'admin', 'approver', 'superadmin']
  if (role && !allowedRoles.includes(role)) {
    return (
      <div data-module="process" className="mx-auto max-w-[820px] px-8 pb-[60px] pt-7">
        <div className="rounded-lg border border-danger-bd bg-danger-bg p-5">
          <p className="text-sm text-danger">
            No tenés permisos para ver esta página. Tu rol actual es:{' '}
            <span className="font-semibold">{role}</span>.
          </p>
        </div>
      </div>
    )
  }

  // ── Guard: sin workspace ──────────────────────────────────────────────────
  if (!selectedWorkspaceId) {
    return (
      <div data-module="process" className="mx-auto max-w-[820px] px-8 pb-[60px] pt-7">
        <div className="rounded-lg border border-warning-bd bg-warning-bg p-5">
          <p className="text-sm text-warning">
            Seleccioná un espacio de trabajo para ver la bandeja de aprobación.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div data-module="process" className="mx-auto max-w-[820px] px-8 pb-[60px] pt-7">
      {/* Header */}
      <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">
        Bandeja de aprobación
      </div>
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[25px] font-extrabold leading-tight text-ink-900">Por aprobar</h1>
          <p className="mt-1.5 text-[13px] text-ink-400">
            Documentos que esperan tu decisión. Entrá a resolver, no a buscar.
          </p>
        </div>
        {!loading && (
          <button
            onClick={load}
            aria-label="Actualizar bandeja"
            className="mb-0.5 flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold text-ink-500 hover:bg-ink-100 hover:text-ink-800 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Actualizar
          </button>
        )}
      </div>

      {/* Contador de pendientes */}
      {!loading && !error && documents.length > 0 && (
        <div className="mt-4 flex items-center gap-2">
          <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-warning px-1.5 text-[10.5px] font-extrabold text-white">
            {documents.length}
          </span>
          <span className="text-[12.5px] text-ink-500">
            {documents.length === 1 ? 'documento pendiente' : 'documentos pendientes'}
          </span>
        </div>
      )}

      {/* Error inline */}
      {error && (
        <div className="mt-5 rounded-lg border border-danger-bd bg-danger-bg p-4">
          <p className="mb-3 text-sm text-danger">{error}</p>
          <Button variant="danger" size="sm" onClick={load}>
            Reintentar
          </Button>
        </div>
      )}

      {/* Lista */}
      <div className="mt-6 flex flex-col gap-2.5">
        {loading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : !error && documents.length === 0 ? (
          /* Estado vacío */
          <div className="flex flex-col items-center gap-3 rounded-[13px] border border-line bg-surface px-8 py-14 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-xl bg-ink-100">
              <Inbox className="h-6 w-6 text-ink-400" aria-hidden="true" />
            </span>
            <p className="text-[14.5px] font-semibold text-ink-700">Todo al día</p>
            <p className="max-w-xs text-[13px] text-ink-400">
              No hay documentos pendientes de aprobación. Volvé más tarde.
            </p>
          </div>
        ) : (
          documents.map((doc) => (
            <button
              key={doc.id}
              onClick={() => router.push(`/dashboard/approval-queue/${doc.id}/review`)}
              className="flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-[15px] text-left transition-colors hover:border-indigo-light hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
              aria-label={`Revisar documento: ${doc.name}`}
            >
              {/* Icono */}
              <span
                className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-[11px] bg-amber-bg text-amber"
                aria-hidden="true"
              >
                <FileText className="h-5 w-5" />
              </span>

              {/* Info */}
              <div className="min-w-0 flex-1">
                <div className="truncate text-[14.5px] font-extrabold text-ink-900">
                  {doc.name}
                </div>
                <div className="mt-0.5 truncate text-xs text-ink-400">
                  {folderPath(folders, doc.folder_id)}
                  {doc.document_type && (
                    <> &middot; {typeLabel(doc.document_type)}</>
                  )}
                  {doc.created_at && (
                    <> &middot; {relativeTime(doc.created_at)}</>
                  )}
                </div>
              </div>

              {/* Badge estado */}
              <EsperandoBadge />

              {/* Chevron */}
              <ChevronRight
                className="h-4 w-4 flex-shrink-0 text-ink-200"
                aria-hidden="true"
              />
            </button>
          ))
        )}
      </div>
    </div>
  )
}
