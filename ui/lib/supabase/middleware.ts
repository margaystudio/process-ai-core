/**
 * Cliente de Supabase para uso en Middleware.
 *
 * Verifica la sesión en cada request. Si no hay sesión activa, redirige al hub
 * de autenticación: hub.margaystudio.io/login?next=<URL completa de process-ai>.
 * La cookie compartida en .margaystudio.io permite que la sesión del hub sea
 * válida aquí sin re-login.
 */

import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!supabaseUrl || !supabaseKey) {
    console.warn('⚠️  Supabase no configurado. Middleware de autenticación deshabilitado.')
    return NextResponse.next({ request })
  }

  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(supabaseUrl, supabaseKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
        supabaseResponse = NextResponse.next({ request })
        cookiesToSet.forEach(({ name, value, options }) =>
          supabaseResponse.cookies.set(name, value, options)
        )
      },
    },
  })

  // IMPORTANT: no poner lógica entre createServerClient y getUser().
  const {
    data: { user },
  } = await supabase.auth.getUser()

  // Rutas que no requieren sesión activa
  const publicPaths = ['/auth', '/invitations/accept']
  const isPublicPath = publicPaths.some((p) => request.nextUrl.pathname.startsWith(p))

  if (!user && !isPublicPath) {
    const HUB_URL = process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.margaystudio.io'
    // Construir la URL completa de destino para volver después del login
    const fullUrl = request.nextUrl.href
    const loginUrl = new URL(`${HUB_URL}/login`)
    loginUrl.searchParams.set('next', fullUrl)
    return NextResponse.redirect(loginUrl)
  }

  return supabaseResponse
}
