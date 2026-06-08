'use client'

import { useState, useEffect } from 'react'
import { Field } from '@/shared/ui/components'
import { getCatalogOptions, CatalogOption } from '@/lib/api'

interface OptionalFieldsProps {
  detailLevel: string
  contextText: string
  description: string
  onDetailLevelChange: (value: string) => void
  onContextTextChange: (value: string) => void
  onDescriptionChange: (value: string) => void
}

const selectClass =
  'h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'
const textareaClass =
  'w-full resize-y rounded-md border border-ink-300 bg-white px-3 py-2 text-body text-ink-800 placeholder:text-ink-500 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'

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
      <h3 className="text-h3 text-ink-900">Campos opcionales</h3>
      <p className="text-sm text-ink-500">
        Estos campos ayudan a personalizar el documento. Si los dejás vacíos, se usarán los valores por defecto.
      </p>

      <Field label="Nivel de detalle">
        {loading ? (
          <div className="h-10 w-full animate-pulse rounded-md border border-ink-200 bg-ink-100" />
        ) : detailLevelOptions.length > 0 ? (
          <select
            id="detail_level"
            name="detail_level"
            value={detailLevel}
            onChange={(e) => onDetailLevelChange(e.target.value)}
            className={selectClass}
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
            className={selectClass}
          >
            <option value="">Seleccionar...</option>
            <option value="breve">Breve</option>
            <option value="estandar">Estándar</option>
            <option value="detallado">Detallado</option>
          </select>
        )}
      </Field>

      <div>
        <Field label="Descripción">
          <textarea
            id="description"
            name="description"
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            rows={3}
            className={textareaClass}
            placeholder="Descripción breve del proceso (opcional). Si no la completás, la IA la generará automáticamente."
          />
        </Field>
        <p className="mt-1 text-sm text-ink-500">
          Descripción breve del proceso. Si la dejás vacía, la IA la generará automáticamente basándose en el contenido.
        </p>
      </div>

      <div>
        <Field label="Contexto adicional">
          <textarea
            id="context_text"
            name="context_text"
            value={contextText}
            onChange={(e) => onContextTextChange(e.target.value)}
            rows={4}
            className={textareaClass}
            placeholder="Información adicional sobre el proceso, contexto del negocio, requisitos especiales, etc."
          />
        </Field>
        <p className="mt-1 text-sm text-ink-500">
          Este texto se incluirá en el prompt para ayudar a la IA a generar un documento más preciso.
        </p>
      </div>
    </div>
  )
}
