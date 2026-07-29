/**
 * Vigencia de la aprobación.
 *
 * La fecha se decide en el acto de aprobar y queda congelada en el acta del PDF.
 * No es una política del workspace: una política es mutable y por eso no se
 * podría imprimir. Acá solo vive el valor que se PROPONE al aprobador, que puede
 * cambiarlo o desactivarlo.
 */

/** Ciclo de revisión habitual de un sistema de gestión documental. */
export const DEFAULT_VALIDITY_MONTHS = 24

/** Suma meses cuidando fin de mes (31/01 + 1 mes = 28/02, no 03/03). */
export function addMonths(base: Date, months: number): Date {
  const resultado = new Date(base.getTime())
  const diaOriginal = resultado.getDate()
  resultado.setDate(1)
  resultado.setMonth(resultado.getMonth() + months)
  const ultimoDiaDelMes = new Date(
    resultado.getFullYear(),
    resultado.getMonth() + 1,
    0
  ).getDate()
  resultado.setDate(Math.min(diaOriginal, ultimoDiaDelMes))
  return resultado
}

/** Fecha propuesta por defecto, en el formato `yyyy-mm-dd` que espera `<input type="date">`. */
export function defaultValidityDate(
  months: number = DEFAULT_VALIDITY_MONTHS,
  from: Date = new Date()
): string {
  return toDateInputValue(addMonths(from, months))
}

export function toDateInputValue(date: Date): string {
  const mes = String(date.getMonth() + 1).padStart(2, '0')
  const dia = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${mes}-${dia}`
}
