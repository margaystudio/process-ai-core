/**
 * Callback route para OAuth y Magic Links de Supabase.
 * 
 * Esta ruta maneja:
 * - Callbacks de OAuth (Google, Facebook, etc.)
 * - Magic links enviados por email
 * - Verificación de tokens
 */

import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { syncUser } from '@/lib/api'

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const next = requestUrl.searchParams.get('next') || '/workspace'

  if (code) {
    const supabase = await createClient()
    
    // Intercambiar código por sesión
    const { data, error } = await supabase.auth.exchangeCodeForSession(code)

    if (error) {
      console.error('Error intercambiando código:', error)
      return NextResponse.redirect(new URL(`/login?error=${encodeURIComponent(error.message)}`, requestUrl.origin))
    }

    if (data.user) {
      // Sincronizar usuario con backend
      try {
        const metadata = data.user.user_metadata || {}
        const appMetadata = data.user.app_metadata || {}
        const providers = appMetadata.providers || []
        const authProvider = providers.length > 0 ? providers[0] : 'supabase'

        const syncResponse = await syncUser({
          supabase_user_id: data.user.id,
          email: data.user.email || '',
          name: metadata.name || metadata.full_name || data.user.email?.split('@')[0] || 'Usuario',
          auth_provider: authProvider,
          metadata: {
            avatar_url: metadata.avatar_url,
            ...metadata,
          },
        })
        
        // El userId local se guardará en localStorage desde el cliente cuando se cargue la página
      } catch (err) {
        console.error('Error sincronizando usuario:', err)
        // No redirigir a error, el usuario ya está autenticado
      }
    }

    // Redirigir a la página solicitada, o a onboarding si no tiene workspaces
    // Por ahora redirigimos a workspace, que manejará el caso de no tener workspaces
    return NextResponse.redirect(new URL(next, requestUrl.origin))
  }

  // Si no hay código, redirigir a login
  return NextResponse.redirect(new URL('/login', requestUrl.origin))
}


