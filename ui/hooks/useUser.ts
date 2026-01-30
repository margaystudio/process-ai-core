'use client'

import { useEffect, useState } from 'react'

interface UserInfo {
  email: string | null
  name: string | null
  avatarUrl: string | null
  supabaseUserId: string | null
}

/**
 * Hook para obtener la información del usuario autenticado desde Supabase.
 * 
 * @returns Información del usuario o null si no está autenticado
 */
export function useUser(): UserInfo | null {
  const [user, setUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    async function getUserInfo() {
      try {
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
        const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

        if (!supabaseUrl || !supabaseKey) {
          // Supabase no configurado: retornar null
          setUser(null)
          return
        }

        const { createClient } = await import('@/lib/supabase/client')
        const supabase = createClient()
        
        const { data: { session } } = await supabase.auth.getSession()
        
        if (session?.user) {
          const metadata = session.user.user_metadata || {}
          setUser({
            email: session.user.email || null,
            name: metadata.name || metadata.full_name || session.user.email?.split('@')[0] || null,
            avatarUrl: metadata.avatar_url || null,
            supabaseUserId: session.user.id,
          })
        } else {
          setUser(null)
        }

        // Escuchar cambios en la sesión
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
          if (session?.user) {
            const metadata = session.user.user_metadata || {}
            setUser({
              email: session.user.email || null,
              name: metadata.name || metadata.full_name || session.user.email?.split('@')[0] || null,
              avatarUrl: metadata.avatar_url || null,
              supabaseUserId: session.user.id,
            })
          } else {
            setUser(null)
          }
        })

        return () => {
          subscription.unsubscribe()
        }
      } catch (err) {
        console.warn('Error obteniendo información del usuario:', err)
        setUser(null)
      }
    }

    getUserInfo()
  }, [])

  return user
}
