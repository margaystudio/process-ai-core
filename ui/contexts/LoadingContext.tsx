'use client'

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react'
import { Spinner } from '@/shared/ui/components'

interface LoadingContextType {
  isLoading: boolean
  setLoading: (loading: boolean) => void
  withLoading: <T>(fn: () => Promise<T>) => Promise<T>
}

const LoadingContext = createContext<LoadingContextType | undefined>(undefined)

export function LoadingProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(false)

  const setLoading = useCallback((loading: boolean) => {
    setIsLoading(loading)
  }, [])

  /**
   * Ejecuta una función asíncrona mostrando el loading automáticamente.
   *
   * @param fn - Función asíncrona a ejecutar
   * @returns Resultado de la función
   */
  const withLoading = useCallback(async <T,>(fn: () => Promise<T>): Promise<T> => {
    try {
      setIsLoading(true)
      return await fn()
    } finally {
      setIsLoading(false)
    }
  }, [])

  // useMemo: LoadingProvider envuelve TODA la app; sin esto cada toggle de
  // loading re-renderizaba todos los consumidores dos veces (objeto nuevo).
  const value = useMemo(
    () => ({ isLoading, setLoading, withLoading }),
    [isLoading, setLoading, withLoading]
  )

  return (
    <LoadingContext.Provider value={value}>
      {children}
      {/* Overlay bloqueante para acciones "de página" (guardar, aprobar) disparadas con
          `withLoading`. Usa el `Spinner` estándar del sistema — ya no el logo del margay
          girando. Sigue siendo la excepción "a pantalla completa" al criterio de que el
          spinner va SOLO dentro de un control: acá bloquea a propósito mientras la
          acción está en vuelo, para no permitir un segundo submit. */}
      {isLoading && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-ink-900/50">
          <div className="flex flex-col items-center gap-4 rounded-lg bg-white p-8 shadow-modal">
            <Spinner size="lg" className="text-ink-500" />
            <p className="text-sm font-medium text-ink-700">Procesando…</p>
          </div>
        </div>
      )}
    </LoadingContext.Provider>
  )
}

export function useLoading() {
  const context = useContext(LoadingContext)
  if (context === undefined) {
    throw new Error('useLoading must be used within a LoadingProvider')
  }
  return context
}



