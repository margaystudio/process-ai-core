/**
 * Lógica pura para la elección de tipo documental en la importación por lote
 * (`app/import/page.tsx`). Sin imports de React: testeable sin DOM.
 *
 * Espeja del lado del cliente lo que resuelve el backend en
 * `process_ai_core/domains/document_types/resolucion.py::resolver_tipo_de_importacion`,
 * para que lo que el usuario ve ANTES de importar (tipo precargado, si va a
 * pedir aprobación) coincida con lo que el backend va a aplicar. Si esa
 * resolución cambia del lado del servidor, hay que actualizar esto también.
 */

import type { DocumentType, FolderGovernance } from './api'

/**
 * Espeja `TIPO_POR_DEFECTO` de resolucion.py: la última red de contención
 * cuando ni quien importa eligió un tipo ni la carpeta (ni sus ancestros)
 * definen uno. Se elige el tipo más exigente a propósito.
 */
export const TIPO_DOCUMENTAL_POR_DEFECTO = 'procedimiento'

/**
 * Tipo documental a precargar para una carpeta, según su gobierno efectivo
 * (herencia ya resuelta por `GET /folders/{id}/governance`). Nunca devuelve
 * vacío: si la carpeta no define nada (o todavía no sabemos, ej. gobierno
 * inaccesible), cae al mismo default que aplicaría el backend a ciegas.
 */
export function resolverTipoPorDefecto(
  governance: FolderGovernance | null | undefined
): string {
  return governance?.default_document_type.value ?? TIPO_DOCUMENTAL_POR_DEFECTO
}

/**
 * El tipo efectivo de una fila: el override puntual del archivo si lo hay,
 * si no el default vigente del lote. El override nunca se pisa solo porque
 * cambie el default del lote — es una elección explícita de la fila.
 */
export function tipoEfectivoDeFila(
  override: string | null | undefined,
  tipoDelLote: string
): string {
  return override ?? tipoDelLote
}

/**
 * Si el tipo pide aprobación, según su behavior `aprobacion`. Si el tipo
 * todavía no cargó o no está en la lista (tenant sin ese tipo activo), asume
 * que sí requiere aprobación: es el lado seguro, igual que el fallback del
 * backend cuando no encuentra el tipo pedido.
 */
export function tipoRequiereAprobacion(
  key: string,
  documentTypes: DocumentType[]
): boolean {
  const tipo = documentTypes.find((candidate) => candidate.key === key)
  if (!tipo) return true
  return Boolean(tipo.behaviors.aprobacion)
}

/**
 * Copy de la consecuencia de importar con ese tipo, en palabras de quien
 * usa la pantalla — nunca "behaviors" ni el nombre técnico del estado.
 */
export function consecuenciaImportacion(requiresApproval: boolean): string {
  return requiresApproval
    ? 'Va a pedir aprobación antes de quedar vigente'
    : 'Va a quedar vigente y consultable de inmediato'
}
