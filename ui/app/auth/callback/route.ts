/**
 * Callback de Supabase para process-ai.
 *
 * Intercambia el code por una sesión y emite la cookie en el dominio padre
 * (.margaystudio.io en prod) para que hub y process-ai compartan la sesión.
 *
 * El parámetro `next` puede ser:
 *   - URL absoluta (ej. https://process.margaystudio.io/workspace) → redirect directo
 *   - Path relativo (ej. /workspace) → redirect dentro de process-ai
 */

import { createServerClient, type CookieOptions } from '@supabase/ssr'
import { NextRequest, NextResponse } from 'next/server'

const PROD_COOKIE_DOMAIN = '.margaystudio.io'

const ALLOWED_ORIGINS = [
  'https://process.margaystudio.io',
  'https://hub.margaystudio.io',
  'http://localhost:3000',
  'http://localhost:3001',
  'https://process.local.margaystudio.io:3000',
  'https://hub.local.margaystudio.io:3001',
]

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const accessToken = requestUrl.searchParams.get('access_token')
  const refreshToken = requestUrl.searchParams.get('refresh_token')
  const nextParam = requestUrl.searchParams.get('next') || '/'

  const HUB_URL = process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.margaystudio.io'
  const cookieDomain = process.env.NEXT_PUBLIC_COOKIE_DOMAIN
    ?? (process.env.NODE_ENV === 'production' ? PROD_COOKIE_DOMAIN : undefined)

  // Resolver URL de destino segura
  let redirectTarget: URL
  try {
    const parsed = new URL(nextParam)
    redirectTarget = (['http:', 'https:'].includes(parsed.protocol) && ALLOWED_ORIGINS.includes(parsed.origin))
      ? parsed
      : new URL('/', requestUrl.origin)
  } catch {
    const safePath = nextParam.startsWith('/') && !nextParam.startsWith('//') ? nextParam : '/'
    redirectTarget = new URL(safePath, requestUrl.origin)
  }

  let response = NextResponse.next({ request: { headers: request.headers } })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() { return request.cookies.getAll() },
        setAll(cookiesToSet: Array<{ name: string; value: string; options?: CookieOptions }>) {
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, {
              ...options,
              httpOnly: options?.httpOnly ?? true,
              secure: options?.secure ?? (process.env.NODE_ENV === 'production'),
              sameSite: options?.sameSite ?? 'lax',
              path: options?.path ?? '/',
              ...(cookieDomain ? { domain: cookieDomain } : {}),
            })
          })
        },
      },
    }
  )

  if (accessToken && refreshToken) {
    // El hub ya hizo el exchange PKCE y nos pasa los tokens directamente.
    // Usamos setSession para establecer la sesión local sin necesitar el code verifier.
    const { error } = await supabase.auth.setSession({
      access_token: accessToken,
      refresh_token: refreshToken,
    })
    if (error) {
      console.error('[callback] setSession error:', error.message)
      return NextResponse.redirect(`${HUB_URL}/login?error=${encodeURIComponent(error.message)}`)
    }
  } else if (code) {
    // Flujo directo: el callback llega con un code (mismo dominio o dev sin hub).
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (error) {
      console.error('[callback] exchange error:', error.message)
      return NextResponse.redirect(`${HUB_URL}/login?error=${encodeURIComponent(error.message)}`)
    }
  } else {
    return NextResponse.redirect(`${HUB_URL}/login?error=no_code`)
  }

  const redirect = NextResponse.redirect(redirectTarget)
  response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie))
  return redirect
}
