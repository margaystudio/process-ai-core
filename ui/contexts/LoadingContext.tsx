'use client'

import { createContext, useContext, useState, ReactNode } from 'react'
import LoadingOverlay from '@/components/layout/LoadingOverlay'

interface LoadingContextType {
  isLoading: boolean
  setLoading: (loading: boolean) => void
  withLoading: <T>(fn: () => Promise<T>) => Promise<T>
}

const LoadingContext = createContext<LoadingContextType | undefined>(undefined)

export function LoadingProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(false)

  const setLoading = (loading: boolean) => {
    setIsLoading(loading)
  }

  /**
   * Ejecuta una función asíncrona mostrando el loading automáticamente.
   * 
   * @param fn - Función asíncrona a ejecutar
   * @returns Resultado de la función
   */
  const withLoading = async <T,>(fn: () => Promise<T>): Promise<T> => {
    try {
      setIsLoading(true)
      return await fn()
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <LoadingContext.Provider value={{ isLoading, setLoading, withLoading }}>
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



