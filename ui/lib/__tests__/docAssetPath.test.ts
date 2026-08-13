/**
 * Lista blanca de rutas del proxy de doc-assets (`lib/docAssetPath.ts`).
 *
 * Lo que se protege: que el proxy siga siendo un allow-list anclado de punta a
 * punta y no un proxy abierto a cualquier endpoint GET de la API con la sesión
 * del usuario. En particular, que la familia `artifacts/.../assets/...` (que sí
 * admite subdirectorios legítimos) no habilite path traversal vía `.` o `..`.
 */

import { describe, expect, it } from 'vitest'
import { esRutaDocAssetPermitida } from '@/lib/docAssetPath'

function segmentos(ruta: string): string[] {
  return ruta.split('/')
}

describe('esRutaDocAssetPermitida', () => {
  it('acepta las tres familias legítimas', () => {
    expect(esRutaDocAssetPermitida(segmentos('api/v1/documents/doc-1/versions/ver-1/assets/img.png'))).toBe(true)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/documents/doc-1/editor-images/subida.png'))).toBe(true)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/paso1.png'))).toBe(true)
  })

  it('acepta subdirectorios legítimos en assets de un artifact', () => {
    expect(
      esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/frames_vid1/step01_1.png'))
    ).toBe(true)
    expect(
      esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/a/b/c/hoja.png'))
    ).toBe(true)
  })

  it('rechaza dot-segments en cualquier posición de la cola de assets', () => {
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/..'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/.'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/../secret.env'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/x/../../secret'))).toBe(false)
    expect(
      esRutaDocAssetPermitida(['api', 'v1', 'artifacts', 'run-1', 'assets', 'x', '..', 'y'])
    ).toBe(false)
  })

  it('permite nombres de archivo que empiezan con punto pero no son "." ni ".."', () => {
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/..png'))).toBe(true)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/.oculto'))).toBe(true)
  })

  it('rechaza un runId con dot-segment', () => {
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/../assets/img.png'))).toBe(false)
  })

  it('exige al menos un segmento de archivo tras assets/ en un artifact', () => {
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/assets/'))).toBe(false)
    expect(esRutaDocAssetPermitida(['api', 'v1', 'artifacts', 'run-1', 'assets'])).toBe(false)
  })

  it('rechaza rutas de otras APIs (no es un proxy abierto)', () => {
    expect(esRutaDocAssetPermitida(segmentos('api/v1/documents'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/workspaces/ws-1/members'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/documents/doc-1/versions/ver-1/pdf'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/documents/doc-1'))).toBe(false)
    expect(esRutaDocAssetPermitida(segmentos('api/v1/artifacts/run-1/pdf'))).toBe(false)
  })

  it('rechaza rutas con segmentos vacíos (doble barra)', () => {
    expect(esRutaDocAssetPermitida(['api', 'v1', 'documents', 'doc-1', 'versions', 'ver-1', 'assets', ''])).toBe(
      false
    )
    expect(esRutaDocAssetPermitida(['api', 'v1', 'artifacts', 'run-1', 'assets', ''])).toBe(false)
  })

  it('barras codificadas dentro de un segmento no rompen el allow-list', () => {
    // Next decodifica cada segmento antes de llamar al handler: un "%2F" dentro
    // de un segmento del catch-all NO produce una barra real de separación acá,
    // así que la validación lo trata como un único segmento con ese carácter.
    expect(esRutaDocAssetPermitida(['api', 'v1', 'artifacts', 'run-1', 'assets', 'x/y'])).toBe(true)
    expect(esRutaDocAssetPermitida(['api', 'v1', 'artifacts', 'run-1', 'assets', '..%2Fsecret'])).toBe(true)
  })
})
