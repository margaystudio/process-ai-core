// lib/tytoSuggestions.ts
// Lógica pura de mapeo de `GET /tyto/suggestions` a chips tocables — separada
// del render para poder testearla sin montar la pantalla. El backend ya
// rankea por frecuencia; acá solo se filtra basura y se recorta el label
// visible (nunca la pregunta real que viaja al hacer clic).
import type { TytoSuggestion } from '@/lib/api'

export interface TytoSuggestionChip {
  /** Pregunta completa — la que se manda a Tyto al tocar el chip. */
  question: string
  /** Texto a mostrar en el chip: recortado si hace falta. */
  label: string
}

const MAX_CHIP_LABEL = 56

/**
 * Prepara como máximo `limit` chips: descarta vacíos y duplicados (mismo
 * texto salvo mayúsculas/espacios) preservando el orden de llegada — que ya
 * viene rankeado por `veces` desde el backend.
 */
export function prepareSuggestionChips(
  suggestions: TytoSuggestion[],
  limit = 6
): TytoSuggestionChip[] {
  const seen = new Set<string>()
  const chips: TytoSuggestionChip[] = []

  for (const s of suggestions) {
    const question = s?.question?.trim()
    if (!question) continue
    const key = question.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    chips.push({ question, label: truncateLabel(question) })
    if (chips.length >= limit) break
  }

  return chips
}

function truncateLabel(text: string): string {
  if (text.length <= MAX_CHIP_LABEL) return text
  return `${text.slice(0, MAX_CHIP_LABEL - 1).trimEnd()}…`
}
