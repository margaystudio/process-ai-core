/**
 * Utilidades para formatear fechas con la zona horaria de Uruguay (GMT-3).
 * 
 * El backend guarda las fechas en UTC, así que necesitamos convertirlas
 * a la zona horaria de Uruguay (America/Montevideo) antes de mostrarlas.
 */

const TIMEZONE = 'America/Montevideo'
const LOCALE = 'es-UY'

/**
 * Convierte una fecha UTC a la zona horaria de Uruguay y la formatea.
 * 
 * @param date - Fecha como string ISO (UTC) o objeto Date
 * @param options - Opciones adicionales para el formateo
 * @returns String formateado con fecha y hora en zona horaria de Uruguay
 */
export function formatDateTime(
  date: string | Date,
  options?: Intl.DateTimeFormatOptions
): string {
  // Asegurarnos de que la fecha se interprete como UTC
  const dateStr = typeof date === 'string' ? date : date.toISOString()
  // Si no tiene 'Z' al final, agregarlo para indicar UTC
  const utcDateStr = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const dateObj = new Date(utcDateStr)
  
  return dateObj.toLocaleString(LOCALE, {
    timeZone: TIMEZONE,
    ...options,
  })
}

/**
 * Convierte una fecha UTC a la zona horaria de Uruguay y la formatea (solo fecha).
 * 
 * @param date - Fecha como string ISO (UTC) o objeto Date
 * @param options - Opciones adicionales para el formateo
 * @returns String formateado con solo la fecha en zona horaria de Uruguay
 */
export function formatDate(
  date: string | Date,
  options?: Intl.DateTimeFormatOptions
): string {
  // Asegurarnos de que la fecha se interprete como UTC
  const dateStr = typeof date === 'string' ? date : date.toISOString()
  // Si no tiene 'Z' al final, agregarlo para indicar UTC
  const utcDateStr = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const dateObj = new Date(utcDateStr)
  
  return dateObj.toLocaleDateString(LOCALE, {
    timeZone: TIMEZONE,
    ...options,
  })
}

/**
 * Convierte una fecha UTC a la zona horaria de Uruguay y la formatea (solo hora).
 * 
 * @param date - Fecha como string ISO (UTC) o objeto Date
 * @param options - Opciones adicionales para el formateo
 * @returns String formateado con solo la hora en zona horaria de Uruguay
 */
export function formatTime(
  date: string | Date,
  options?: Intl.DateTimeFormatOptions
): string {
  // Asegurarnos de que la fecha se interprete como UTC
  const dateStr = typeof date === 'string' ? date : date.toISOString()
  // Si no tiene 'Z' al final, agregarlo para indicar UTC
  const utcDateStr = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const dateObj = new Date(utcDateStr)
  
  return dateObj.toLocaleTimeString(LOCALE, {
    timeZone: TIMEZONE,
    ...options,
  })
}
