/**
 * Utilidades para agregar autenticación a las requests de la API.
 */

export const ACTIVE_TENANT_STORAGE_KEY = 'active_tenant_id'

/**
 * Tenant activo elegido en el selector (margay-workspace tenant id).
 */
export function getActiveTenantId(): string | null {
  if (typeof window === 'undefined') return null
  // `localStorage` puede no estar disponible aunque exista `window`: modo
  // privado con almacenamiento bloqueado, webviews embebidos, políticas de
  // cookies de terceros. Es un dato de conveniencia —el backend resuelve un
  // tenant igual—, así que no puede tumbar una request.
  try {
    return localStorage.getItem(ACTIVE_TENANT_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setActiveTenantId(tenantId: string): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, tenantId)
  } catch {
    // Sin persistencia, el tenant elegido dura lo que la pestaña. Preferible a
    // romper el cambio de tenant entero.
  }
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
/**
 * Completa el tenant activo en una request que ya lleva sesión.
 *
 * POR QUÉ ESTÁ ACÁ Y NO EN CADA LLAMADA
 * -------------------------------------
 * `getAuthHeaders()` agrega `Authorization` y `X-Active-Tenant-Id` juntos, pero
 * una docena de llamadas arman los headers a mano —porque suben multipart, o
 * porque piden un blob— y ponían solo el token. Sin el tenant, el backend
 * resuelve el workspace por defecto del usuario: para alguien con un solo
 * tenant no se nota, y para alguien con varios la request apunta a OTRO
 * workspace. Ahí no falla ruidosamente: devuelve 404 —el documento no existe en
 * ese workspace— y la pantalla se queda esperando algo que nunca llega.
 *
 * Se resuelve en el único lugar por el que pasan todas: agregarlo en cada
 * call-site es acordarse doce veces, y trece la próxima.
 *
 * Solo toca requests que YA llevan `Authorization`: si no hay sesión, no es una
 * llamada a la API del módulo y no se le inventa contexto.
 */
function conTenantActivo(init?: RequestInit): RequestInit | undefined {
  if (!getHeaderValue(init?.headers, 'Authorization')) return init
  if (getHeaderValue(init?.headers, 'X-Active-Tenant-Id')) return init

  const activeTenantId = getActiveTenantId()
  if (!activeTenantId) return init

  const headers = new Headers(init?.headers)
  headers.set('X-Active-Tenant-Id', activeTenantId)
  return { ...init, headers }
}

export async function authFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const conTenant = conTenantActivo(init)
  const response = await fetch(input, conTenant)
  if (response.status !== 401) return response

  const previousAuth = getHeaderValue(conTenant?.headers, 'Authorization')
  if (!previousAuth || !isReplayableBody(conTenant?.body)) return response

  const freshToken = await forceRefreshAccessToken()
  // Sin token nuevo (o idéntico al rechazado) el retry no puede cambiar el resultado.
  if (!freshToken || `Bearer ${freshToken}` === previousAuth) return response

  const retryHeaders = new Headers(conTenant?.headers)
  retryHeaders.set('Authorization', `Bearer ${freshToken}`)
  return fetch(input, { ...conTenant, headers: retryHeaders })
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
