/**
 * Utilidades para agregar autenticación a las requests de la API.
 * 
 * Este módulo proporciona funciones para obtener el token de Supabase
 * y agregarlo automáticamente a los headers de las requests.
 */

import { createClient } from '@/lib/supabase/client'

/**
 * Obtiene el token de acceso actual de Supabase.
 * 
 * @returns Token JWT o null si no hay sesión
 */
export async function getAccessToken(): Promise<string | null> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token || null
}

/**
 * Crea headers con autenticación para requests a la API.
 * 
 * @param additionalHeaders - Headers adicionales a incluir
 * @returns Headers con Authorization incluido si hay sesión
 */
export async function getAuthHeaders(additionalHeaders: Record<string, string> = {}): Promise<HeadersInit> {
  const token = await getAccessToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...additionalHeaders,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  return headers
}



