// components/tyto/TytoAnswerText.tsx
// Renderiza la prosa de Tyto convirtiendo los marcadores [Sn] inline en:
//  - mientras streamea (sources === null): chip neutro, SIN color de nivel ni link
//    (regla de reliability: los niveles solo existen después del evento `result`).
//  - ya resuelto (sources: TytoSource[]): link a la ficha del documento fuente,
//    teñido con el nivel de esa fuente puntual.
'use client'

import * as React from 'react'
import Link from 'next/link'
import { cn } from '@/shared/ui/cn'
import { tierMeta } from '@/shared/ui/components'
import type { TytoSource } from '@/lib/api'

const CITATION_RE = /(\[S\d+\])/g
const CITATION_MATCH_RE = /^\[S(\d+)\]$/

export function TytoAnswerText({
  text,
  sources,
  className,
}: {
  text: string
  /** `null`/`undefined` mientras streamea (todavía no llegó `result`). */
  sources?: TytoSource[] | null
  className?: string
}) {
  const parts = text.split(CITATION_RE)
  const resolved = Boolean(sources)

  return (
    <p className={cn('whitespace-pre-wrap text-body leading-relaxed text-ink-800', className)}>
      {parts.map((part, i) => {
        const match = CITATION_MATCH_RE.exec(part)
        if (!match) return <React.Fragment key={i}>{part}</React.Fragment>

        const sourceId = `S${match[1]}`
        const source = sources?.find((s) => s.source_id === sourceId)
        return (
          <CitationMark key={i} sourceId={sourceId} source={source} resolved={resolved} />
        )
      })}
    </p>
  )
}

function CitationMark({
  sourceId,
  source,
  resolved,
}: {
  sourceId: string
  source?: TytoSource
  resolved: boolean
}) {
  // Streaming: marcador neutro, no clickeable, sin color de nivel.
  if (!resolved || !source) {
    return (
      <span
        className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded bg-ink-100 px-1 align-text-top text-[10px] font-bold text-ink-500"
        aria-hidden={!resolved}
      >
        {sourceId}
      </span>
    )
  }

  const m = tierMeta(source.tier)
  return (
    <Link
      href={`/documents/${source.document_id}`}
      className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded px-1 align-text-top text-[10px] font-bold transition-colors hover:underline"
      style={{ color: m.text, background: m.bg }}
      title={`${source.document_name} · ${m.label}`}
    >
      {sourceId}
    </Link>
  )
}
