'use client'

import { useState } from 'react'
import {
  AlertCircle,
  Check,
  GitMerge,
  Link2,
  Network,
  Plus,
  Sparkles,
} from 'lucide-react'

import {
  HIGH_CONFIDENCE_THRESHOLD,
  KNOWLEDGE_OBJECT_TYPE_OPTIONS,
  RELATION_TYPE_OPTIONS,
  RelationCandidateRow,
  relationTypeLabel,
  targetTypeLabel,
} from '@/components/relations/RelationCandidateRow'
import {
  confirmRelation,
  createKnowledgeObject,
  editRelation,
  getDocumentImpact,
  getDocumentRelations,
  mergeKnowledgeObject,
  rejectRelation,
  searchKnowledgeObjects,
  suggestDocumentRelations,
  type DocumentRelationItem,
  type KnowledgeObject,
  type KnowledgeObjectType,
  type RelationType,
} from '@/lib/api'
import { useAsync } from '@/hooks/useAsync'
import { Button, Dialog, Spinner } from '@/shared/ui/components'

interface DocumentRelationsPanelProps {
  documentId: string
  canApprove?: boolean
  canReject?: boolean
  canEdit?: boolean
}

export function DocumentRelationsPanel({
  documentId,
  canApprove = true,
  canReject = true,
  canEdit = true,
}: DocumentRelationsPanelProps) {
  const relations = useAsync(
    () => getDocumentRelations(documentId, 'candidate'),
    [documentId]
  )
  const impact = useAsync(() => getDocumentImpact(documentId), [documentId])

  const [busyAction, setBusyAction] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(() => new Set())

  const [editingRelation, setEditingRelation] = useState<DocumentRelationItem | null>(null)
  const [editRelationType, setEditRelationType] = useState<RelationType>('relacionado_con')
  const [editTargetType, setEditTargetType] = useState<KnowledgeObjectType>('sistema')
  const [editTargetId, setEditTargetId] = useState('')
  const [targetQuery, setTargetQuery] = useState('')
  const [targetOptions, setTargetOptions] = useState<KnowledgeObject[]>([])
  const [targetSearchLoading, setTargetSearchLoading] = useState(false)

  const [mergeRelation, setMergeRelation] = useState<DocumentRelationItem | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createType, setCreateType] = useState<KnowledgeObjectType>('sistema')
  const [createName, setCreateName] = useState('')
  const [createDescription, setCreateDescription] = useState('')

  const groups = (relations.data?.groups ?? [])
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !dismissedIds.has(item.id)),
    }))
    .filter((group) => group.items.length > 0)
  const candidateItems = groups.flatMap((group) => group.items)
  const highConfidenceItems = candidateItems.filter(
    (item) => (item.confidence ?? 0) >= HIGH_CONFIDENCE_THRESHOLD
  )
  const impactedNodeCount =
    (impact.data?.affected_documents.length ?? 0) +
    (impact.data?.affected_entities.length ?? 0)

  async function runAction(
    key: string,
    action: () => Promise<unknown>,
    message: string,
    idsToDismiss: string[] = []
  ): Promise<boolean> {
    try {
      setBusyAction(key)
      setActionError(null)
      setActionMessage(null)
      await action()
      if (idsToDismiss.length > 0) {
        setDismissedIds((current) => {
          const next = new Set(current)
          idsToDismiss.forEach((id) => next.add(id))
          return next
        })
      }
      setActionMessage(message)
      return true
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'No se pudo completar la acción')
      return false
    } finally {
      relations.reload()
      impact.reload()
      setBusyAction(null)
    }
  }

  async function handleSuggest() {
    const succeeded = await runAction(
      'suggest',
      () => suggestDocumentRelations(documentId),
      'La detección terminó y la lista fue actualizada.'
    )
    if (succeeded) setDismissedIds(new Set())
  }

  async function handleConfirmAll() {
    await runAction(
      'confirm-all',
      () => Promise.all(highConfidenceItems.map((item) => confirmRelation(item.id))),
      `${highConfidenceItems.length} relaciones de alta confianza confirmadas.`,
      highConfidenceItems.map((item) => item.id)
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

  function openEditDialog(relationType: string, relation: DocumentRelationItem) {
    const safeRelationType = RELATION_TYPE_OPTIONS.some((item) => item.value === relationType)
      ? (relationType as RelationType)
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

  async function handleSaveEdit() {
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

  async function handleMerge() {
    const duplicate = mergeRelation?.possible_duplicate_of
    if (!mergeRelation || !duplicate) return
    const succeeded = await runAction(
      `merge:${mergeRelation.id}`,
      () => mergeKnowledgeObject(mergeRelation.target.id, { into_id: duplicate.id }),
      `“${mergeRelation.target.name}” se unió con “${duplicate.name}”.`
    )
    if (succeeded) setMergeRelation(null)
  }

  async function handleCreate() {
    const canonicalName = createName.trim()
    if (!canonicalName) return
    const succeeded = await runAction(
      'create-entity',
      () =>
        createKnowledgeObject({
          type: createType,
          canonical_name: canonicalName,
          description: createDescription.trim() || undefined,
        }),
      `Entidad “${canonicalName}” creada.`
    )
    if (succeeded) {
      setCreateOpen(false)
      setCreateName('')
      setCreateDescription('')
    }
  }

  return (
    <section className="mb-8 rounded-[14px] border border-ink-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-ink-200 px-6 py-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Link2 className="h-5 w-5 text-indigo" aria-hidden="true" />
            <h2 className="text-h2 text-ink-900">Relaciones semánticas</h2>
          </div>
          <p className="max-w-2xl text-sm text-ink-500">
            Revisá las conexiones sugeridas por el sistema. Nada se incorpora a la red
            oficial hasta que una persona lo confirme.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setCreateOpen(true)}
              disabled={busyAction !== null}
            >
              <Plus aria-hidden="true" />
              Crear entidad
            </Button>
          )}
          {canEdit && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleSuggest}
              disabled={busyAction !== null}
            >
              {busyAction === 'suggest' ? (
                <Spinner size="sm" aria-hidden="true" />
              ) : (
                <Sparkles aria-hidden="true" />
              )}
              Detectar relaciones
            </Button>
          )}
        </div>
      </div>

      <div className="space-y-5 p-6">
        {actionError && (
          <div role="alert" className="flex gap-2 rounded-lg border border-danger-bd bg-danger-bg p-3 text-sm text-danger">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{actionError}</span>
          </div>
        )}
        {actionMessage && (
          <div role="status" className="rounded-lg border border-success-bd bg-success-bg p-3 text-sm text-success-fg">
            {actionMessage}
          </div>
        )}

        <div className="rounded-lg border border-indigo-border bg-indigo-tint p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Network className="mt-0.5 h-5 w-5 text-indigo" aria-hidden="true" />
              <div>
                <p className="text-sm font-semibold text-ink-800">
                  Este documento toca {impactedNodeCount} {impactedNodeCount === 1 ? 'nodo' : 'nodos'}
                </p>
                <p className="text-xs text-ink-500">
                  Impacto calculado sobre relaciones ya confirmadas.
                </p>
              </div>
            </div>
            {canApprove && highConfidenceItems.length > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleConfirmAll}
                disabled={busyAction !== null}
              >
                {busyAction === 'confirm-all' ? (
                  <Spinner size="sm" aria-hidden="true" />
                ) : (
                  <Check aria-hidden="true" />
                )}
                Confirmar todo ({highConfidenceItems.length})
              </Button>
            )}
          </div>

          {impact.status === 'loading' && !impact.data && (
            <p className="mt-3 text-xs text-ink-400">Calculando impacto…</p>
          )}
          {impact.error && (
            <p className="mt-3 text-xs text-danger">No se pudo cargar el impacto: {impact.error}</p>
          )}
          {impact.data && impactedNodeCount > 0 && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {impact.data.affected_documents.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-400">
                    Documentos afectados
                  </p>
                  <ul className="space-y-1 text-sm text-ink-700">
                    {impact.data.affected_documents.map((item) => (
                      <li key={item.id}>{item.name}</li>
                    ))}
                  </ul>
                </div>
              )}
              {impact.data.affected_entities.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-400">
                    Entidades afectadas
                  </p>
                  <ul className="space-y-1 text-sm text-ink-700">
                    {impact.data.affected_entities.map((item) => (
                      <li key={item.id}>
                        {item.name}{' '}
                        <span className="text-xs text-ink-400">· {targetTypeLabel(item.type)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {relations.status === 'loading' && !relations.data && (
          <div aria-busy="true" className="space-y-3">
            {[0, 1, 2].map((item) => (
              <div key={item} className="h-24 animate-pulse rounded-lg bg-ink-100" />
            ))}
          </div>
        )}

        {relations.error && (
          <div className="rounded-lg border border-danger-bd bg-danger-bg p-5 text-sm text-danger">
            <p className="mb-3">No se pudieron cargar las relaciones: {relations.error}</p>
            <Button variant="secondary" size="sm" onClick={relations.reload}>
              Reintentar
            </Button>
          </div>
        )}

        {relations.status === 'success' && candidateItems.length === 0 && (
          <div className="rounded-lg border border-dashed border-ink-300 px-6 py-12 text-center">
            <Link2 className="mx-auto mb-3 h-8 w-8 text-ink-300" aria-hidden="true" />
            <h3 className="text-sm font-semibold text-ink-800">No hay relaciones candidatas</h3>
            <p className="mx-auto mt-1 max-w-md text-sm text-ink-500">
              Podés volver a analizar la versión aprobada con “Detectar relaciones”.
            </p>
          </div>
        )}

        {groups.map((group) => (
          <div key={group.relation_type}>
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink-800">
                {relationTypeLabel(group.relation_type)}
              </h3>
              <span className="text-xs text-ink-400">{group.items.length}</span>
            </div>
            <div className="space-y-2">
              {group.items.map((relation) => (
                <RelationCandidateRow
                  key={relation.id}
                  relationType={group.relation_type}
                  relation={relation}
                  canApprove={canApprove}
                  canReject={canReject}
                  canEdit={canEdit}
                  busy={busyAction !== null}
                  onEdit={() => openEditDialog(group.relation_type, relation)}
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
          </div>
        ))}
      </div>

      <Dialog
        open={editingRelation !== null}
        onClose={() => setEditingRelation(null)}
        title="Editar relación"
      >
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">Tipo de relación</span>
            <select
              value={editRelationType}
              onChange={(event) => setEditRelationType(event.target.value as RelationType)}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm text-ink-800"
            >
              {RELATION_TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">Tipo de entidad</span>
            <select
              value={editTargetType}
              onChange={(event) => {
                const value = event.target.value as KnowledgeObjectType
                setEditTargetType(value)
                setEditTargetId('')
                void loadTargetOptions(value, targetQuery)
              }}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm text-ink-800"
            >
              {KNOWLEDGE_OBJECT_TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>

          <div>
            <label htmlFor="relation-target-search" className="mb-1.5 block text-sm font-semibold text-ink-700">
              Buscar entidad destino
            </label>
            <div className="flex gap-2">
              <input
                id="relation-target-search"
                value={targetQuery}
                onChange={(event) => setTargetQuery(event.target.value)}
                className="h-[38px] min-w-0 flex-1 rounded-md border border-ink-300 px-3 text-sm"
                placeholder="Nombre de la entidad"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => loadTargetOptions(editTargetType, targetQuery)}
                disabled={targetSearchLoading}
              >
                {targetSearchLoading ? <Spinner size="sm" aria-hidden="true" /> : 'Buscar'}
              </Button>
            </div>
          </div>

          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">Entidad destino</span>
            <select
              value={editTargetId}
              onChange={(event) => setEditTargetId(event.target.value)}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm text-ink-800"
            >
              {targetOptions.length === 0 && <option value="">Sin resultados</option>}
              {targetOptions.map((item) => (
                <option key={item.id} value={item.id}>{item.canonical_name}</option>
              ))}
            </select>
          </label>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setEditingRelation(null)}>Cancelar</Button>
            <Button
              onClick={handleSaveEdit}
              disabled={!editTargetId || busyAction !== null}
            >
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
          <Button variant="secondary" onClick={() => setMergeRelation(null)}>Cancelar</Button>
          <Button onClick={handleMerge} disabled={busyAction !== null}>
            <GitMerge aria-hidden="true" />
            Unir entidades
          </Button>
        </div>
      </Dialog>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="Crear entidad">
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">Tipo</span>
            <select
              value={createType}
              onChange={(event) => setCreateType(event.target.value as KnowledgeObjectType)}
              className="h-[38px] w-full rounded-md border border-ink-300 bg-white px-3 text-sm text-ink-800"
            >
              {KNOWLEDGE_OBJECT_TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">Nombre</span>
            <input
              value={createName}
              onChange={(event) => setCreateName(event.target.value)}
              className="h-[38px] w-full rounded-md border border-ink-300 px-3 text-sm"
              placeholder="Ej. SAP ERP"
              maxLength={300}
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink-700">Descripción opcional</span>
            <textarea
              value={createDescription}
              onChange={(event) => setCreateDescription(event.target.value)}
              className="min-h-24 w-full rounded-md border border-ink-300 px-3 py-2 text-sm"
            />
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancelar</Button>
            <Button
              variant="create"
              onClick={handleCreate}
              disabled={!createName.trim() || busyAction !== null}
            >
              Crear entidad
            </Button>
          </div>
        </div>
      </Dialog>
    </section>
  )
}
