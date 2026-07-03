/**
 * Cliente de Supabase para uso en componentes del cliente (Client Components).
 *
 * En producción, la cookie de sesión se emite en el dominio padre `.margaystudio.io`
 * para que hub y process-ai compartan la sesión sin re-login.
 */

import { createBrowserClient } from '@supabase/ssr'
import { getSupabaseClientCookieOptions } from '@/lib/supabase/cookie-options'

const PROD_COOKIE_DOMAIN = '.margaystudio.io'

export function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      'Supabase no está configurado. Por favor, configura NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY en .env.local'
    )
  }

  const cookieOptions = getSupabaseClientCookieOptions()

  return createBrowserClient(supabaseUrl, supabaseKey, {
    cookieOptions: cookieOptions ?? undefined,
  })
}

