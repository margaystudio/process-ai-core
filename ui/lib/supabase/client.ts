/**
 * Cliente de Supabase para uso en componentes del cliente (Client Components).
 *
 * En producción, la cookie de sesión se emite en el dominio padre `.margaystudio.io`
 * para que hub y process-ai compartan la sesión sin re-login.
 */

import { createBrowserClient } from '@supabase/ssr'

const PROD_COOKIE_DOMAIN = '.margaystudio.io'

export function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      'Supabase no está configurado. Por favor, configura NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY en .env.local'
    )
  }

  const cookieDomain = process.env.NEXT_PUBLIC_COOKIE_DOMAIN
    ?? (process.env.NODE_ENV === 'production' ? PROD_COOKIE_DOMAIN : undefined)

  return createBrowserClient(supabaseUrl, supabaseKey, {
    cookieOptions: cookieDomain
      ? { domain: cookieDomain, sameSite: 'lax', secure: true, path: '/' }
      : undefined,
  })
}

