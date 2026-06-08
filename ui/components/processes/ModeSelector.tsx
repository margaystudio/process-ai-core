'use client'

import { useState, useEffect } from 'react'
import { OptionSet } from '@/shared/ui/components'
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
      <label className="mb-2 block text-sm font-semibold text-ink-700">Audiencia *</label>
      {loading ? (
        <div className="h-[52px] w-full animate-pulse rounded-md border border-ink-200 bg-ink-100" />
      ) : (
        <OptionSet
          options={options.map((opt) => ({ value: opt.value, label: opt.label }))}
          value={value}
          onChange={(v) => onChange(v as 'operativo' | 'gestion')}
        />
      )}
      <p className="mt-1.5 text-sm text-ink-500">{getDescription(value)}</p>
    </div>
  )
}
