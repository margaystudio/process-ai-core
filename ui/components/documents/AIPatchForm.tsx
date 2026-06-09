'use client'

import { useState } from 'react'
import { X } from 'lucide-react'

interface AIPatchFormProps {
  onPatch: (additionalObservations: string) => void
  onCancel: () => void
  processing: boolean
  defaultObservations?: string
}

export default function AIPatchForm({
  onPatch,
  onCancel,
  processing,
  defaultObservations = '',
}: AIPatchFormProps) {
  const [observations, setObservations] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onPatch(observations)
  }

  return (
    <div className="bg-white border-2 border-accent rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-h2 text-ink-900">Patch por IA</h3>
        <button
          onClick={onCancel}
          disabled={processing}
          className="text-ink-400 hover:text-ink-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <p className="text-sm text-ink-600 mb-4">
        Las observaciones del rechazo ya están incluidas. Puedes agregar observaciones adicionales
        si es necesario.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label
            htmlFor="observations"
            className="block text-sm font-medium text-ink-700 mb-2"
          >
            Observaciones adicionales (opcional)
          </label>
          <textarea
            id="observations"
            value={observations}
            onChange={(e) => setObservations(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
            placeholder="Ej: También corregir la numeración de los pasos..."
            disabled={processing}
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={processing}
            className="px-4 py-2 text-sm text-ink-700 bg-ink-100 rounded-md hover:bg-ink-200 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={processing}
            className="px-4 py-2 text-sm bg-action text-white rounded-md hover:bg-action-hover disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {processing ? 'Procesando con IA...' : 'Aplicar Patch por IA'}
          </button>
        </div>
      </form>
    </div>
  )
}



