/**
 * Cliente de Supabase para uso en Server Components y Server Actions.
 *
 * En producción, la cookie de sesión se emite en el dominio padre `.margaystudio.io`
 * para que hub y process-ai compartan la sesión sin re-login.
 */

import { createServerClient, type CookieOptions } from '@supabase/ssr'
import { cookies } from 'next/headers'

const PROD_COOKIE_DOMAIN = '.margaystudio.io'

export async function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      'Supabase no está configurado. Por favor, configura NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY en .env.local'
    )
  }

  const cookieDomain = process.env.NEXT_PUBLIC_COOKIE_DOMAIN
    ?? (process.env.NODE_ENV === 'production' ? PROD_COOKIE_DOMAIN : undefined)
  const cookieStore = await cookies()

  return createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet: Array<{ name: string; value: string; options?: CookieOptions }>) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, {
              ...options,
              ...(cookieDomain ? { domain: cookieDomain } : {}),
            })
          )
        } catch {
          // Called from a Server Component — safe to ignore (middleware refreshes cookies).
        }
      },
    },
  })
}

