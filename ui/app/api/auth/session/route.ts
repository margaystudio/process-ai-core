import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

/**
 * Expone el access token leyendo cookies HttpOnly en el servidor.
 * El browser client no puede leer la cookie SSO del Hub; esta ruta es el puente.
 */
export async function GET() {
  const supabase = await createClient()
  const {
    data: { session },
    error,
  } = await supabase.auth.getSession()

  if (error || !session?.access_token) {
    return NextResponse.json({ access_token: null }, { status: 401 })
  }

  return NextResponse.json({ access_token: session.access_token })
}
