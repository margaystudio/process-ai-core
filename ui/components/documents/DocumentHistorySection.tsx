'use client'

/**
 * Historial y trazabilidad — colapsable.
 * Versiones aprobadas + audit log (misma data, mejor presentación visual).
 */

import { ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/shared/ui/components/button'
import { Badge } from '@/shared/ui/components/badge'
import { formatDateTime } from '@/utils/dateFormat'
import type { AuditLogEntry, DocumentVersion, Validation } from '@/lib/api'

const CONTENT_TYPE_LABELS: Record<string, string> = {
  generated: 'Generada',
  manual_edit: 'Edición manual',
  ai_patch: 'Patch por IA',
}

const ACTION_LABELS: Record<string, string> = {
  updated: 'Actualizado',
  validated: 'Validado',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  'version.draft_reused': 'Borrador reutilizado',
  'version.draft_created': 'Borrador creado',
  'version.draft_updated': 'Borrador actualizado',
  'version.draft_updated_by_ai_patch': 'Borrador actualizado (patch IA)',
  'version.draft_created_by_ai_patch': 'Borrador creado (patch IA)',
  'version.submitted': 'Enviado a revisión',
  'version.submission_cancelled': 'Envío cancelado',
  'version.approved': 'Versión aprobada',
  'version.rejected': 'Versión rechazada',
  manual_edit_saved: 'Edición manual guardada',
}

interface DocumentHistorySectionProps {
  versions: DocumentVersion[]
  auditLog: AuditLogEntry[]
  validations: Validation[]
  userDisplayNames: Record<string, string>
  showHistory: boolean
  onToggle: () => void
}

export function DocumentHistorySection({
  versions,
  auditLog,
  validations,
  userDisplayNames,
  showHistory,
  onToggle,
}: DocumentHistorySectionProps) {
  const approvedVersions = versions.filter((v) => v.version_status === 'APPROVED')

  return (
    <section aria-label="Historial y trazabilidad">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-h2 text-ink-900">Historial y trazabilidad</h2>
        <Button variant="secondary" size="sm" onClick={onToggle} aria-expanded={showHistory}>
          {showHistory ? (
            <>
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
              Ocultar
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
              Ver historial
            </>
          )}
        </Button>
      </div>

      {showHistory && (
        <div className="space-y-6">
          {/* Versiones aprobadas */}
          <div>
            <h3 className="text-h3 text-ink-900 mb-3">Versiones aprobadas</h3>
            {approvedVersions.length === 0 ? (
              <p className="text-sm text-ink-500">No hay versiones aprobadas.</p>
            ) : (
              <div className="space-y-2">
                {approvedVersions.map((v) => (
                  <div
                    key={v.id}
                    className={`rounded-lg border p-4 ${
                      v.is_current
                        ? 'border-success-bd bg-success-bg'
                        : 'border-ink-200 bg-white'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-ink-900">
                        Versión {v.version_number}
                      </span>
                      {v.is_current && (
                        <Badge variant="success" dot={false}>
                          Actual
                        </Badge>
                      )}
                      {v.content_type && (
                        <span className="text-xs text-ink-500">
                          {CONTENT_TYPE_LABELS[v.content_type] ?? v.content_type}
                        </span>
                      )}
                    </div>
                    {v.approved_at && (
                      <p className="text-xs text-ink-500">
                        Aprobada el {formatDateTime(v.approved_at)}
                        {v.approved_by ? ` por ${v.approved_by}` : ''}
                      </p>
                    )}
                    {v.run_id && (
                      <p className="text-xs text-ink-400 font-mono mt-0.5">
                        Run {v.run_id.substring(0, 8)}…
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Historial de validaciones */}
          {validations.length > 0 && (
            <div>
              <h3 className="text-h3 text-ink-900 mb-3">Historial de validaciones</h3>
              <div className="space-y-3">
                {[...validations]
                  .sort(
                    (a, b) =>
                      new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
                  )
                  .map((val, idx) => {
                    const ver = versions.find((v) => v.validation_id === val.id)
                    const submittedBy = ver?.created_by ?? null
                    const validatorId = val.validator_user_id ?? null
                    const isPending = val.status !== 'approved' && val.status !== 'rejected'
                    const actorId = isPending
                      ? (submittedBy ?? validatorId)
                      : validatorId ?? submittedBy

                    const badgeVariant =
                      val.status === 'approved'
                        ? 'success'
                        : val.status === 'rejected'
                        ? 'danger'
                        : 'warning'
                    const statusLabel =
                      val.status === 'approved'
                        ? 'Aprobada'
                        : val.status === 'rejected'
                        ? 'Rechazada'
                        : 'Pendiente'
                    const eventLabel = isPending
                      ? idx === 0
                        ? 'Enviado'
                        : 'Reenviado para validación'
                      : statusLabel

                    return (
                      <div
                        key={val.id}
                        className="rounded-lg border border-ink-200 bg-white p-4"
                      >
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <Badge variant={badgeVariant}>{statusLabel}</Badge>
                          <span className="text-xs text-ink-500">
                            {eventLabel} el {formatDateTime(val.created_at)}
                            {actorId && (
                              <>
                                {' '}
                                por{' '}
                                <span title={actorId}>
                                  {userDisplayNames[actorId] ?? actorId}
                                </span>
                              </>
                            )}
                          </span>
                        </div>
                        {val.observations && (
                          <p className="text-sm text-ink-700 whitespace-pre-wrap">
                            {val.observations}
                          </p>
                        )}
                      </div>
                    )
                  })}
              </div>
            </div>
          )}

          {/* Audit log */}
          {auditLog.length > 0 && (
            <div>
              <h3 className="text-h3 text-ink-900 mb-3">Registro de auditoría</h3>
              <div className="space-y-2">
                {auditLog.map((entry) => (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-ink-200 bg-white p-3"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-ink-900">
                        {ACTION_LABELS[entry.action] ?? entry.action}
                      </span>
                      <span className="text-xs text-ink-400">{entry.entity_type}</span>
                    </div>
                    <p className="text-xs text-ink-500 mb-1">{formatDateTime(entry.created_at)}</p>
                    {entry.changes_json && (
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs text-ink-500 hover:text-ink-800">
                          Ver cambios
                        </summary>
                        <pre className="mt-2 max-h-40 overflow-auto rounded bg-ink-50 p-2 text-xs">
                          {JSON.stringify(JSON.parse(entry.changes_json), null, 2)}
                        </pre>
                      </details>
                    )}
                    {entry.metadata_json && (
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs text-ink-500 hover:text-ink-800">
                          Ver metadata
                        </summary>
                        <pre className="mt-2 max-h-40 overflow-auto rounded bg-ink-50 p-2 text-xs">
                          {JSON.stringify(JSON.parse(entry.metadata_json), null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {approvedVersions.length === 0 &&
            validations.length === 0 &&
            auditLog.length === 0 && (
              <p className="py-8 text-center text-sm text-ink-500">
                No hay historial disponible aún.
              </p>
            )}
        </div>
      )}
    </section>
  )
}
