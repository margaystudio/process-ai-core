/**
 * Proxy autenticado de imágenes embebidas (app/api/doc-assets/[...ruta]/route.ts).
 *
 * Lo que se protege:
 *  - Sin sesión → 401, NO un redirect al login (el consumidor es una <img>).
 *  - Lista blanca de rutas: no es un proxy abierto a la API con la sesión del usuario.
 *  - La credencial va en el header, nunca en la dirección.
 *  - Streaming: el cuerpo se pasa tal cual, sin bufferear la imagen en memoria.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NextRequest } from 'next/server'

const getSession = vi.fn()
vi.mock('@/lib/supabase/server', () => ({
  createClient: async () => ({ auth: { getSession } }),
}))

import { GET } from '@/app/api/doc-assets/[...ruta]/route'

const RUTA_IMAGEN = ['api', 'v1', 'documents', 'doc-1', 'versions', 'ver-1', 'assets', 'img01.png']

function pedido(ruta: string[], query = '', headers: Record<string, string> = {}) {
  const url = `http://front.test/api/doc-assets/${ruta.join('/')}${query}`
  return {
    request: new NextRequest(url, { headers }),
    params: Promise.resolve({ ruta }),
  }
}

function respuestaUpstream(body: BodyInit | null, init: ResponseInit = {}) {
  return new Response(body, {
    status: 200,
    headers: { 'content-type': 'image/png', etag: '"abc"', 'cache-control': 'private, no-cache' },
    ...init,
  })
}

describe('proxy de imágenes de documento', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getSession.mockReset()
    getSession.mockResolvedValue({ data: { session: { access_token: 'token-de-sesion' } } })
  })

  it('sin sesión devuelve 401 y no redirige al login', async () => {
    getSession.mockResolvedValue({ data: { session: null } })
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    const { request, params } = pedido(RUTA_IMAGEN)
    const response = await GET(request, { params })

    expect(response.status).toBe(401)
    // Un 3xx haría que el navegador pinte el HTML del login como si fuera la imagen.
    expect(response.headers.get('location')).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('manda la credencial en el header, nunca en la dirección', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(respuestaUpstream(new Uint8Array([1, 2, 3])))

    const { request, params } = pedido(RUTA_IMAGEN)
    await GET(request, { params })

    const [url, init] = fetchSpy.mock.calls[0]
    expect(String(url)).toContain('/api/v1/documents/doc-1/versions/ver-1/assets/img01.png')
    expect(String(url)).not.toContain('token')
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer token-de-sesion')
  })

  it('reenvía el tenant activo como header, que una <img> no puede mandar', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(respuestaUpstream(new Uint8Array([1])))

    const { request, params } = pedido(RUTA_IMAGEN, '?t=tenant-9')
    await GET(request, { params })

    const init = fetchSpy.mock.calls[0][1]
    expect((init?.headers as Record<string, string>)['X-Active-Tenant-Id']).toBe('tenant-9')
  })

  it('solo reenvía las rutas de la lista blanca', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    for (const ruta of [
      ['api', 'v1', 'documents'], // listado de documentos
      ['api', 'v1', 'workspaces', 'ws-1', 'members'], // datos del workspace
      ['api', 'v1', 'documents', 'doc-1', 'versions', 'ver-1', 'pdf'], // el PDF, que va por su propio camino
    ]) {
      const { request, params } = pedido(ruta)
      const response = await GET(request, { params })
      expect(response.status, ruta.join('/')).toBe(404)
    }
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('acepta las tres familias de imagen embebida', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(respuestaUpstream(new Uint8Array([1])))

    for (const ruta of [
      RUTA_IMAGEN,
      ['api', 'v1', 'documents', 'doc-1', 'editor-images', 'subida.png'],
      ['api', 'v1', 'artifacts', 'run-1', 'assets', 'paso1.png'],
    ]) {
      const { request, params } = pedido(ruta)
      const response = await GET(request, { params })
      expect(response.status, ruta.join('/')).toBe(200)
    }
  })

  it('pasa el cuerpo como stream, sin bufferearlo', async () => {
    const upstreamBody = new ReadableStream()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(respuestaUpstream(upstreamBody))

    const { request, params } = pedido(RUTA_IMAGEN)
    const response = await GET(request, { params })

    // El MISMO stream, no una copia leída a memoria.
    expect(response.body).toBe(upstreamBody)
  })

  it('propaga la revalidación condicional y el 304 sin cuerpo', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(null, { status: 304, headers: { etag: '"abc"' } }))

    const { request, params } = pedido(RUTA_IMAGEN, '', { 'if-none-match': '"abc"' })
    const response = await GET(request, { params })

    const init = fetchSpy.mock.calls[0][1]
    expect((init?.headers as Record<string, string>)['If-None-Match']).toBe('"abc"')
    expect(response.status).toBe(304)
    expect(response.body).toBeNull()
  })

  it('propaga el 403 de la API sin convertirlo en otra cosa', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'sin acceso' }), { status: 403 })
    )

    const { request, params } = pedido(RUTA_IMAGEN)
    const response = await GET(request, { params })

    expect(response.status).toBe(403)
  })
})
