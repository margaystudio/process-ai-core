'use client'

import { useState, useEffect } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useRouter, useParams } from 'next/navigation'
import {
  getDocument,
  listValidations,
  patchDocumentWithAI,
  createDocumentRun,
  Document,
  Validation,
} from '@/lib/api'
import { useUserId } from '@/hooks/useUserId'
import CorrectionOptionCard from '@/components/documents/CorrectionOptionCard'
import AIPatchForm from '@/components/documents/AIPatchForm'
import ManualEditPanel from '@/components/documents/ManualEditPanel'
import RegenerateForm from '@/components/documents/RegenerateForm'
import DocumentPreview from '@/components/documents/DocumentPreview'
import { formatDate } from '@/utils/dateFormat'

type CorrectionOption = 'ai-patch' | 'manual-edit' | 'regenerate' | null

export default function CorrectDocumentPage() {
  const router = useRouter()
  const params = useParams()
  const documentId = params.id as string
  const userId = useUserId()

  const [document, setDocument] = useState<Document | null>(null)
  const [validations, setValidations] = useState<Validation[]>([])
  const [selectedOption, setSelectedOption] = useState<CorrectionOption>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        setError(null)

        const [doc, validationsData] = await Promise.all([
          getDocument(documentId),
          listValidations(documentId),
        ])

        setDocument(doc)
        // Obtener la última validación rechazada
        const rejectedValidations = validationsData.filter((v) => v.status === 'rejected')
        setValidations(rejectedValidations)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        setLoading(false)
      }
    }

    if (documentId) {
      loadData()
    }
  }, [documentId])

  const handleAIPatch = async (additionalObservations: string) => {
    if (!document) return

    setProcessing(true)
    try {
      const lastValidation = validations[0]
      const allObservations = lastValidation
        ? `${lastValidation.observations}\n\n${additionalObservations}`
        : additionalObservations

      await patchDocumentWithAI(document.id, allObservations)
      router.push(`/documents/${document.id}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Error al aplicar patch por IA')
    } finally {
      setProcessing(false)
    }
  }


  const handleRegenerate = async (formData: FormData) => {
    if (!document) return

    setProcessing(true)
    try {
      await createDocumentRun(document.id, formData)
      router.push(`/documents/${document.id}`)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Error al regenerar documento')
    } finally {
      setProcessing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-accent mx-auto mb-4"></div>
          <p className="text-ink-600">Cargando documento...</p>
        </div>
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-danger-bg border border-danger-bd rounded-lg p-6">
            <p className="text-danger">Error: {error || 'Documento no encontrado'}</p>
            <button
              onClick={() => router.back()}
              className="mt-4 px-4 py-2 bg-danger text-white rounded-md hover:bg-danger"
            >
              Volver
            </button>
          </div>
        </div>
      </div>
    )
  }

  const lastRejection = validations[0]

  return (
    <div className="p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="text-accent hover:text-accent-ink mb-4"
          >
            <ArrowLeft className="h-4 w-4" /> Volver
          </button>
          <h1 className="text-h1 text-ink-900">Corregir Documento</h1>
          <p className="text-ink-600 mt-1">{document.name}</p>
        </div>

        {/* Observaciones del Rechazo */}
        {lastRejection && (
          <div className="bg-danger-bg border border-danger-bd rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-danger mb-2">
              Observaciones del Rechazo
            </h2>
            <p className="text-danger whitespace-pre-wrap">{lastRejection.observations}</p>
            {lastRejection.validator_user_id && (
              <p className="text-sm text-danger mt-2">
                Rechazado por usuario: {lastRejection.validator_user_id}
              </p>
            )}
            {lastRejection.completed_at && (
              <p className="text-sm text-danger">
                Fecha: {formatDate(lastRejection.completed_at)}
              </p>
            )}
          </div>
        )}

        {/* Layout: 2 columnas */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Columna principal: Opciones y formularios */}
          <div className="lg:col-span-2">
            {/* Cards de Opciones */}
            {!selectedOption && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <CorrectionOptionCard
                  title="Patch por IA"
                  description="Correcciones automáticas usando IA"
                  idealFor={[
                    'Errores gramaticales',
                    'Ajustes de estilo',
                    'Correcciones menores',
                  ]}
                  note="Rápido y automático"
                  onClick={() => setSelectedOption('ai-patch')}
                />

                <CorrectionOptionCard
                  title="Edición Manual"
                  description="Editor visual tipo Word: texto, listas, imágenes y tablas"
                  idealFor={[
                    'Cambios de redacción',
                    'Agregar o quitar secciones',
                    'Insertar imágenes y enlaces',
                  ]}
                  note="Guardado como borrador y envío a validación"
                  onClick={() => setSelectedOption('manual-edit')}
                />

                <CorrectionOptionCard
                  title="Regenerar Documento"
                  description="Crea una nueva versión con nuevos archivos multimedia"
                  idealFor={[
                    'Nuevos archivos disponibles',
                    'Cambios en el proceso',
                    'Regeneración completa',
                  ]}
                  note="Sube nuevos archivos"
                  onClick={() => setSelectedOption('regenerate')}
                />
              </div>
            )}

            {/* Formularios Expandidos */}
            {selectedOption === 'ai-patch' && (
              <AIPatchForm
                onPatch={handleAIPatch}
                onCancel={() => setSelectedOption(null)}
                processing={processing}
                defaultObservations={lastRejection?.observations || ''}
              />
            )}

            {selectedOption === 'manual-edit' && (
              <ManualEditPanel
                documentId={document.id}
                workspaceId={document.workspace_id}
                userId={userId}
                onCancel={() => setSelectedOption(null)}
                onSubmitForReview={() => router.push(`/documents/${document.id}`)}
              />
            )}

            {selectedOption === 'regenerate' && (
              <RegenerateForm
                documentId={document.id}
                onRegenerate={handleRegenerate}
                onCancel={() => setSelectedOption(null)}
                processing={processing}
              />
            )}
          </div>

          {/* Sidebar: Preview del Documento */}
          <div className="lg:col-span-1">
            <DocumentPreview documentId={document.id} />
          </div>
        </div>
      </div>
    </div>
  )
}

