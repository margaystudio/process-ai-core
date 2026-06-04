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

/**
 * Origin público real del módulo. Cloud Run termina el TLS: dentro del contenedor
 * request.nextUrl ve el host interno (localhost:8080). Para el `next` del SSO
 * usamos NEXT_PUBLIC_SITE_URL (horneado) y, si falta, los headers x-forwarded-*.
 */
function publicOrigin(request: NextRequest): string {
  const site = process.env.NEXT_PUBLIC_SITE_URL
  if (site) return site.replace(/\/+$/, '')
  const proto = request.headers.get('x-forwarded-proto') ?? 'https'
  const host = request.headers.get('x-forwarded-host') ?? request.headers.get('host')
  return host ? `${proto}://${host}` : request.nextUrl.origin
}

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
    // URL pública completa de destino para volver después del login (no el host interno)
    const fullUrl = `${publicOrigin(request)}${request.nextUrl.pathname}${request.nextUrl.search}`
    const loginUrl = new URL(`${HUB_URL}/login`)
    loginUrl.searchParams.set('next', fullUrl)
    return NextResponse.redirect(loginUrl)
  }

  return supabaseResponse
}
