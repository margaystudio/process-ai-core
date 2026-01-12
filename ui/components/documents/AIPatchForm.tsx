'use client'

import { useState } from 'react'

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
    <div className="bg-white border-2 border-blue-400 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold text-gray-900">🤖 Patch por IA</h3>
        <button
          onClick={onCancel}
          disabled={processing}
          className="text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      </div>

      <p className="text-sm text-gray-600 mb-4">
        Las observaciones del rechazo ya están incluidas. Puedes agregar observaciones adicionales
        si es necesario.
      </p>

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label
            htmlFor="observations"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Observaciones adicionales (opcional)
          </label>
          <textarea
            id="observations"
            value={observations}
            onChange={(e) => setObservations(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Ej: También corregir la numeración de los pasos..."
            disabled={processing}
          />
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={processing}
            className="px-4 py-2 text-sm text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={processing}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {processing ? 'Procesando con IA...' : 'Aplicar Patch por IA'}
          </button>
        </div>
      </form>
    </div>
  )
}



