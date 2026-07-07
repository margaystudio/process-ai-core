import { clearLocalAuthState } from '@/lib/clear-auth-state'

const DEFAULT_HUB_URL = 'https://hub.margaystudio.io'

function getHubUrl(): string {
  return (process.env.NEXT_PUBLIC_HUB_URL ?? DEFAULT_HUB_URL).replace(/\/+$/, '')
}
/**
 * URL del login del Hub (SSO). Por defecto incluye `next` con la página actual
 * para volver a process-ai tras autenticarse.
 *
 * @param next - URL de retorno. `false` omite el parámetro (p. ej. tras cerrar sesión).
 */
export function getHubLoginUrl(next?: string | false): string {
  const hub = getHubUrl()
  if (next === false) {
    return `${hub}/login`
  }
  const returnTo = next ?? (typeof window !== 'undefined' ? window.location.href : '')
  if (!returnTo) {
    return `${hub}/login`
  }
  return `${hub}/login?next=${encodeURIComponent(returnTo)}`
}

type RedirectToHubLoginOptions = {
  /** Limpia cookies/localStorage antes de ir al Hub (solo en sign-out explícito). */
  clearStale?: boolean
}

/** Redirección completa al login del Hub (evita /login local inexistente). */
export function redirectToHubLogin(
  next?: string | false,
  options?: RedirectToHubLoginOptions
): void {
  if (typeof window === 'undefined') return
  if (options?.clearStale) clearLocalAuthState()
  window.location.assign(getHubLoginUrl(next))
}