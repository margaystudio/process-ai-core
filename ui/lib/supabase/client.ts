/**
 * Cliente de Supabase para uso en componentes del cliente (Client Components).
 * 
 * Este cliente se usa en componentes que tienen 'use client' y se ejecutan en el navegador.
 */

import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    throw new Error(
      'Supabase no está configurado. Por favor, configura NEXT_PUBLIC_SUPABASE_URL y NEXT_PUBLIC_SUPABASE_ANON_KEY en .env.local'
    )
  }

  return createBrowserClient(supabaseUrl, supabaseKey)
}

