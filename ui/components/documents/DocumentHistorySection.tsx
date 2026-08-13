'use client'

/**
 * Historial y trazabilidad — colapsable.
 * Versiones (aprobadas, rechazadas y superadas) + audit log (misma data, mejor
 * presentación visual). Las aprobadas y superadas tienen botón de descarga:
 * el PDF que baja lleva estampado el sello "VERSIÓN SUPERADA" cuando corresponde.
 */

import { useState } from 'react'
import { AlertCircle, ChevronDown, ChevronUp, Download } from 'lucide-react'
import { Button } from '@/shared/ui/components/button'
import { Badge } from '@/shared/ui/components/badge'
import { Spinner } from '@/shared/ui/components/Spinner'
import { formatDateTime } from '@/utils/dateFormat'
import { downloadVersionPdf } from '@/lib/api'
import type { AuditLogEntry, DocumentVersion, Validation } from '@/lib/api'

/**
 * Versiones con artefacto congelado descargable: APPROVED siempre, OBSOLETE si
 * en su momento se congeló al aprobarla (el backend resuelve ese detalle al
 * servir — ver `getVersionPdfUrl`). REJECTED nunca tiene artefacto: no se
 * genera PDF para una versión que no llegó a regir.
 */
function hasDownloadablePdf(version: DocumentVersion): boolean {
  return version.version_status === 'APPROVED' || version.version_status === 'OBSOLETE'
}

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
  documentId: string
  versions: DocumentVersion[]
  auditLog: AuditLogEntry[]
  validations: Validation[]
  showHistory: boolean
  onToggle: () => void
}

export function DocumentHistorySection({
  documentId,
  versions,
  auditLog,
  validations,
  showHistory,
  onToggle,
}: DocumentHistorySectionProps) {
  // OBSOLETE (versión aprobada y luego superada) entra a la lista: es
  // justamente el caso donde importa poder bajar el PDF con el sello.
  const versionEvents = versions
    .filter(
      (v) =>
        v.version_status === 'APPROVED' ||
        v.version_status === 'REJECTED' ||
        v.version_status === 'OBSOLETE'
    )
    .sort((a, b) => {
      const aDate = a.version_status === 'REJECTED' ? a.rejected_at : a.approved_at
      const bDate = b.version_status === 'REJECTED' ? b.rejected_at : b.approved_at
      return new Date(bDate ?? 0).getTime() - new Date(aDate ?? 0).getTime()
    })

  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<{ versionId: string; message: string } | null>(
    null
  )

  async function handleDownload(version: DocumentVersion) {
    setDownloadingId(version.id)
    setDownloadError(null)
    try {
      await downloadVersionPdf(documentId, version.id, version.version_status)
    } catch (err) {
      setDownloadError({
        versionId: version.id,
        message: err instanceof Error ? err.message : 'No se pudo descargar el PDF.',
      })
    } finally {
      setDownloadingId(null)
    }
  }

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
          {/* Versiones */}
          <div>
            <h3 className="text-h3 text-ink-900 mb-3">Versiones</h3>
            {versionEvents.length === 0 ? (
              <p className="text-sm text-ink-500">No hay versiones registradas.</p>
            ) : (
              <div className="space-y-2">
                {versionEvents.map((v) => {
                  const isRejected = v.version_status === 'REJECTED'
                  const isObsolete = v.version_status === 'OBSOLETE'
                  const isDownloading = downloadingId === v.id
                  return (
                    <div
                      key={v.id}
                      className={`rounded-lg border p-4 ${
                        v.is_current
                          ? 'border-success-bd bg-success-bg'
                          : 'border-ink-200 bg-white'
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-ink-900">
                            Versión {v.version_number}
                          </span>
                          {v.is_current && (
                            <Badge variant="success" dot={false}>
                              Actual
                            </Badge>
                          )}
                          {isRejected && (
                            <Badge variant="danger" dot={false}>
                              Rechazada
                            </Badge>
                          )}
                          {isObsolete && (
                            <Badge variant="warning" dot={false}>
                              Superada
                            </Badge>
                          )}
                          {v.content_type && (
                            <span className="text-xs text-ink-500">
                              {CONTENT_TYPE_LABELS[v.content_type] ?? v.content_type}
                            </span>
                          )}
                        </div>
                        {hasDownloadablePdf(v) && (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleDownload(v)}
                            disabled={isDownloading}
                            aria-busy={isDownloading}
                            aria-label={`Descargar PDF de la versión ${v.version_number}`}
                          >
                            {isDownloading ? (
                              <Spinner size="sm" aria-hidden="true" />
                            ) : (
                              <Download aria-hidden="true" />
                            )}
                            {isDownloading ? 'Descargando…' : 'Descargar'}
                          </Button>
                        )}
                      </div>
                      {isRejected
                        ? v.rejected_at && (
                            <p className="text-xs text-ink-500">
                              Rechazada el {formatDateTime(v.rejected_at)}
                              {v.rejected_by_name ? ` por ${v.rejected_by_name}` : ''}
                            </p>
                          )
                        : v.approved_at && (
                            <p className="text-xs text-ink-500">
                              Aprobada el {formatDateTime(v.approved_at)}
                              {v.approved_by_name ? ` por ${v.approved_by_name}` : ''}
                            </p>
                          )}
                      {v.run_id && (
                        <p className="text-xs text-ink-400 font-mono mt-0.5">
                          Run {v.run_id.substring(0, 8)}…
                        </p>
                      )}
                      {downloadError?.versionId === v.id && (
                        <div
                          role="alert"
                          className="mt-2 flex items-start gap-2 rounded-lg border border-danger-bd bg-danger-bg p-2 text-xs text-danger"
                        >
                          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          <span>{downloadError.message}</span>
                        </div>
                      )}
                    </div>
                  )
                })}
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
                    const submittedByName = ver?.created_by_name ?? ''
                    const validatorId = val.validator_user_id ?? null
                    const validatorName = val.validator_user_name ?? ''
                    const isPending = val.status !== 'approved' && val.status !== 'rejected'
                    const actorId = isPending
                      ? (submittedBy ?? validatorId)
                      : validatorId ?? submittedBy
                    const actorName = isPending
                      ? (submittedByName || validatorName)
                      : (validatorName || submittedByName)

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
                            {actorName && (
                              <>
                                {' '}
                                por{' '}
                                <span title={actorId ?? undefined}>{actorName}</span>
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
                    <p className="text-xs text-ink-500 mb-1">
                      {formatDateTime(entry.created_at)}
                      {entry.user_name ? ` · ${entry.user_name}` : ''}
                    </p>
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

          {versionEvents.length === 0 &&
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
