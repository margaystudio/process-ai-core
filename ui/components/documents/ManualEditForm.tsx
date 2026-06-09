'use client'

import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
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
      <div className="bg-white border-2 border-accent rounded-lg p-6">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-2"></div>
          <p className="text-sm text-ink-600">Cargando contenido...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white border-2 border-danger-bd rounded-lg p-6">
        <div className="bg-danger-bg border border-danger-bd rounded-md p-4">
          <p className="text-danger">Error: {error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border-2 border-accent rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-h2 text-ink-900">Edición Manual</h3>
        <button
          onClick={onCancel}
          disabled={processing}
          className="text-ink-400 hover:text-ink-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label
            htmlFor="json-content"
            className="block text-sm font-medium text-ink-700 mb-2"
          >
            Editor JSON
          </label>
          <textarea
            id="json-content"
            value={jsonContent}
            onChange={(e) => setJsonContent(e.target.value)}
            rows={20}
            className="w-full px-3 py-2 border border-ink-300 rounded-md font-mono text-sm focus:ring-2 focus:ring-action-ring focus:border-accent"
            disabled={processing}
          />
          <p className="text-xs text-ink-500 mt-1">
            Requiere conocimiento técnico. El JSON será validado antes de guardar.
          </p>
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
            {processing ? 'Guardando...' : 'Guardar Cambios'}
          </button>
        </div>
      </form>
    </div>
  )
}



