'use client'

import { useState } from 'react'
import { AlertCircle, Check, GitMerge, Inbox, Loader2 } from 'lucide-react'

import {
  KNOWLEDGE_OBJECT_TYPE_OPTIONS,
  RELATION_TYPE_OPTIONS,
  RelationCandidateRow,
} from '@/components/relations/RelationCandidateRow'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useAsync } from '@/hooks/useAsync'
import {
  useCanApproveDocuments,
  useCanManageWorkspace,
  useCanRejectDocuments,
  useHasPermission,
} from '@/hooks/useHasPermission'
import {
  confirmRelation,
  editRelation,
  getWorkspaceRelations,
  listFolders,
  mergeKnowledgeObject,
  rejectRelation,
  searchKnowledgeObjects,
  type KnowledgeObject,
  type KnowledgeObjectType,
  type RelationType,
  type WorkspaceRelationItem,
} from '@/lib/api'
import { Button, Dialog } from '@/shared/ui/components'

const PAGE_SIZE = 25

export default function RelationsInboxPage() {
  const { loading: workspaceLoading } = useWorkspace()
  const { canManage: canAdminister, loading: canAdministerLoading } = useCanManageWorkspace()
  const { hasPermission: canApprove } = useCanApproveDocuments()
  const { hasPermission: canReject } = useCanRejectDocuments()
  const { hasPermission: canEdit } = useHasPermission('documents.create')

  const [typeFilter, setTypeFilter] = useState('')
  const [folderFilter, setFolderFilter] = useState('')
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(() => new Set())
  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const [editingRelation, setEditingRelation] = useState<WorkspaceRelationItem | null>(null)
  const [editRelationType, setEditRelationType] = useState<RelationType>('relacionado_con')
  const [editTargetType, setEditTargetType] = useState<KnowledgeObjectType>('sistema')
  const [editTargetId, setEditTargetId] = useState('')
  const [targetQuery, setTargetQuery] = useState('')
  const [targetOptions, setTargetOptions] = useState<KnowledgeObject[]>([])
  const [targetSearchLoading, setTargetSearchLoading] = useState(false)
  const [mergeRelation, setMergeRelation] = useState<WorkspaceRelationItem | null>(null)

  const inbox = useAsync(
    () =>
      canAdminister
        ? getWorkspaceRelations({
            status: 'candidate',
            type: typeFilter || undefined,
            folder_id: folderFilter || undefined,
            page,
            page_size: PAGE_SIZE,
          })
        : Promise.resolve(undefined),
    [canAdminister, typeFilter, folderFilter, page]
  )
  const folders = useAsync(
    () => (canAdminister ? listFolders() : Promise.resolve(undefined)),
    [canAdminister]
  )

  const items = (inbox.data?.items ?? []).filter((item) => !dismissedIds.has(item.id))
  const selectedOnPage = items.filter((item) => selectedIds.has(item.id))

  function dismiss(ids: string[]) {
    setDismissedIds((current) => {
      const next = new Set(current)
      ids.forEach((id) => next.add(id))
      return next
    })
    setSelectedIds((current) => {
      const next = new Set(current)
      ids.forEach((id) => next.delete(id))
      return next
    })
  }

  async function runAction(
    key: string,
    action: () => Promise<unknown>,
    successMessage: string,
    idsToDismiss: string[] = []
  ): Promise<boolean> {
    try {
      setBusyAction(key)
      setActionError(null)
      setActionMessage(null)
      await action()
      if (idsToDismiss.length > 0) dismiss(idsToDismiss)
      setActionMessage(successMessage)
      return true
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'No se pudo completar la acción')
      return false
    } finally {
      inbox.reload()
      setBusyAction(null)
    }
  }

  function changeFilter(kind: 'type' | 'folder', value: string) {
    if (kind === 'type') setTypeFilter(value)
    else setFolderFilter(value)
    setPage(1)
    setSelectedIds(new Set())
  }

  function toggleSelected(id: string, selected: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (selected) next.add(id)
      else next.delete(id)
      return next
    })
  }

  async function confirmSelected() {
    const ids = selectedOnPage.map((item) => item.id)
    if (ids.length === 0) return
    await runAction(
      'confirm-selected',
      () => Promise.all(ids.map((id) => confirmRelation(id))),
      `${ids.length} relaciones confirmadas.`,
      ids
    )
  }

  async function loadTargetOptions(
    type: KnowledgeObjectType,
    query = '',
    selectedTargetId = editTargetId
  ) {
    try {
      setTargetSearchLoading(true)
      const found = await searchKnowledgeObjects({ type, q: query })
      setTargetOptions(found)
      if (found.length > 0 && !found.some((item) => item.id === selectedTargetId)) {
        setEditTargetId(found[0].id)
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'No se pudieron buscar entidades')
    } finally {
      setTargetSearchLoading(false)
    }
  }

  function openEditDialog(relation: WorkspaceRelationItem) {
    const safeRelationType = RELATION_TYPE_OPTIONS.some(
      (item) => item.value === relation.relation_type
    )
      ? (relation.relation_type as RelationType)
      : 'relacionado_con'
    const safeTargetType = KNOWLEDGE_OBJECT_TYPE_OPTIONS.some(
      (item) => item.value === relation.target.type
    )
      ? (relation.target.type as KnowledgeObjectType)
      : 'sistema'

    setEditingRelation(relation)
    setEditRelationType(safeRelationType)
    setEditTargetType(safeTargetType)
    setEditTargetId(relation.target.id)
    setTargetQuery('')
    setTargetOptions([
      {
        id: relation.target.id,
        type: relation.target.type,
        canonical_name: relation.target.name,
        normalized_name: relation.target.name.toLowerCase(),
        description: null,
        aliases: [],
      },
    ])
    void loadTargetOptions(safeTargetType, '', relation.target.id)
  }

  async function saveEdit() {
    if (!editingRelation || !editTargetId) return
    const succeeded = await runAction(
      `edit:${editingRelation.id}`,
      () =>
        editRelation(editingRelation.id, {
          relation_type: editRelationType,
          target_type: editTargetType,
          target_id: editTargetId,
        }),
      'Relación actualizada.'
    )
    if (succeeded) setEditingRelation(null)
  }

  async function mergeDuplicate() {
    const duplicate = mergeRelation?.possible_duplicate_of
    if (!mergeRelation || !duplicate) return
    const succeeded = await runAction(
      `merge:${mergeRelation.id}`,
      () => mergeKnowledgeObject(mergeRelation.target.id, { into_id: duplicate.id }),
      `“${mergeRelation.target.name}” se unió con “${duplicate.name}”.`
    )
    if (succeeded) setMergeRelation(null)
  }

  if (workspaceLoading || canAdministerLoading) {
    return (
      <main className="mx-auto max-w-6xl px-8 py-12">
        <div className="h-40 animate-pulse rounded-lg bg-ink-100" aria-busy="true" />
      </main>
    )
  }

  if (!canAdminister) {
    return (
      <main className="mx-auto max-w-4xl px-8 py-12">
        <div className="rounded-lg border border-danger-bd bg-danger-bg p-6 text-danger">
          No tenés permisos para administrar las relaciones del workspace.
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-6xl px-8 pb-16 pt-8">
      <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-indigo">
            <Inbox className="h-5 w-5" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-wide">Bandeja global</span>
          </div>
          <h1 className="text-h1 text-ink-900">Revisión de relaciones</h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-500">
            Curá las conexiones candidatas de todos los documentos del workspace,
            ordenadas por confianza.
          </p>
        </div>
        {canApprove && selectedOnPage.length > 0 && (
          <Button onClick={confirmSelected} disabled={busyAction !== null}>
            {busyAction === 'confirm-selected' ? (
              <Loader2 className="animate-spin" aria-hidden="true" />
            ) : (
              <Check aria-hidden="true" />
            )}
            Confirmar seleccionadas ({selectedOnPage.length})
          </Button>
        )}
      </div>

      <section className="mb-6 grid gap-4 rounded-lg border border-ink-200 bg-white p-4 shadow-sm sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-500">
            Tipo de relación
          </span>
          <select
            value={typeFilter}
            onChange={(event) => changeFilter('type', event.target.value)}
            className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm"
          >
            <option value="">Todos los tipos</option>
            {RELATION_TYPE_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-500">
            Carpeta
          </span>
          <select
            value={folderFilter}
            onChange={(event) => changeFilter('folder', event.target.value)}
            className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm"
          >
            <option value="">Todas las carpetas</option>
            {(folders.data ?? []).map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.path || folder.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      {actionError && (
        <div
          role="alert"
          className="mb-5 flex gap-2 rounded-lg border border-danger-bd bg-danger-bg p-3 text-sm text-danger"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {actionError}
        </div>
      )}
      {actionMessage && (
        <div
          role="status"
          className="mb-5 rounded-lg border border-success-bd bg-success-bg p-3 text-sm text-success-fg"
        >
          {actionMessage}
        </div>
      )}

      {inbox.status === 'loading' && !inbox.data && (
        <div aria-busy="true" className="space-y-3">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-28 animate-pulse rounded-lg bg-ink-100" />
          ))}
        </div>
      )}

      {inbox.error && (
        <div className="rounded-lg border border-danger-bd bg-danger-bg p-5 text-sm text-danger">
          <p className="mb-3">No se pudo cargar la bandeja: {inbox.error}</p>
          <Button variant="secondary" size="sm" onClick={inbox.reload}>
            Reintentar
          </Button>
        </div>
      )}

      {inbox.status === 'success' && items.length === 0 && (
        <div className="rounded-lg border border-dashed border-ink-300 bg-white px-6 py-16 text-center">
          <Inbox className="mx-auto mb-3 h-9 w-9 text-ink-300" aria-hidden="true" />
          <h2 className="text-h2 text-ink-800">No hay relaciones pendientes</h2>
          <p className="mt-1 text-sm text-ink-500">
            No encontramos candidatas para los filtros seleccionados.
          </p>
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="mb-3 flex items-center justify-between text-xs text-ink-500">
            <span>{inbox.data?.total ?? items.length} relaciones pendientes</span>
            <span>Confianza: mayor a menor</span>
          </div>
          <div className="space-y-3">
            {items.map((relation) => (
              <RelationCandidateRow
                key={relation.id}
                relationType={relation.relation_type}
                relation={relation}
                sourceDocument={relation.document}
                canApprove={canApprove ?? false}
                canReject={canReject ?? false}
                canEdit={canEdit ?? false}
                busy={busyAction !== null}
                selectable={canApprove ?? false}
                selected={selectedIds.has(relation.id)}
                onSelectedChange={(selected) => toggleSelected(relation.id, selected)}
                onEdit={() => openEditDialog(relation)}
                onMerge={() => setMergeRelation(relation)}
                onConfirm={() =>
                  void runAction(
                    `confirm:${relation.id}`,
                    () => confirmRelation(relation.id),
                    `Relación con “${relation.target.name}” confirmada.`,
                    [relation.id]
                  )
                }
                onReject={() =>
                  void runAction(
                    `reject:${relation.id}`,
                    () => rejectRelation(relation.id),
                    `Relación con “${relation.target.name}” rechazada.`,
                    [relation.id]
                  )
                }
              />
            ))}
          </div>

          {(inbox.data?.total_pages ?? 0) > 1 && (
            <div className="mt-6 flex items-center justify-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1 || busyAction !== null}
              >
                Anterior
              </Button>
              <span className="text-sm text-ink-500">
                Página {page} de {inbox.data?.total_pages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((current) => current + 1)}
                disabled={page >= (inbox.data?.total_pages ?? 1) || busyAction !== null}
              >
                Siguiente
              </Button>
            </div>
          )}
        </>
      )}

      <Dialog
        open={editingRelation !== null}
        onClose={() => setEditingRelation(null)}
        title="Editar relación"
      >
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">
              Tipo de relación
            </span>
            <select
              value={editRelationType}
              onChange={(event) => setEditRelationType(event.target.value as RelationType)}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm"
            >
              {RELATION_TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">
              Tipo de entidad
            </span>
            <select
              value={editTargetType}
              onChange={(event) => {
                const value = event.target.value as KnowledgeObjectType
                setEditTargetType(value)
                setEditTargetId('')
                void loadTargetOptions(value, targetQuery, '')
              }}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm"
            >
              {KNOWLEDGE_OBJECT_TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <div>
            <label
              htmlFor="inbox-relation-target-search"
              className="mb-1.5 block text-sm font-semibold text-ink-700"
            >
              Buscar entidad destino
            </label>
            <div className="flex gap-2">
              <input
                id="inbox-relation-target-search"
                value={targetQuery}
                onChange={(event) => setTargetQuery(event.target.value)}
                placeholder="Nombre de la entidad"
                className="h-[38px] min-w-0 flex-1 rounded-md border border-ink-300 px-3 text-sm"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => loadTargetOptions(editTargetType, targetQuery)}
                disabled={targetSearchLoading}
              >
                {targetSearchLoading ? (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                ) : (
                  'Buscar'
                )}
              </Button>
            </div>
          </div>
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">
              Entidad destino
            </span>
            <select
              value={editTargetId}
              onChange={(event) => setEditTargetId(event.target.value)}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm"
            >
              {targetOptions.length === 0 && <option value="">Sin resultados</option>}
              {targetOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.canonical_name}
                </option>
              ))}
            </select>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setEditingRelation(null)}>
              Cancelar
            </Button>
            <Button onClick={saveEdit} disabled={!editTargetId || busyAction !== null}>
              Guardar cambios
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={mergeRelation !== null}
        onClose={() => setMergeRelation(null)}
        title="Unir entidades duplicadas"
      >
        <p className="text-sm text-ink-700">
          La entidad <strong>{mergeRelation?.target.name}</strong> se unirá dentro de{' '}
          <strong>{mergeRelation?.possible_duplicate_of?.name}</strong>. Todas sus relaciones
          serán reapuntadas y el duplicado desaparecerá.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setMergeRelation(null)}>
            Cancelar
          </Button>
          <Button onClick={mergeDuplicate} disabled={busyAction !== null}>
            <GitMerge aria-hidden="true" />
            Unir entidades
          </Button>
        </div>
      </Dialog>
    </main>
  )
}
