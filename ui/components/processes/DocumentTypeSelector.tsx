'use client'

import { useEffect, useState } from 'react'
import { Field } from '@/shared/ui/components'
import { getDocumentTypes } from '@/lib/api'

const selectClass =
  'h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'

// Fallback si el endpoint aún no está disponible (en dev sin backend).
const FALLBACK: { value: string; label: string }[] = [
  { value: 'procedimiento', label: 'Procedimiento' },
  { value: 'instructivo', label: 'Instructivo' },
  { value: 'manual_interno', label: 'Manual interno' },
  { value: 'manual_externo', label: 'Manual externo' },
  { value: 'politica', label: 'Política' },
  { value: 'normativa', label: 'Normativa' },
  { value: 'formulario', label: 'Formulario' },
  { value: 'checklist', label: 'Checklist' },
  { value: 'tramite', label: 'Trámite' },
  { value: 'faq_validada', label: 'FAQ validada' },
  { value: 'presupuesto', label: 'Presupuesto' },
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
  const [options, setOptions] = useState<{ value: string; label: string }[]>([])

  useEffect(() => {
    getDocumentTypes(false)
      .then((types) => {
        if (types.length === 0) {
          setOptions(FALLBACK)
          return
        }
        setOptions(
          types.map((t) => ({ value: t.key, label: t.label }))
        )
      })
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
