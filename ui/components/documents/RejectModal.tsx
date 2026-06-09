'use client'

import { useState } from 'react'
import { X } from 'lucide-react'
import { Document } from '@/lib/api'

interface RejectModalProps {
  document: Document
  isOpen: boolean
  onClose: () => void
  onReject: (observations: string) => void
  processing?: boolean
}

export default function RejectModal({
  document,
  isOpen,
  onClose,
  onReject,
  processing = false,
}: RejectModalProps) {
  const [observations, setObservations] = useState('')

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (observations.trim()) {
      onReject(observations)
      setObservations('') // Reset después de enviar
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-h2 text-ink-900">
              Rechazar Documento
            </h2>
            <button
              onClick={onClose}
              disabled={processing}
              className="text-ink-400 hover:text-ink-600"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-4">
            <p className="text-sm text-ink-600 mb-2">
              Documento: <span className="font-medium">{document.name}</span>
            </p>
            <p className="text-sm text-ink-500">
              Por favor, proporciona observaciones detalladas sobre por qué se rechaza este documento.
              Estas observaciones serán visibles para el creador.
            </p>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label
                htmlFor="observations"
                className="block text-sm font-medium text-ink-700 mb-2"
              >
                Observaciones <span className="text-danger">*</span>
              </label>
              <textarea
                id="observations"
                value={observations}
                onChange={(e) => setObservations(e.target.value)}
                required
                rows={6}
                className="w-full px-3 py-2 border border-ink-300 rounded-md focus:ring-2 focus:ring-danger focus:border-danger"
                placeholder="Ej: El documento tiene errores gramaticales en los pasos 3 y 5. Además, falta información sobre los indicadores de éxito..."
                disabled={processing}
              />
            </div>

            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                disabled={processing}
                className="px-4 py-2 text-sm text-ink-700 bg-ink-100 rounded-md hover:bg-ink-200 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={processing || !observations.trim()}
                className="px-4 py-2 text-sm bg-danger text-white rounded-md hover:bg-danger disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {processing ? 'Enviando...' : 'Enviar a Revisión'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}



