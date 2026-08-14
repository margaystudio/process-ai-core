import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { mapSessionEntryToMessages, sortTytoSessions, useDebouncedValue } from '@/lib/tytoHistory'
import type { TytoSessionEntry, TytoSessionSummary } from '@/lib/api'

function session(overrides: Partial<TytoSessionSummary> = {}): TytoSessionSummary {
  return {
    id: 's1',
    title: 'Cierre de caja',
    pinned: false,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    message_count: 2,
    ...overrides,
  }
}

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('devuelve el valor inicial de inmediato, sin esperar el delay', () => {
    const { result } = renderHook(() => useDebouncedValue('inicial', 300))
    expect(result.current).toBe('inicial')
  })

  it('no actualiza hasta que pasa el delay completo desde el último cambio', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: '' },
    })

    rerender({ value: 'cie' })
    act(() => {
      vi.advanceTimersByTime(200)
    })
    expect(result.current).toBe('') // todavía no pasó el delay

    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(result.current).toBe('cie')
  })

  it('cada tecla reinicia el temporizador — solo se emite el último valor', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: '' },
    })

    rerender({ value: 'c' })
    act(() => vi.advanceTimersByTime(150))
    rerender({ value: 'ci' })
    act(() => vi.advanceTimersByTime(150))
    rerender({ value: 'cie' })
    // Todavía no pasaron 300ms desde el último cambio ('cie').
    act(() => vi.advanceTimersByTime(250))
    expect(result.current).toBe('')

    act(() => vi.advanceTimersByTime(50))
    expect(result.current).toBe('cie')
  })
})

describe('sortTytoSessions', () => {
  it('pone las ancladas primero, sin importar su fecha', () => {
    const sessions = [
      session({ id: 'vieja-sin-anclar', pinned: false, updated_at: '2026-08-10T00:00:00Z' }),
      session({ id: 'anclada', pinned: true, updated_at: '2026-08-01T00:00:00Z' }),
    ]
    const sorted = sortTytoSessions(sessions)
    expect(sorted.map((s) => s.id)).toEqual(['anclada', 'vieja-sin-anclar'])
  })

  it('dentro de cada grupo (ancladas / no ancladas) ordena por más reciente', () => {
    const sessions = [
      session({ id: 'a', pinned: false, updated_at: '2026-08-01T00:00:00Z' }),
      session({ id: 'b', pinned: false, updated_at: '2026-08-10T00:00:00Z' }),
      session({ id: 'c', pinned: true, updated_at: '2026-08-02T00:00:00Z' }),
      session({ id: 'd', pinned: true, updated_at: '2026-08-09T00:00:00Z' }),
    ]
    const sorted = sortTytoSessions(sessions)
    expect(sorted.map((s) => s.id)).toEqual(['d', 'c', 'b', 'a'])
  })

  it('no muta el array original', () => {
    const sessions = [session({ id: 'a', pinned: false }), session({ id: 'b', pinned: true })]
    const original = [...sessions]
    sortTytoSessions(sessions)
    expect(sessions).toEqual(original)
  })
})

describe('mapSessionEntryToMessages', () => {
  it('mapea una entrada contestada a un par usuario/asistente con sus fuentes', () => {
    const entry: TytoSessionEntry = {
      id: 'e1',
      question: '¿Qué necesito para el cierre de caja?',
      answered: true,
      answer: 'Contá el efectivo con el supervisor [S1].',
      refusal_reason: null,
      sources: [
        {
          source_id: 'S1',
          document_id: 'doc-1',
          document_name: 'Cierre de caja',
          version: 4,
          approved_at: '2026-06-12T00:00:00Z',
          tier: 'aprobado',
        },
      ],
      created_at: '2026-08-01T10:00:00Z',
    }

    const { user, assistant } = mapSessionEntryToMessages(entry)

    expect(user).toEqual({
      id: 'hist-user-e1',
      role: 'user',
      question: '¿Qué necesito para el cierre de caja?',
    })
    expect(assistant.role).toBe('assistant')
    expect(assistant.status).toBe('answered')
    expect(assistant.text).toBe('Contá el efectivo con el supervisor [S1].')
    expect(assistant.result?.sources).toEqual(entry.sources)
    expect(assistant.result?.answered).toBe(true)
  })

  it('mapea un rechazo (answered: false) con el mismo tratamiento que el chat en vivo', () => {
    const entry: TytoSessionEntry = {
      id: 'e2',
      question: '¿Cuándo juega Peñarol?',
      answered: false,
      answer: null,
      refusal_reason: 'No tengo documentación aprobada sobre ese tema.',
      sources: [],
      created_at: '2026-08-01T10:05:00Z',
    }

    const { assistant } = mapSessionEntryToMessages(entry)

    expect(assistant.status).toBe('refused')
    expect(assistant.text).toBe('No tengo documentación aprobada sobre ese tema.')
    expect(assistant.result).toBeUndefined()
  })

  it('un rechazo sin motivo guardado cae al mismo fallback que el chat en vivo', () => {
    const entry: TytoSessionEntry = {
      id: 'e3',
      question: '¿Cómo hago el arqueo?',
      answered: false,
      answer: null,
      refusal_reason: null,
      sources: [],
      created_at: '2026-08-01T10:06:00Z',
    }

    const { assistant } = mapSessionEntryToMessages(entry)
    expect(assistant.text).toMatch(/No encontré documentación aprobada suficiente/)
  })

  it('ids estables por entrada, para no chocar con los ids de la conversación en curso', () => {
    const entry: TytoSessionEntry = {
      id: 'abc-123',
      question: 'q',
      answered: true,
      answer: 'a',
      refusal_reason: null,
      sources: [],
      created_at: '2026-08-01T10:00:00Z',
    }
    const { user, assistant } = mapSessionEntryToMessages(entry)
    expect(user.id).toBe('hist-user-abc-123')
    expect(assistant.id).toBe('hist-assistant-abc-123')
  })
})
