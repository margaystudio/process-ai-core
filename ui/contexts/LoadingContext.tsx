'use client'

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react'
import LoadingOverlay from '@/components/layout/LoadingOverlay'

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
      {isLoading && <LoadingOverlay />}
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



