import { describe, expect, it } from 'vitest'
import { prepareSuggestionChips } from '@/lib/tytoSuggestions'

describe('prepareSuggestionChips', () => {
  it('mapea preguntas a chips preservando el orden que ya viene rankeado por frecuencia', () => {
    const chips = prepareSuggestionChips([
      { question: '¿Cómo cierro la caja?', veces: 42 },
      { question: '¿Cada cuánto se calibra el surtidor?', veces: 17 },
    ])

    expect(chips).toEqual([
      { question: '¿Cómo cierro la caja?', label: '¿Cómo cierro la caja?' },
      { question: '¿Cada cuánto se calibra el surtidor?', label: '¿Cada cuánto se calibra el surtidor?' },
    ])
  })

  it('descarta preguntas vacías o en blanco', () => {
    const chips = prepareSuggestionChips([
      { question: '   ', veces: 5 },
      { question: '', veces: 3 },
      { question: '¿Cómo cierro la caja?', veces: 1 },
    ])

    expect(chips).toHaveLength(1)
    expect(chips[0].question).toBe('¿Cómo cierro la caja?')
  })

  it('deduplica preguntas repetidas salvo mayúsculas/espacios', () => {
    const chips = prepareSuggestionChips([
      { question: '¿Cómo cierro la caja?', veces: 10 },
      { question: '  ¿cómo cierro la caja?  ', veces: 4 },
    ])

    expect(chips).toHaveLength(1)
  })

  it('respeta el límite pedido', () => {
    const suggestions = Array.from({ length: 10 }, (_, i) => ({ question: `Pregunta ${i}`, veces: 10 - i }))
    expect(prepareSuggestionChips(suggestions, 3)).toHaveLength(3)
    expect(prepareSuggestionChips(suggestions)).toHaveLength(6) // límite por defecto
  })

  it('trunca el label visible de una pregunta larga, pero conserva la pregunta completa para preguntar', () => {
    const larga =
      '¿Qué tengo que hacer si el surtidor número tres no calibra bien después del mantenimiento programado de la semana pasada?'
    const [chip] = prepareSuggestionChips([{ question: larga, veces: 1 }])

    expect(chip.question).toBe(larga)
    expect(chip.label.length).toBeLessThan(larga.length)
    expect(chip.label.endsWith('…')).toBe(true)
  })

  it('sin sugerencias, devuelve una lista vacía (no revienta)', () => {
    expect(prepareSuggestionChips([])).toEqual([])
  })
})
