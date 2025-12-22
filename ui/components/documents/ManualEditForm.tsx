'use client'

import { useState, useEffect } from 'react'
import { getCurrentDocumentVersion } from '@/lib/api'

interface ManualEditFormProps {
  documentId: string
  onSave: (contentJson: string) => void
  onCancel: () => void
  processing: boolean
}

export default function ManualEditForm({
  documentId,
  onSave,
  onCancel,
  processing,
}: ManualEditFormProps) {
  const [jsonContent, setJsonContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadContent() {
      try {
        setLoading(true)
        setError(null)
        const version = await getCurrentDocumentVersion(documentId)
        setJsonContent(version.content_json)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando contenido')
      } finally {
        setLoading(false)
      }
    }

    loadContent()
  }, [documentId])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    try {
      // Validar JSON
      JSON.parse(jsonContent)
      onSave(jsonContent)
    } catch (err) {
      alert('El JSON no es válido. Por favor, corrige los errores antes de guardar.')
    }
  }

  if (loading) {
    return (
      <div className="bg-white border-2 border-blue-400 rounded-lg p-6">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Cargando contenido...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white border-2 border-red-400 rounded-lg p-6">
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <p className="text-red-800">Error: {error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border-2 border-blue-400 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold text-gray-900">✏️ Edición Manual</h3>
        <button
          onClick={onCancel}
          disabled={processing}
          className="text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label
            htmlFor="json-content"
            className="block text-sm font-medium text-gray-700 mb-2"
          >
            Editor JSON
          </label>
          <textarea
            id="json-content"
            value={jsonContent}
            onChange={(e) => setJsonContent(e.target.value)}
            rows={20}
            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            disabled={processing}
          />
          <p className="text-xs text-gray-500 mt-1">
            ⚠️ Requiere conocimiento técnico. El JSON será validado antes de guardar.
          </p>
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
            {processing ? 'Guardando...' : 'Guardar Cambios'}
          </button>
        </div>
      </form>
    </div>
  )
}

