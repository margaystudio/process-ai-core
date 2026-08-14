// components/tyto/TytoSuggestionChips.tsx
// Para quien no sabe qué preguntar: las preguntas más frecuentes de ESTE
// workspace como chips tocables (preguntan directo, sin pasar por el campo).
// Si no hay ninguna (workspace nuevo, o el pedido falló), nunca un hueco en
// blanco — una ayuda breve de qué se le puede preguntar a Tyto.
'use client'

import { Chip, Skeleton } from '@/shared/ui/components'
import { prepareSuggestionChips } from '@/lib/tytoSuggestions'
import type { TytoSuggestion } from '@/lib/api'

export function TytoSuggestionChips({
  suggestions,
  loading,
  onAsk,
}: {
  suggestions: TytoSuggestion[]
  loading: boolean
  onAsk: (question: string) => void
}) {
  if (loading) {
    return (
      <div className="flex flex-wrap justify-center gap-2" aria-hidden="true">
        <Skeleton className="h-9 w-40 rounded-pill" />
        <Skeleton className="h-9 w-32 rounded-pill" />
        <Skeleton className="h-9 w-36 rounded-pill" />
      </div>
    )
  }

  const chips = prepareSuggestionChips(suggestions)

  if (chips.length === 0) {
    return (
      <div className="mx-auto max-w-sm rounded-lg border border-dashed border-line-input bg-surface-hover px-4 py-4 text-center text-[13px] leading-relaxed text-ink-600">
        Preguntale cosas como{' '}
        <span className="font-bold text-ink-800">&ldquo;¿cómo cierro la caja?&rdquo;</span> o{' '}
        <span className="font-bold text-ink-800">
          &ldquo;¿cada cuánto se calibra el surtidor?&rdquo;
        </span>
        . Tyto busca en la documentación aprobada y te dice justo qué hacer.
      </div>
    )
  }

  return (
    <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Preguntas frecuentes">
      {chips.map((chip) => (
        <Chip
          key={chip.question}
          onClick={() => onAsk(chip.question)}
          title={chip.question}
          // Contraste reforzado sobre el que trae el Chip por defecto (pensado
          // para densidad de escritorio): esta pantalla se usa afuera, al sol.
          className="h-10 px-4 text-[13px] leading-snug text-ink-700"
        >
          {chip.label}
        </Chip>
      ))}
    </div>
  )
}
