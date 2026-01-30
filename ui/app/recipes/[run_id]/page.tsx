'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { getRun, getArtifactUrl } from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import ArtifactViewerModal from '@/components/processes/ArtifactViewerModal'

export default function RecipeResultPage() {
  const params = useParams()
  const runId = params.run_id as string
  const { withLoading } = useLoading()
  
  const [run, setRun] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [viewerModal, setViewerModal] = useState<{
    isOpen: boolean
    filename: string
    type: 'json' | 'markdown' | 'pdf'
  }>({
    isOpen: false,
    filename: '',
    type: 'pdf',
  })

  useEffect(() => {
    if (runId) {
      loadRun()
    }
  }, [runId])

  const loadRun = async () => {
    await withLoading(async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await getRun(runId, 'recipe')
        setRun(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al cargar la receta')
      } finally {
        setLoading(false)
      }
    })
  }

  const openArtifact = (filename: string, type: 'json' | 'markdown' | 'pdf') => {
    setViewerModal({
      isOpen: true,
      filename,
      type,
    })
  }

  const closeModal = () => {
    setViewerModal({ ...viewerModal, isOpen: false })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Cargando receta...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={loadRun}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md"
          >
            Reintentar
          </button>
        </div>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Receta no encontrada</p>
        </div>
      </div>
    )
  }

  const artifacts = run.artifacts || {}

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white shadow rounded-lg p-6">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              🍳 {run.recipe_name || 'Receta'}
            </h1>
            <p className="text-sm text-gray-500">
              Run ID: <code className="bg-gray-100 px-2 py-1 rounded">{runId}</code>
            </p>
            <p className="text-sm text-gray-500">
              Status: <span className={`font-medium ${run.status === 'completed' ? 'text-green-600' : 'text-yellow-600'}`}>
                {run.status}
              </span>
            </p>
          </div>

          {run.error && (
            <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
              <span className="block sm:inline">Error: {run.error}</span>
            </div>
          )}

          {/* Artefactos */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-900">Artefactos Generados</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* PDF */}
              {artifacts.pdf && (
                <div className="space-y-2">
                  <button
                    onClick={() => openArtifact('recipe.pdf', 'pdf')}
                    className="w-full p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="text-3xl">📄</div>
                      <div>
                        <p className="font-medium text-gray-900">PDF</p>
                        <p className="text-sm text-gray-500">Ver PDF</p>
                      </div>
                    </div>
                  </button>
                  <a
                    href={`${getArtifactUrl(runId, 'recipe.pdf')}?download=true`}
                    download
                    className="block w-full text-center text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    Descargar PDF
                  </a>
                </div>
              )}

              {/* Markdown */}
              {artifacts.markdown && (
                <button
                  onClick={() => openArtifact('recipe.md', 'markdown')}
                  className="p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left"
                >
                  <div className="flex items-center space-x-3">
                    <div className="text-3xl">📝</div>
                    <div>
                      <p className="font-medium text-gray-900">Markdown</p>
                      <p className="text-sm text-gray-500">Ver Markdown</p>
                    </div>
                  </div>
                </button>
              )}

              {/* JSON */}
              {artifacts.json && (
                <button
                  onClick={() => openArtifact('recipe.json', 'json')}
                  className="p-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left"
                >
                  <div className="flex items-center space-x-3">
                    <div className="text-3xl">📋</div>
                    <div>
                      <p className="font-medium text-gray-900">JSON</p>
                      <p className="text-sm text-gray-500">Ver JSON</p>
                    </div>
                  </div>
                </button>
              )}
            </div>

            {!artifacts.pdf && !artifacts.markdown && !artifacts.json && (
              <p className="text-gray-500 text-center py-8">
                No hay artefactos disponibles aún. El procesamiento puede estar en curso.
              </p>
            )}
          </div>

          {/* Botón para crear otra receta */}
          <div className="mt-8 pt-6 border-t border-gray-200">
            <a
              href="/recipes/new"
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md"
            >
              Crear Otra Receta
            </a>
          </div>
        </div>
      </div>

      {/* Modal para ver artefactos */}
      <ArtifactViewerModal
        isOpen={viewerModal.isOpen}
        onClose={closeModal}
        runId={runId}
        filename={viewerModal.filename}
        type={viewerModal.type}
      />
    </div>
  )
}
