'use client'

import { useEffect, useState } from 'react'

/**
 * Hook para obtener el ID del usuario actual desde Supabase Auth.
 * 
 * Si Supabase no está configurado, retorna null y permite usar localStorage como fallback.
 * 
 * @returns ID del usuario local (de la DB) o null si no está autenticado
 */
export function useUserId(): string | null {
  const [userId, setUserId] = useState<string | null>(null)

  useEffect(() => {
    // Verificar si Supabase está configurado
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

    if (!supabaseUrl || !supabaseKey) {
      // Supabase no configurado: usar localStorage como fallback (modo desarrollo)
      const storedUserId = localStorage.getItem('userId')
      setUserId(storedUserId)
      return
    }

    // Supabase configurado: usar autenticación real
    async function getUserId() {
      try {
        const { createClient } = await import('@/lib/supabase/client')
        const supabase = createClient()
        
        const { data: { session } } = await supabase.auth.getSession()
        
        if (session?.user) {
          // El userId local se obtiene después de sincronizar con el backend
          // Se guarda en localStorage cuando se sincroniza el usuario
          const storedUserId = localStorage.getItem('local_user_id')
          if (storedUserId) {
            setUserId(storedUserId)
          } else {
            // Si no hay userId local guardado, intentar obtenerlo del backend
            // usando el token de Supabase
            try {
              const token = (await supabase.auth.getSession()).data.session?.access_token
              if (token) {
                const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/user`, {
                  headers: {
                    'Authorization': `Bearer ${token}`
                  }
                })
                if (response.ok) {
                  const data = await response.json()
                  if (data.user?.id) {
                    localStorage.setItem('local_user_id', data.user.id)
                    setUserId(data.user.id)
                  }
                }
              }
            } catch (err) {
              console.warn('Error obteniendo userId del backend:', err)
              // Continuar sin userId, se sincronizará después
            }
          }
        } else {
          setUserId(null)
          localStorage.removeItem('local_user_id')
        }

        // Escuchar cambios en la sesión
        const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
          if (session?.user) {
            const storedUserId = localStorage.getItem('local_user_id')
            setUserId(storedUserId || session.user.id)
          } else {
            setUserId(null)
            localStorage.removeItem('local_user_id')
          }
        })

        // Escuchar cambios en localStorage (para detectar cuando se guarda user_id después de aceptar invitación)
        // Nota: storage events solo se disparan desde otras ventanas, así que usamos un evento personalizado
        const handleStorageChange = (e: StorageEvent) => {
          if (e.key === 'local_user_id' && e.newValue) {
            console.log('[useUserId] Detectado cambio en local_user_id (storage event):', e.newValue)
            setUserId(e.newValue)
          }
        }
        window.addEventListener('storage', handleStorageChange)

        // Escuchar evento personalizado que se dispara cuando se guarda user_id en la misma ventana
        const handleCustomStorageChange = (e: Event) => {
          const customEvent = e as CustomEvent
          if (customEvent.detail?.key === 'local_user_id' && customEvent.detail?.value) {
            console.log('[useUserId] Detectado cambio en local_user_id (custom event):', customEvent.detail.value)
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
        // Si hay error creando el cliente, usar localStorage como fallback
        console.warn('Error inicializando Supabase, usando localStorage:', err)
        const storedUserId = localStorage.getItem('userId')
        setUserId(storedUserId)
      }
    }

    getUserId()
  }, [])

  return userId
}

