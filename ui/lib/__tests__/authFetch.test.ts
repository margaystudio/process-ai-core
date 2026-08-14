import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { authFetch, clearAccessTokenCache } from '@/lib/api-auth'

const API = 'http://localhost:8000/api/v1/things'

/** JWT falso con claim exp (la firma no se verifica en el cliente). */
function fakeJwt(expSeconds: number): string {
  return `header.${btoa(JSON.stringify({ exp: expSeconds }))}.signature`
}

const FRESH_TOKEN = fakeJwt(Math.floor(Date.now() / 1000) + 3600)

function response(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

/** Mockea fetch: /api/auth/session devuelve FRESH_TOKEN; la API responde según la secuencia. */
function mockFetch(apiStatuses: number[]): ReturnType<typeof vi.fn> {
  let apiCall = 0
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).includes('/api/auth/session')) {
      return response(200, { access_token: FRESH_TOKEN })
    }
    const status = apiStatuses[Math.min(apiCall, apiStatuses.length - 1)]
    apiCall += 1
    return response(status)
  })
  global.fetch = fn as unknown as typeof fetch
  return fn
}

describe('authFetch (retry único ante 401)', () => {
  beforeEach(() => {
    clearAccessTokenCache()
  })

  it('401 → refresca el token y reintenta una vez con el token nuevo', async () => {
    const fetchMock = mockFetch([401, 200])

    const res = await authFetch(API, {
      method: 'POST',
      headers: { Authorization: 'Bearer stale-token', 'Content-Type': 'application/json' },
      body: JSON.stringify({ a: 1 }),
    })

    expect(res.status).toBe(200)
    // 3 llamadas: API (401) → /api/auth/session → API (retry)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const retryInit = fetchMock.mock.calls[2][1] as RequestInit
    const retryHeaders = new Headers(retryInit.headers)
    expect(retryHeaders.get('Authorization')).toBe(`Bearer ${FRESH_TOKEN}`)
    expect(retryHeaders.get('Content-Type')).toBe('application/json')
    expect(retryInit.body).toBe(JSON.stringify({ a: 1 }))
  })

  it('401 → retry también 401: propaga la respuesta sin loops', async () => {
    const fetchMock = mockFetch([401, 401])

    const res = await authFetch(API, {
      headers: { Authorization: 'Bearer stale-token' },
    })

    expect(res.status).toBe(401)
    // API (401) → session → API (401) y nada más: un solo retry
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('401 sin Authorization: no refresca ni reintenta', async () => {
    const fetchMock = mockFetch([401])

    const res = await authFetch(API, { method: 'GET' })

    expect(res.status).toBe(401)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('respuesta OK: no toca el cache ni reintenta', async () => {
    const fetchMock = mockFetch([200])

    const res = await authFetch(API, {
      headers: { Authorization: 'Bearer stale-token' },
    })

    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('authFetch — tenant activo', () => {
  const ORIGINAL = globalThis.localStorage

  function conTenant(valor: string | null) {
    Object.defineProperty(globalThis, 'localStorage', {
      value: { getItem: () => valor, setItem: () => {} },
      configurable: true,
    })
  }

  afterEach(() => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: ORIGINAL,
      configurable: true,
    })
  })

  it('completa X-Active-Tenant-Id cuando la request lleva sesión pero se olvidó el tenant', async () => {
    // El bug real: una docena de llamadas arman los headers a mano (multipart,
    // blobs) y mandaban solo el token. Sin el tenant, el backend resuelve el
    // workspace por defecto y quien tiene varios recibe 404.
    conTenant('tenant-activo')
    const fetchMock = vi.fn().mockResolvedValue(new Response('ok', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await authFetch('https://api.test/x', {
      headers: { Authorization: 'Bearer t1' },
    })

    const enviados = new Headers(fetchMock.mock.calls[0][1].headers)
    expect(enviados.get('X-Active-Tenant-Id')).toBe('tenant-activo')
    expect(enviados.get('Authorization')).toBe('Bearer t1')
  })

  it('respeta el tenant que el llamador ya puso', async () => {
    conTenant('tenant-activo')
    const fetchMock = vi.fn().mockResolvedValue(new Response('ok', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await authFetch('https://api.test/x', {
      headers: { Authorization: 'Bearer t1', 'X-Active-Tenant-Id': 'el-que-pidio' },
    })

    expect(
      new Headers(fetchMock.mock.calls[0][1].headers).get('X-Active-Tenant-Id')
    ).toBe('el-que-pidio')
  })

  it('no le inventa contexto a una request sin sesión', async () => {
    conTenant('tenant-activo')
    const fetchMock = vi.fn().mockResolvedValue(new Response('ok', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await authFetch('/api/auth/session')

    const init = fetchMock.mock.calls[0][1]
    expect(init?.headers ? new Headers(init.headers).get('X-Active-Tenant-Id') : null).toBeNull()
  })

  it('sin localStorage utilizable no rompe la request', async () => {
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: () => {
          throw new Error('acceso denegado al almacenamiento')
        },
      },
      configurable: true,
    })
    const fetchMock = vi.fn().mockResolvedValue(new Response('ok', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const res = await authFetch('https://api.test/x', {
      headers: { Authorization: 'Bearer t1' },
    })
    expect(res.status).toBe(200)
  })
})
