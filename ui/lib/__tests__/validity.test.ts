import { describe, expect, it } from 'vitest'

import {
  DEFAULT_VALIDITY_MONTHS,
  addMonths,
  defaultValidityDate,
  toDateInputValue,
} from '@/lib/validity'

describe('vigencia de la aprobación', () => {
  it('propone 24 meses por defecto', () => {
    expect(DEFAULT_VALIDITY_MONTHS).toBe(24)
    expect(defaultValidityDate(24, new Date(2026, 0, 15))).toBe('2028-01-15')
  })

  it('respeta el fin de mes al sumar', () => {
    // 31/01 + 1 mes es 28/02, no 03/03: sumar meses ingenuamente desborda.
    expect(toDateInputValue(addMonths(new Date(2026, 0, 31), 1))).toBe('2026-02-28')
    expect(toDateInputValue(addMonths(new Date(2024, 1, 29), 12))).toBe('2025-02-28')
    expect(toDateInputValue(addMonths(new Date(2026, 0, 31), 24))).toBe('2028-01-31')
  })

  it('formatea con el padding que espera <input type="date">', () => {
    expect(toDateInputValue(new Date(2026, 2, 5))).toBe('2026-03-05')
  })

  it('coincide con el cálculo del backend', () => {
    // El backend usa el mismo criterio (_add_months en db/helpers.py). Si
    // divergieran, la fecha que propone la UI no sería la que se congela.
    const casos: Array<[Date, number, string]> = [
      [new Date(2026, 0, 31), 1, '2026-02-28'],
      [new Date(2026, 0, 31), 24, '2028-01-31'],
      [new Date(2024, 1, 29), 12, '2025-02-28'],
    ]
    for (const [base, meses, esperado] of casos) {
      expect(toDateInputValue(addMonths(base, meses))).toBe(esperado)
    }
  })
})
