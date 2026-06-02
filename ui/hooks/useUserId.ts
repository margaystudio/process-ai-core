'use client'

import { useEffect, useState } from 'react'

const SUPABASE_TIMEOUT_MS = 6000

/**
 * Devuelve el ID local del usuario (UUID de la BD de process-ai).
 *
 * El ID se guarda en localStorage bajo 'local_user_id' por useUserValidation
 * (que llama a GET /api/v1/users/me y lo persiste). Este hook simplemente
 * lee ese valor y reacciona a cambios vía Supabase onAuthStateChange.
 */
export function useUserId(): string | null {
  const [userId, setUserId] = useState<string | null>(null)

  useEffect(() => {
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

    if (!supabaseUrl || !supabaseKey) {
      const storedUserId = localStorage.getItem('userId')
      setUserId(storedUserId)
      return
    }

    async function init() {
      try {
        const { createClient } = await import('@/lib/supabase/client')
        const supabase = createClient()

        const getSessionWithTimeout = () =>
          Promise.race([
            supabase.auth.getSession(),
            new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error('SupabaseTimeout')), SUPABASE_TIMEOUT_MS)
            ),
          ])

        const { data: { session } } = await getSessionWithTimeout()

        if (session?.user) {
          const storedUserId = localStorage.getItem('local_user_id')
          if (storedUserId) {
            setUserId(storedUserId)
          }
          // Si no hay local_user_id todavía, useUserValidation lo seteará
          // y el evento localStorageChange de abajo lo va a capturar.
        } else {
          setUserId(null)
          localStorage.removeItem('local_user_id')
        }

        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
          if (session?.user) {
            const storedUserId = localStorage.getItem('local_user_id')
            setUserId(storedUserId)
          } else {
            setUserId(null)
            localStorage.removeItem('local_user_id')
          }
        })

        const handleStorageChange = (e: StorageEvent) => {
          if (e.key === 'local_user_id' && e.newValue) {
            setUserId(e.newValue)
          }
        }
        window.addEventListener('storage', handleStorageChange)

        const handleCustomStorageChange = (e: Event) => {
          const customEvent = e as CustomEvent
          if (customEvent.detail?.key === 'local_user_id' && customEvent.detail?.value) {
            setUserId(customEvent.detail.value)
          }
        }
        window.addEventListener('localStorageChange', handleCustomStorageChange as EventListener)

        return () => {
          subscription.unsubscribe()
          window.removeEventListener('storage', handleStorageChange)
          window.removeEventListener('localStorageChange', handleCustomStorageChange as EventListener)
        }
      } catch (err) {
        if (err instanceof Error && err.message === 'SupabaseTimeout') {
          console.warn('[useUserId] Timeout conectando con Supabase, usando localStorage')
        } else {
          console.warn('[useUserId] Error inicializando Supabase:', err)
        }
        const storedUserId = localStorage.getItem('local_user_id') ?? localStorage.getItem('userId')
        setUserId(storedUserId)
      }
    }

    init()
  }, [])

  return userId
}
