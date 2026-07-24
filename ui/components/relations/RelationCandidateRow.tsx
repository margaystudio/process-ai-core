'use client'

import { Check, GitMerge, Pencil, X } from 'lucide-react'

import type {
  DocumentRelationItem,
  KnowledgeObjectType,
  RelationType,
  WorkspaceRelationDocument,
} from '@/lib/api'
import { Badge, Button } from '@/shared/ui/components'

export const HIGH_CONFIDENCE_THRESHOLD = 0.85

export const RELATION_TYPE_OPTIONS: Array<{ value: RelationType; label: string }> = [
  { value: 'usa', label: 'Usa' },
  { value: 'requiere', label: 'Requiere' },
  { value: 'genera', label: 'Genera' },
  { value: 'relacionado_con', label: 'Relacionado con' },
  { value: 'describe', label: 'Describe' },
  { value: 'aplica_a', label: 'Aplica a' },
  { value: 'depende_de', label: 'Depende de' },
  { value: 'reemplaza_a', label: 'Reemplaza a' },
  { value: 'ejecutado_por', label: 'Ejecutado por' },
  { value: 'aprobado_por', label: 'Aprobado por' },
  { value: 'ubicado_en', label: 'Ubicado en' },
]

export const KNOWLEDGE_OBJECT_TYPE_OPTIONS: Array<{
  value: KnowledgeObjectType
  label: string
}> = [
  { value: 'sistema', label: 'Sistema' },
  { value: 'rol', label: 'Rol' },
  { value: 'area', label: 'Área' },
  { value: 'equipo', label: 'Equipo' },
  { value: 'formulario', label: 'Formulario' },
  { value: 'proceso', label: 'Proceso' },
  { value: 'ubicacion', label: 'Ubicación' },
  { value: 'normativa', label: 'Normativa' },
]

const RELATION_LABELS = Object.fromEntries(
  RELATION_TYPE_OPTIONS.map(({ value, label }) => [value, label])
) as Record<string, string>

export function relationTypeLabel(type: string): string {
  return RELATION_LABELS[type] ?? type.replaceAll('_', ' ')
}

export function targetTypeLabel(type: string): string {
  return (
    KNOWLEDGE_OBJECT_TYPE_OPTIONS.find((item) => item.value === type)?.label ??
    (type === 'documento' || type === 'document' ? 'Documento' : type)
  )
}

function confidenceLabel(confidence: number | null): string {
  if (confidence === null) return 'Sin confianza'
  return `${Math.round(confidence * 100)}% confianza`
}

interface RelationCandidateRowProps {
  relationType: string
  relation: DocumentRelationItem
  sourceDocument?: WorkspaceRelationDocument
  canApprove?: boolean
  canReject?: boolean
  canEdit?: boolean
  busy?: boolean
  selectable?: boolean
  selected?: boolean
  onSelectedChange?: (selected: boolean) => void
  onConfirm: () => void
  onReject: () => void
  onEdit: () => void
  onMerge: () => void
}

export function RelationCandidateRow({
  relationType,
  relation,
  sourceDocument,
  canApprove = true,
  canReject = true,
  canEdit = true,
  busy = false,
  selectable = false,
  selected = false,
  onSelectedChange,
  onConfirm,
  onReject,
  onEdit,
  onMerge,
}: RelationCandidateRowProps) {
  const confidence = relation.confidence ?? 0

  return (
    <article className="rounded-lg border border-ink-200 bg-ink-50/40 p-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          {selectable && (
            <input
              type="checkbox"
              checked={selected}
              onChange={(event) => onSelectedChange?.(event.target.checked)}
              aria-label={`Seleccionar relación con ${relation.target.name}`}
              className="mt-1 h-4 w-4 rounded border-ink-300 text-indigo"
            />
          )}
          <div className="min-w-0">
            {sourceDocument && (
              <p className="mb-1 text-xs font-medium text-ink-500">
                {sourceDocument.name} · {sourceDocument.folder_name}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-semibold text-ink-900">{relation.target.name}</p>
              <Badge variant="neutral" dot={false}>
                {targetTypeLabel(relation.target.type)}
              </Badge>
              <Badge variant="info" dot={false}>
                {relationTypeLabel(relationType)}
              </Badge>
              {relation.possible_duplicate_of && (
                <Badge variant="warning" dot={false}>
                  Posible duplicado
                </Badge>
              )}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1.5 w-28 overflow-hidden rounded-full bg-ink-150">
                <div
                  className={
                    confidence >= HIGH_CONFIDENCE_THRESHOLD
                      ? 'h-full bg-success'
                      : 'h-full bg-warning'
                  }
                  style={{ width: `${Math.round(confidence * 100)}%` }}
                />
              </div>
              <span className="text-xs font-medium text-ink-500">
                {confidenceLabel(relation.confidence)}
              </span>
            </div>
            {relation.evidence_text && (
              <p className="mt-2 line-clamp-2 text-xs text-ink-500">
                “{relation.evidence_text}”
              </p>
            )}
            {relation.possible_duplicate_of && (
              <p className="mt-2 text-xs text-warning">
                Se parece a “{relation.possible_duplicate_of.name}”.
              </p>
            )}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          {canEdit && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onEdit}
              disabled={busy}
              aria-label={`Editar relación con ${relation.target.name}`}
            >
              <Pencil aria-hidden="true" />
              Editar
            </Button>
          )}
          {canEdit && relation.possible_duplicate_of && (
            <Button variant="secondary" size="sm" onClick={onMerge} disabled={busy}>
              <GitMerge aria-hidden="true" />
              Unir
            </Button>
          )}
          {canApprove && (
            <Button variant="secondary" size="sm" onClick={onConfirm} disabled={busy}>
              <Check aria-hidden="true" />
              Confirmar
            </Button>
          )}
          {canReject && (
            <Button variant="danger" size="sm" onClick={onReject} disabled={busy}>
              <X aria-hidden="true" />
              Rechazar
            </Button>
          )}
        </div>
      </div>
    </article>
  )
}
