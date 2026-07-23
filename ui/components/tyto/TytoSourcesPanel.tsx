// components/tyto/TytoSourcesPanel.tsx
// Panel derecho "De qué piezas se arma esta respuesta": una card por fuente de
// la ÚLTIMA respuesta contestada (answered: true) + leyenda de niveles al pie.
// Nunca se puebla antes del evento `result` (regla de reliability).
'use client'

import { TierBadge, TierDot } from '@/shared/ui/components'
import { formatDate } from '@/utils/dateFormat'
import type { TytoQueryResult, TytoSource } from '@/lib/api'

export function TytoSourcesPanel({ result }: { result: TytoQueryResult | null }) {
  const sources = result?.sources ?? []

  return (
    <aside className="hidden w-[320px] flex-shrink-0 flex-col overflow-hidden border-l border-line bg-surface lg:flex">
      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5 pt-6">
        <div className="mb-1 text-[11px] font-extrabold uppercase tracking-[.06em] text-ink-400">
          De qué piezas se arma esta respuesta
        </div>
        <p className="mb-5 text-[12px] leading-relaxed text-ink-400">
          Se apoya en lo aprobado: las referencias externas y las inferencias van
          marcadas con su nivel.
        </p>

        {sources.length === 0 ? (
          <div className="rounded-lg border border-dashed border-line-input bg-surface-hover px-3 py-4 text-[12.5px] leading-relaxed text-ink-500">
            Las piezas que arman la respuesta van a aparecer acá cuando le hagas
            una pregunta a Tyto.
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {sources.map((source) => (
              <SourceCard key={source.source_id} source={source} />
            ))}
          </div>
        )}
      </div>

      <div className="flex-shrink-0 border-t border-line px-5 py-4">
        <div className="mb-2 text-[10.5px] font-extrabold uppercase tracking-[.06em] text-ink-400">
          Niveles
        </div>
        <div className="flex flex-col gap-1.5">
          <LegendRow tier="aprobado" label="Fuente aprobada" />
          <LegendRow tier="referencia" label="Referencia no validada" />
          <LegendRow tier="inferido" label="Inferido" />
        </div>
      </div>
    </aside>
  )
}

function SourceCard({ source }: { source: TytoSource }) {
  return (
    <div className="rounded-[11px] border border-line bg-surface px-3.5 py-3">
      <div className="mb-1 flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-[13px] font-bold text-ink-800">
          {source.document_name}
        </span>
        <TierBadge tier={source.tier} />
      </div>
      <div className="font-mono text-[11px] text-ink-400">
        {source.version != null ? `v${source.version}` : 'sin versión'}
        {' · '}
        {source.approved_at ? formatDate(source.approved_at) : 'sin fecha de aprobación'}
      </div>
    </div>
  )
}

function LegendRow({ tier, label }: { tier: 'aprobado' | 'referencia' | 'inferido'; label: string }) {
  return (
    <div className="flex items-center gap-2 text-[11.5px] text-ink-600">
      <TierDot tier={tier} />
      {label}
    </div>
  )
}
