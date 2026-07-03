import type { CookieOptions } from '@supabase/ssr'

const PROD_COOKIE_DOMAIN = '.margaystudio.io'

export function getSupabaseCookieDomain(): string | undefined {
  return (
    process.env.NEXT_PUBLIC_COOKIE_DOMAIN ??
    (process.env.NODE_ENV === 'production' ? PROD_COOKIE_DOMAIN : undefined)
  )
}

export function getSupabaseClientCookieOptions():
  | { domain: string; sameSite: 'lax'; secure: boolean; path: '/' }
  | undefined {
  const domain = getSupabaseCookieDomain()
  if (!domain) return undefined
  return {
    domain,
    sameSite: 'lax',
    secure: true,
    path: '/',
  }
}

export function withSupabaseCookieOptions(options?: CookieOptions): CookieOptions {
  const domain = getSupabaseCookieDomain()
  const useSecure =
    process.env.NODE_ENV === 'production' || Boolean(process.env.NEXT_PUBLIC_COOKIE_DOMAIN)

  return {
    ...options,
    path: options?.path ?? '/',
    sameSite: (options?.sameSite as CookieOptions['sameSite']) ?? 'lax',
    secure: options?.secure ?? useSecure,
    ...(domain ? { domain } : {}),
  }
}
