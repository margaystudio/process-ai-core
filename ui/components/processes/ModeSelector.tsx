'use client'

import { useState, useEffect } from 'react'
import { getCatalogOptions, CatalogOption } from '@/lib/api'

interface ModeSelectorProps {
  value: 'operativo' | 'gestion'
  onChange: (value: 'operativo' | 'gestion') => void
}

export default function ModeSelector({ value, onChange }: ModeSelectorProps) {
  const [modeOptions, setModeOptions] = useState<CatalogOption[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadCatalog() {
      try {
        // El modo del documento es la audiencia
        const options = await getCatalogOptions('audience').catch(() => [])
        setModeOptions(options)
        
        // Si hay opciones y no hay valor seleccionado, usar la primera
        if (options.length > 0 && !value) {
          onChange(options[0].value as 'operativo' | 'gestion')
        }
      } catch (err) {
        console.error('Error cargando catálogo de audiencia:', err)
      } finally {
        setLoading(false)
      }
    }

    loadCatalog()
  }, [])

  // Fallback a valores hardcodeados si no hay catálogo
  const options = modeOptions.length > 0 
    ? modeOptions 
    : [
        { value: 'operativo', label: 'Operativo (pistero)', sort_order: 0 },
        { value: 'gestion', label: 'Gestión / Dueños', sort_order: 1 },
      ]

  const getDescription = (modeValue: string) => {
    if (modeValue === 'operativo') {
      return 'Documento corto y práctico para ejecución'
    }
    if (modeValue === 'gestion') {
      return 'Documento completo con controles y métricas'
    }
    return ''
  }

  return (
    <div>
      <label htmlFor="mode" className="block text-sm font-medium text-gray-700 mb-2">
        Audiencia *
      </label>
      {loading ? (
        <div className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-100 animate-pulse">
          Cargando opciones...
        </div>
      ) : (
        <select
          id="mode"
          name="mode"
          value={value}
          onChange={(e) => onChange(e.target.value as 'operativo' | 'gestion')}
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}
      <p className="mt-1 text-sm text-gray-500">
        {getDescription(value)}
      </p>
    </div>
  )
}
