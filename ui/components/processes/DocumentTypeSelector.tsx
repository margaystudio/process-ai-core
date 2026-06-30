'use client'

import { useEffect, useState } from 'react'
import { Field } from '@/shared/ui/components'
import { getCatalogOptions, CatalogOption } from '@/lib/api'

const selectClass =
  'h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'

// Fallback si el catálogo aún no está seedeado (domain "document_type").
const FALLBACK: CatalogOption[] = [
  { value: 'procedimiento', label: 'Procedimiento', sort_order: 10 },
  { value: 'instructivo', label: 'Instructivo', sort_order: 20 },
  { value: 'manual_interno', label: 'Manual interno', sort_order: 30 },
  { value: 'manual_externo', label: 'Manual externo', sort_order: 40 },
  { value: 'politica', label: 'Política', sort_order: 50 },
  { value: 'normativa', label: 'Normativa', sort_order: 60 },
  { value: 'formulario', label: 'Formulario', sort_order: 70 },
  { value: 'checklist', label: 'Checklist', sort_order: 80 },
  { value: 'tramite', label: 'Trámite', sort_order: 90 },
  { value: 'faq_validada', label: 'FAQ validada', sort_order: 100 },
  { value: 'presupuesto', label: 'Presupuesto', sort_order: 110 },
]

interface DocumentTypeSelectorProps {
  value: string
  onChange: (value: string) => void
  label?: string
}

export default function DocumentTypeSelector({
  value,
  onChange,
  label = 'Tipo de documento',
}: DocumentTypeSelectorProps) {
  const [options, setOptions] = useState<CatalogOption[]>([])

  useEffect(() => {
    getCatalogOptions('document_type')
      .then((opts) => setOptions(opts.length > 0 ? opts : FALLBACK))
      .catch(() => setOptions(FALLBACK))
  }, [])

  const list = options.length > 0 ? options : FALLBACK

  return (
    <Field label={label}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={selectClass}
      >
        {list.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </Field>
  )
}
