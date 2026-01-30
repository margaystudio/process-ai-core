'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createRecipeRun, getArtifactUrl } from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'

export default function NewRecipePage() {
  const router = useRouter()
  const { withLoading } = useLoading()
  const [recipeName, setRecipeName] = useState('')
  const [mode, setMode] = useState<'simple' | 'detallado'>('simple')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // Validar que sea un archivo de audio
      const validExtensions = ['.mp3', '.m4a', '.wav', '.aac', '.ogg', '.opus']
      const extension = '.' + file.name.split('.').pop()?.toLowerCase()
      
      if (!validExtensions.includes(extension)) {
        setError(`Formato no válido. Use: ${validExtensions.join(', ')}`)
        return
      }
      
      setAudioFile(file)
      setError(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    
    if (!recipeName.trim()) {
      setError('El nombre de la receta es requerido')
      return
    }
    
    if (!audioFile) {
      setError('Debe seleccionar un archivo de audio')
      return
    }

    await withLoading(async () => {
      try {
        setIsSubmitting(true)
        setError(null)
        setResult(null)

        // Crear FormData
        const formData = new FormData()
        formData.append('recipe_name', recipeName.trim())
        formData.append('mode', mode)
        formData.append('audio_files', audioFile)

        // Llamar a la API
        const response = await createRecipeRun(formData)
        
        setResult(response)
        
        // Redirigir a la página de resultados
        if (response.run_id) {
          router.push(`/recipes/${response.run_id}`)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al crear la receta')
      } finally {
        setIsSubmitting(false)
      }
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white shadow rounded-lg p-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">🍳 Crear Nueva Receta</h1>
          
          {error && (
            <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
              <span className="block sm:inline">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Nombre de la receta */}
            <div>
              <label htmlFor="recipeName" className="block text-sm font-medium text-gray-700 mb-1">
                Nombre de la Receta *
              </label>
              <input
                type="text"
                id="recipeName"
                value={recipeName}
                onChange={(e) => setRecipeName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ej: Pasta Carbonara"
                required
              />
            </div>

            {/* Modo */}
            <div>
              <label htmlFor="mode" className="block text-sm font-medium text-gray-700 mb-1">
                Modo
              </label>
              <select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as 'simple' | 'detallado')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="simple">Simple</option>
                <option value="detallado">Detallado</option>
              </select>
            </div>

            {/* Archivo de audio */}
            <div>
              <label htmlFor="audioFile" className="block text-sm font-medium text-gray-700 mb-1">
                Archivo de Audio *
              </label>
              <input
                type="file"
                id="audioFile"
                accept=".mp3,.m4a,.wav,.aac,.ogg,.opus,audio/*"
                onChange={handleFileChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                required
              />
              {audioFile && (
                <p className="mt-2 text-sm text-gray-600">
                  Archivo seleccionado: <strong>{audioFile.name}</strong> ({(audioFile.size / 1024 / 1024).toFixed(2)} MB)
                </p>
              )}
              <p className="mt-1 text-xs text-gray-500">
                Formatos soportados: MP3, M4A, WAV, AAC, OGG, OPUS (incluye audios de WhatsApp)
              </p>
            </div>

            {/* Botón de envío */}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={isSubmitting}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-6 rounded-md"
              >
                {isSubmitting ? 'Procesando...' : 'Crear Receta'}
              </button>
            </div>
          </form>

          {result && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
              <p className="text-sm text-green-800">
                ✅ Receta creada exitosamente! Run ID: {result.run_id}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
