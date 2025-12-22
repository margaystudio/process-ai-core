'use client'

import { useState, useEffect } from 'react'
import { getCatalogOptions, CatalogOption } from '@/lib/api'

interface OptionalFieldsProps {
  detailLevel: string
  contextText: string
  description: string
  onDetailLevelChange: (value: string) => void
  onContextTextChange: (value: string) => void
  onDescriptionChange: (value: string) => void
}

export default function OptionalFields({
  detailLevel,
  contextText,
  description,
  onDetailLevelChange,
  onContextTextChange,
  onDescriptionChange,
}: OptionalFieldsProps) {
  const [detailLevelOptions, setDetailLevelOptions] = useState<CatalogOption[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadCatalog() {
      try {
        const detailLevels = await getCatalogOptions('detail_level').catch(() => [])
        setDetailLevelOptions(detailLevels)
      } catch (err) {
        console.error('Error cargando catálogo:', err)
      } finally {
        setLoading(false)
      }
    }

    loadCatalog()
  }, [])

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium text-gray-900">Campos Opcionales</h3>
      <p className="text-sm text-gray-500">
        Estos campos ayudan a personalizar el documento. Si los dejás vacíos, se usarán los valores por defecto.
      </p>

      <div>
        <label htmlFor="detail_level" className="block text-sm font-medium text-gray-700 mb-2">
          Nivel de Detalle
        </label>
        {loading ? (
          <div className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-100 animate-pulse">
            Cargando opciones...
          </div>
        ) : detailLevelOptions.length > 0 ? (
          <select
            id="detail_level"
            name="detail_level"
            value={detailLevel}
            onChange={(e) => onDetailLevelChange(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Seleccionar...</option>
            {detailLevelOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ) : (
          <select
            id="detail_level"
            name="detail_level"
            value={detailLevel}
            onChange={(e) => onDetailLevelChange(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Seleccionar...</option>
            <option value="breve">Breve</option>
            <option value="estandar">Estándar</option>
            <option value="detallado">Detallado</option>
          </select>
        )}
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
          Descripción
        </label>
        <textarea
          id="description"
          name="description"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          rows={3}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
          placeholder="Descripción breve del proceso (opcional). Si no la completás, la IA la generará automáticamente."
        />
        <p className="mt-1 text-sm text-gray-500">
          Descripción breve del proceso. Si la dejás vacía, la IA la generará automáticamente basándose en el contenido.
        </p>
      </div>

      <div>
        <label htmlFor="context_text" className="block text-sm font-medium text-gray-700 mb-2">
          Contexto Adicional
        </label>
        <textarea
          id="context_text"
          name="context_text"
          value={contextText}
          onChange={(e) => onContextTextChange(e.target.value)}
          rows={4}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y"
          placeholder="Información adicional sobre el proceso, contexto del negocio, requisitos especiales, etc."
        />
        <p className="mt-1 text-sm text-gray-500">
          Este texto se incluirá en el prompt para ayudar a la IA a generar un documento más preciso.
        </p>
      </div>
    </div>
  )
}
