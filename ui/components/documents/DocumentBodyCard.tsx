'use client'

/**
 * Card principal del cuerpo del documento — estilo ReviewPane del prototipo.
 * Muestra el iframe del PDF de la versión vigente con el aviso indigo
 * "Estás revisando la representación derivada…".
 */

import { ShieldCheck } from 'lucide-react'
import type { DocumentVersion } from '@/lib/api'

interface DocumentBodyCardProps {
  documentId: string
  /** Versión cuyo PDF debe mostrarse (DRAFT manual_edit > IN_REVIEW > APPROVED > DRAFT). */
  version: DocumentVersion | null
  /** URL del PDF ya calculada por el caller (getVersionPreviewPdfUrl). */
  pdfUrl: string | null
}

export function DocumentBodyCard({ version, pdfUrl }: DocumentBodyCardProps) {
  return (
    <section
      className="rounded-[14px] border border-line bg-surface p-7 shadow-card"
      aria-label="Vista previa del documento"
    >
      {/* Aviso indigo — patrón del ReviewPane */}
      <div className="mb-4 flex items-center gap-2 rounded-[10px] border border-indigo-border bg-indigo-tint px-3.5 py-2.5 text-xs text-indigo">
        <ShieldCheck className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
        <span>
          Estás revisando la representación derivada. El archivo original es la fuente oficial.
        </span>
      </div>

      {pdfUrl ? (
        <div className="overflow-hidden rounded-lg border border-ink-200">
          <iframe
            src={`${pdfUrl}#toolbar=0`}
            className="h-[680px] w-full"
            title={`Vista previa — versión ${version?.version_number ?? ''}`}
          />
        </div>
      ) : (
        <div className="flex h-64 items-center justify-center rounded-lg bg-ink-50">
          <p className="text-sm text-ink-500">
            {version
              ? 'Generando PDF…'
              : 'No hay versión disponible para previsualizar.'}
          </p>
        </div>
      )}
    </section>
  )
}
