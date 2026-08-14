'use client'

/**
 * Card principal del cuerpo del documento — estilo ReviewPane del prototipo.
 * Muestra el iframe del PDF de la versión vigente con el aviso indigo
 * "Estás revisando la representación derivada…".
 */

import { AlertTriangle, ShieldCheck } from 'lucide-react'
import { Button } from '@/shared/ui'
import type { DocumentVersion } from '@/lib/api'

interface DocumentBodyCardProps {
  documentId: string
  /** Versión cuyo PDF debe mostrarse (DRAFT manual_edit > IN_REVIEW > APPROVED > DRAFT). */
  version: DocumentVersion | null
  /** Blob URL del PDF ya resuelta por el caller (getVersionPdfUrl + authFetch). */
  pdfUrl: string | null
  /** Si la carga falló. Sin esto, un error se ve igual que "todavía cargando". */
  pdfError?: boolean
  onRetryPdf?: () => void
}

export function DocumentBodyCard({
  version,
  pdfUrl,
  pdfError = false,
  onRetryPdf,
}: DocumentBodyCardProps) {
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
      ) : pdfError ? (
        // Un error tiene que decirlo. Antes cualquier fallo dejaba el cartel de
        // "Generando PDF…" para siempre: la pantalla se veía colgada y no había
        // forma de saber que la carga había terminado mal.
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg bg-ink-50 px-6 text-center">
          <AlertTriangle className="h-5 w-5 text-danger" aria-hidden="true" />
          <p className="text-sm text-ink-700">
            No se pudo cargar el PDF de esta versión.
          </p>
          {onRetryPdf ? (
            <Button variant="secondary" size="sm" onClick={onRetryPdf}>
              Reintentar
            </Button>
          ) : null}
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
