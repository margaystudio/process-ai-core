// lib/tytoHistory.ts
// Lógica pura del historial de conversaciones de Tyto — separada del render para
// poder testearla sin montar la página completa: el debounce del buscador, el
// orden de la lista (ancladas primero) y el mapeo de una entrada de hilo guardada
// a los mismos tipos de mensaje que ya pinta el chat en vivo.
'use client'

import { useEffect, useState } from 'react'
import type { TytoAssistantMessage, TytoUserMessage } from '@/components/tyto/types'
import type { TytoSessionEntry, TytoSessionSummary } from '@/lib/api'

/**
 * Devuelve `value` recién `delayMs` después de que dejó de cambiar. Para el
 * buscador de conversaciones: sin esto, cada tecla dispararía una consulta al
 * backend (que además busca dentro de las preguntas del hilo, no es gratis).
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}

/**
 * Ancladas primero, después por más reciente — mismo criterio que ya aplica el
 * backend. Se reaplica en el cliente porque anclar/desanclar es optimista: el
 * ítem tiene que saltar de sección antes de que vuelva la confirmación del PATCH.
 */
export function sortTytoSessions(sessions: TytoSessionSummary[]): TytoSessionSummary[] {
  return [...sessions].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
}

/**
 * Traduce una entrada guardada (`GET /tyto/sessions/{id}`) al par de mensajes
 * que ya sabe pintar el hilo en vivo (`TytoUserBubble` / `TytoAssistantBubble`),
 * para que una conversación retomada se vea idéntica a una recién contestada —
 * incluidas las fuentes citadas y el motivo de rechazo, si lo hubo.
 */
export function mapSessionEntryToMessages(
  entry: TytoSessionEntry
): { user: TytoUserMessage; assistant: TytoAssistantMessage } {
  const user: TytoUserMessage = {
    id: `hist-user-${entry.id}`,
    role: 'user',
    question: entry.question,
  }

  const assistant: TytoAssistantMessage = entry.answered
    ? {
        id: `hist-assistant-${entry.id}`,
        role: 'assistant',
        question: entry.question,
        status: 'answered',
        text: entry.answer ?? '',
        result: {
          answered: true,
          answer: entry.answer ?? '',
          segments: [],
          sources: entry.sources,
        },
      }
    : {
        id: `hist-assistant-${entry.id}`,
        role: 'assistant',
        question: entry.question,
        status: 'refused',
        // Mismo fallback que usa el chat en vivo si el rechazo llegara sin motivo.
        text:
          entry.refusal_reason ||
          'No encontré documentación aprobada suficiente para responder con confianza.',
      }

  return { user, assistant }
}
