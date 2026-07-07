import { ACTIVE_TENANT_STORAGE_KEY } from '@/lib/api-auth'

const PROD_COOKIE_DOMAIN = '.margaystudio.io'

function getSupabaseAuthCookiePrefix(): string | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  if (!url) return null
  try {
    const projectRef = new URL(url).hostname.split('.')[0]
    return `sb-${projectRef}-auth-token`
  } catch {
    return null
  }
}

function getCookieDomain(): string | undefined {
  return (
    process.env.NEXT_PUBLIC_COOKIE_DOMAIN ??
    (process.env.NODE_ENV === 'production' ? PROD_COOKIE_DOMAIN : undefined)
  )
}

/** Borra cookies Supabase sin llamar a la Auth API (evita bucles refresh_token_not_found). */
export function clearSupabaseAuthCookies(): void {
  if (typeof document === 'undefined') return

  const prefix = getSupabaseAuthCookiePrefix()
  if (!prefix) return

  const names = document.cookie
    .split(';')
    .map((part) => part.split('=')[0]?.trim())
    .filter((name): name is string => Boolean(name && name.startsWith(prefix)))

  if (names.length === 0) return

  const domain = getCookieDomain()
  const host = window.location.hostname
  const useSecure = window.location.protocol === 'https:' || Boolean(domain)
  const domains = new Set<string | undefined>([undefined, host])
  if (domain) {
    domains.add(domain)
    domains.add(domain.replace(/^\./, ''))
  }

  for (const name of names) {
    for (const cookieDomain of domains) {
      const domainPart = cookieDomain ? `; Domain=${cookieDomain}` : ''
      const securePart = useSecure ? '; Secure' : ''
      document.cookie = `${name}=; Max-Age=0; Path=/${domainPart}${securePart}`
    }
  }
}

/** Limpia cookies Supabase y claves locales de sesión/workspace. */
export function clearLocalAuthState(): void {
  clearSupabaseAuthCookies()
  if (typeof localStorage === 'undefined') return
  localStorage.removeItem('local_user_id')
  localStorage.removeItem('userId')
  localStorage.removeItem('dev_user_id')
  localStorage.removeItem(ACTIVE_TENANT_STORAGE_KEY)
}
