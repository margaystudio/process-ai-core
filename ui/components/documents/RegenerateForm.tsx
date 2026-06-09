'use client'

import { useState } from 'react'
import { X } from 'lucide-react'

interface RegenerateFormProps {
  documentId: string
  onRegenerate: (formData: FormData) => void
  onCancel: () => void
  processing: boolean
}

export default function RegenerateForm({
  documentId,
  onRegenerate,
  onCancel,
  processing,
}: RegenerateFormProps) {
  const [revisionNotes, setRevisionNotes] = useState('')
  const [audioFiles, setAudioFiles] = useState<File[]>([])
  const [videoFiles, setVideoFiles] = useState<File[]>([])
  const [imageFiles, setImageFiles] = useState<File[]>([])
  const [textFiles, setTextFiles] = useState<File[]>([])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const formData = new FormData()
    formData.append('revision_notes', revisionNotes)

    audioFiles.forEach((file) => {
      formData.append('audio_files', file)
    })
    videoFiles.forEach((file) => {
      formData.append('video_files', file)
    })
    imageFiles.forEach((file) => {
      formData.append('image_files', file)
    })
    textFiles.forEach((file) => {
      formData.append('text_files', file)
    })

    onRegenerate(formData)
  }

  const handleFileChange = (
    e: React.ChangeEvent<HTMLInputElement>,
    setter: (files: File[]) => void
  ) => {
    if (e.target.files) {
      setter(Array.from(e.target.files))
    }
  }

  return (
    <div className="bg-white border-2 border-accent rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-h2 text-ink-900">Regenerar Documento</h3>
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
            htmlFor="revision-notes"
            className="block text-sm font-medium text-ink-700 mb-2"
          >
            Notas de revisión (instrucciones para la IA)
          </label>
          <textarea
            id="revision-notes"
            value={revisionNotes}
            onChange={(e) => setRevisionNotes(e.target.value)}
            rows={4}
            className="w-full px-3 py-2 border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
            placeholder="Ej: Corregir los pasos 3 y 5 según las observaciones..."
            disabled={processing}
          />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-ink-700 mb-2">
            Archivos (opcional - si no subes archivos, se reutilizarán los anteriores)
          </label>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-ink-600 mb-1">Audio</label>
              <input
                type="file"
                multiple
                accept="audio/*"
                onChange={(e) => handleFileChange(e, setAudioFiles)}
                disabled={processing}
                className="w-full text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-ink-600 mb-1">Video</label>
              <input
                type="file"
                multiple
                accept="video/*"
                onChange={(e) => handleFileChange(e, setVideoFiles)}
                disabled={processing}
                className="w-full text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-ink-600 mb-1">Imágenes</label>
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => handleFileChange(e, setImageFiles)}
                disabled={processing}
                className="w-full text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-ink-600 mb-1">Texto</label>
              <input
                type="file"
                multiple
                accept=".txt,.md,.pdf,.docx"
                onChange={(e) => handleFileChange(e, setTextFiles)}
                disabled={processing}
                className="w-full text-sm"
              />
            </div>
          </div>
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
            {processing ? 'Regenerando...' : 'Regenerar Documento'}
          </button>
        </div>
      </form>
    </div>
  )
}



