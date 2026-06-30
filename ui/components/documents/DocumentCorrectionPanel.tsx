'use client'

/**
 * Panel de corrección de contenido (patch por IA / edición manual / regenerar).
 * Se muestra cuando canEditMetadata (borrador o rechazado con permiso).
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Wand2, FileEdit } from 'lucide-react'
import { Button } from '@/shared/ui/components/button'
import ManualEditPanel from './ManualEditPanel'
import type { Document, DocumentVersion } from '@/lib/api'

interface DocumentCorrectionPanelProps {
  document: Document
  userId: string | null
  aiPatchObservations: string
  onAiPatchObservationsChange: (v: string) => void
  onPatchWithAI: () => void
  isPatching: boolean
  onVersionsRefresh: () => Promise<void>
  onDocumentRefresh: () => Promise<void>
  onSavedDraftBanner: () => void
}

export function DocumentCorrectionPanel({
  document,
  userId,
  aiPatchObservations,
  onAiPatchObservationsChange,
  onPatchWithAI,
  isPatching,
  onVersionsRefresh,
  onDocumentRefresh,
  onSavedDraftBanner,
}: DocumentCorrectionPanelProps) {
  const [open, setOpen] = useState(false)
  const [correctionType, setCorrectionType] = useState<'ai_patch' | 'manual' | null>(null)

  const isDraft = document.status === 'draft'
  const isRejected = document.status === 'rejected'
  if (!isDraft && !isRejected) return null

  const handleClose = () => {
    setCorrectionType(null)
    setOpen(false)
  }

  return (
    <section
      className={`rounded-lg border p-5 ${
        isDraft
          ? 'border-indigo-border bg-indigo-tint'
          : 'border-warning-bd bg-warning-bg'
      }`}
      aria-label={isDraft ? 'Modificar contenido del documento' : 'Corregir documento'}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-h3 text-ink-900">
            {isDraft ? 'Modificar contenido' : 'Corregir documento'}
          </h3>
          <p className="mt-0.5 text-sm text-ink-600">
            {isDraft
              ? 'Ajustá el contenido antes de enviarlo a revisión.'
              : 'El documento fue rechazado. Corregí el contenido y envialo nuevamente.'}
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setOpen((o) => !o)
            if (open) setCorrectionType(null)
          }}
          aria-expanded={open}
        >
          {open ? (
            <>
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
              Ocultar
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
              Mostrar opciones
            </>
          )}
        </Button>
      </div>

      {open && (
        <div className="mt-5 space-y-4">
          {/* Selector de modo */}
          {correctionType === null && (
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setCorrectionType('ai_patch')}
                className="flex flex-1 flex-col items-center gap-2 rounded-lg border border-ink-200 bg-white p-4 text-sm font-semibold text-ink-700 hover:border-indigo hover:bg-indigo-tint transition-colors"
              >
                <Wand2 className="h-5 w-5 text-indigo" aria-hidden="true" />
                Patch por IA
              </button>
              <button
                type="button"
                onClick={() => setCorrectionType('manual')}
                className="flex flex-1 flex-col items-center gap-2 rounded-lg border border-ink-200 bg-white p-4 text-sm font-semibold text-ink-700 hover:border-indigo hover:bg-indigo-tint transition-colors"
              >
                <FileEdit className="h-5 w-5 text-indigo" aria-hidden="true" />
                Edición manual
              </button>
            </div>
          )}

          {/* Patch por IA */}
          {correctionType === 'ai_patch' && (
            <div className="rounded-lg border border-ink-200 bg-white p-5">
              <h4 className="text-sm font-semibold text-ink-900 mb-3">Patch por IA</h4>
              <label
                htmlFor="ai-patch-obs"
                className="mb-1.5 block text-sm font-medium text-ink-700"
              >
                Instrucciones para el modelo
              </label>
              <textarea
                id="ai-patch-obs"
                value={aiPatchObservations}
                onChange={(e) => onAiPatchObservationsChange(e.target.value)}
                rows={4}
                className="mb-3 w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
                placeholder="Describe las correcciones que debe aplicar el modelo…"
              />
              <div className="flex gap-3">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onPatchWithAI}
                  disabled={isPatching || !aiPatchObservations.trim()}
                >
                  <Wand2 className="h-4 w-4" aria-hidden="true" />
                  {isPatching ? 'Aplicando…' : 'Aplicar patch'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setCorrectionType(null)
                    onAiPatchObservationsChange('')
                  }}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          )}

          {/* Edición manual */}
          {correctionType === 'manual' && (
            <ManualEditPanel
              documentId={document.id}
              workspaceId={document.workspace_id}
              userId={userId}
              onCancel={() => setCorrectionType(null)}
              onSaved={async () => {
                await onVersionsRefresh()
                setCorrectionType(null)
                setOpen(false)
                onSavedDraftBanner()
              }}
              onSubmitForReview={async () => {
                setCorrectionType(null)
                setOpen(false)
                await Promise.all([onVersionsRefresh(), onDocumentRefresh()])
              }}
            />
          )}

          {/* Botón para volver al selector cuando ya eligió */}
          {correctionType !== null && (
            <button
              type="button"
              onClick={() => setCorrectionType(null)}
              className="text-sm font-medium text-ink-500 hover:text-ink-800"
            >
              ← Volver a opciones
            </button>
          )}
        </div>
      )}
    </section>
  )
}
