/**
 * Lista blanca de rutas que el proxy de doc-assets
 * (`app/api/doc-assets/[...ruta]/route.ts`) tiene permitido reenviar a la API.
 * Ver el comentario de ese archivo para el porqué del proxy.
 *
 * Extraído a un módulo aparte para poder testear los casos borde (dot-segments,
 * rutas de otras APIs, etc.) sin tener que montar el route handler completo.
 */

const PATRON_VERSION_ASSET = /^api\/v1\/documents\/[^/]+\/versions\/[^/]+\/assets\/[^/]+$/
const PATRON_EDITOR_IMAGE = /^api\/v1\/documents\/[^/]+\/editor-images\/[^/]+$/

/** Un segmento de path real: no vacío, y no `.` ni `..` (evita path traversal). */
function esSegmentoSeguro(segmento: string): boolean {
  return segmento.length > 0 && segmento !== '.' && segmento !== '..'
}

/**
 * `api/v1/artifacts/{runId}/assets/{...archivo}`: el archivo puede traer
 * subdirectorios legítimos (ej. `assets/frames_vid1/step01.png`, ver
 * `api/routes/artifacts.py::get_artifact`, que sirve `{filename:path}`), pero
 * ningún segmento puede ser `.` ni `..`. Un regex con `.+` suelto en la cola
 * (la versión anterior) los dejaba pasar.
 */
function esArtifactAsset(segmentos: string[]): boolean {
  const [p0, p1, p2, runId, p4, ...archivo] = segmentos
  if (p0 !== 'api' || p1 !== 'v1' || p2 !== 'artifacts' || p4 !== 'assets') return false
  if (!runId || !esSegmentoSeguro(runId)) return false
  if (archivo.length === 0) return false
  return archivo.every(esSegmentoSeguro)
}

/** True si el proxy tiene permitido reenviar esta ruta (siempre GET, ver el route handler). */
export function esRutaDocAssetPermitida(segmentos: string[]): boolean {
  const ruta = segmentos.join('/')
  return (
    PATRON_VERSION_ASSET.test(ruta) ||
    PATRON_EDITOR_IMAGE.test(ruta) ||
    esArtifactAsset(segmentos)
  )
}
