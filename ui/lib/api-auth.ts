/**
 * Utilidades para agregar autenticación a las requests de la API.
 */

export const ACTIVE_TENANT_STORAGE_KEY = 'active_tenant_id'

/**
 * Tenant activo elegido en el selector (margay-workspace tenant id).
 */
export function getActiveTenantId(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(ACTIVE_TENANT_STORAGE_KEY)
}

export function setActiveTenantId(tenantId: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, tenantId)
}

// Cache en memoria del access token: evita un round-trip a /api/auth/session
// (y el getUser() de Supabase en el middleware) por cada llamada a la API.
// Solo memoria de módulo, nunca localStorage (el token no debe persistir).
const TOKEN_REFRESH_MARGIN_SECONDS = 60

let cachedToken: string | null = null
let cachedTokenExp = 0 // claim exp del JWT, en epoch seconds
let inflightTokenRequest: Promise<string | null> | null = null

/** Decodifica el claim exp del JWT (base64url, sin verificar firma). */
function decodeJwtExp(token: string): number | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    const exp = (JSON.parse(json) as { exp?: number }).exp
    return typeof exp === 'number' ? exp : null
  } catch {
    return null
  }
}

async function fetchAccessToken(): Promise<string | null> {
  try {
    const response = await fetch('/api/auth/session', { credentials: 'include' })
    if (!response.ok) return null
    const data = (await response.json()) as { access_token?: string | null }
    const token = data.access_token ?? null
    if (token) {
      const exp = decodeJwtExp(token)
      // Sin exp decodificable no se cachea: cada llamada vuelve a pedirlo.
      if (exp !== null) {
        cachedToken = token
        cachedTokenExp = exp
      }
    }
    return token
  } catch {
    return null
  }
}

export async function getAccessToken(): Promise<string | null> {
  const nowSeconds = Date.now() / 1000
  if (cachedToken && cachedTokenExp - nowSeconds > TOKEN_REFRESH_MARGIN_SECONDS) {
    return cachedToken
  }
  // Single-flight: las llamadas concurrentes comparten el mismo fetch.
  if (!inflightTokenRequest) {
    inflightTokenRequest = fetchAccessToken().finally(() => {
      inflightTokenRequest = null
    })
  }
  return inflightTokenRequest
}

/** Invalida el token cacheado (llamar en logout). */
export function clearAccessTokenCache(): void {
  cachedToken = null
  cachedTokenExp = 0
  inflightTokenRequest = null
}

/**
 * Invalida el cache y pide un token fresco a /api/auth/session.
 * Para cuando el backend rechaza el token cacheado (sesión revocada,
 * rotación de claves) antes de que venza su exp.
 */
export async function forceRefreshAccessToken(): Promise<string | null> {
  clearAccessTokenCache()
  return getAccessToken()
}

function getHeaderValue(headers: HeadersInit | undefined, name: string): string | null {
  if (!headers) return null
  if (headers instanceof Headers) return headers.get(name)
  const lower = name.toLowerCase()
  if (Array.isArray(headers)) {
    const entry = headers.find(([key]) => key.toLowerCase() === lower)
    return entry?.[1] ?? null
  }
  const key = Object.keys(headers).find((k) => k.toLowerCase() === lower)
  return key ? (headers as Record<string, string>)[key] : null
}

/** Solo se reintenta si el body se puede reenviar tal cual (no streams). */
function isReplayableBody(body: BodyInit | null | undefined): boolean {
  if (body === undefined || body === null) return true
  return (
    typeof body === 'string' ||
    (typeof FormData !== 'undefined' && body instanceof FormData) ||
    (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) ||
    (typeof Blob !== 'undefined' && body instanceof Blob)
  )
}

/**
 * fetch con retry único ante 401: si la request llevaba Authorization y el
 * backend la rechaza, refresca el token (bypass del cache) y reintenta UNA vez.
 * Si el retry vuelve a dar 401, se devuelve esa respuesta tal cual (los
 * llamadores conservan su manejo de error / redirect a login actual).
 * Requests sin Authorization o con body no re-enviable no se reintentan.
 */
export async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const response = await fetch(input, init)
  if (response.status !== 401) return response

  const previousAuth = getHeaderValue(init?.headers, 'Authorization')
  if (!previousAuth || !isReplayableBody(init?.body)) return response

  const freshToken = await forceRefreshAccessToken()
  // Sin token nuevo (o idéntico al rechazado) el retry no puede cambiar el resultado.
  if (!freshToken || `Bearer ${freshToken}` === previousAuth) return response

  const retryHeaders = new Headers(init?.headers)
  retryHeaders.set('Authorization', `Bearer ${freshToken}`)
  return fetch(input, { ...init, headers: retryHeaders })
}

export async function getAuthHeaders(
  additionalHeaders: Record<string, string> = {}
): Promise<HeadersInit> {
  const token = await getAccessToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...additionalHeaders,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const activeTenantId = getActiveTenantId()
  if (activeTenantId) {
    headers['X-Active-Tenant-Id'] = activeTenantId
  }

  return headers
}
