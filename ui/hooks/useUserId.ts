'use client'

/**
 * Hook para obtener el ID del usuario actual.
 * 
 * TODO: Cuando se implemente autenticación real, esto debería obtener el userId
 * del contexto de autenticación o de una cookie/token seguro.
 * 
 * Por ahora, obtiene el userId de localStorage (solo para desarrollo).
 * 
 * @returns ID del usuario o null si no está disponible
 */
export function useUserId(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('userId')
  }
  return null
}

