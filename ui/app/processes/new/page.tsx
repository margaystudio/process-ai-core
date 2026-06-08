'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, FileText } from 'lucide-react'
import { Card, CardBody, Button, buttonVariants } from '@/shared/ui/components'
import { createProcessRun } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useLoading } from '@/contexts/LoadingContext'
import ProcessNameInput from '@/components/processes/ProcessNameInput'
import ModeSelector from '@/components/processes/ModeSelector'
import OptionalFields from '@/components/processes/OptionalFields'
import FolderTree from '@/components/processes/FolderTree'
import FileUploadModal, { FileType } from '@/components/processes/FileUploadModal'
import FileList from '@/components/processes/FileList'
import { usePdfViewer } from '@/hooks/usePdfViewer'
import { FileItemData } from '@/components/processes/FileItem'

export default function NewProcessPage() {
  const router = useRouter()
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const { withLoading } = useLoading()
  const [processName, setProcessName] = useState('')
  const [mode, setMode] = useState<'operativo' | 'gestion'>('operativo')
  const [folderId, setFolderId] = useState('')
  const [detailLevel, setDetailLevel] = useState('')
  const [contextText, setContextText] = useState('')
  const [description, setDescription] = useState('')

  const [files, setFiles] = useState<FileItemData[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)

  // Hook para manejar visualización de artifacts
  const { openArtifactFromRun, ModalComponent } = usePdfViewer()

  const handleAddFile = (file: File, type: FileType, description: string) => {
    const newFile: FileItemData = {
      id: `${Date.now()}-${Math.random()}`,
      file,
      type,
      description,
    }
    setFiles([...files, newFile])
  }

  const handleRemoveFile = (id: string) => {
    setFiles(files.filter(f => f.id !== id))
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()

    await withLoading(async () => {
      setIsSubmitting(true)
      setError(null)
      setResult(null)

      try {
        const formData = new FormData()

        // Campos requeridos
        formData.append('process_name', processName)
        formData.append('mode', mode)

        // Campos requeridos
        if (!folderId) {
          throw new Error('Debes seleccionar una carpeta')
        }
        formData.append('folder_id', folderId)

        // Campos opcionales (solo si tienen valor)
        if (detailLevel) formData.append('detail_level', detailLevel)
        if (contextText.trim()) formData.append('context_text', contextText.trim())
        if (description.trim()) formData.append('description', description.trim())

        // Agregar archivos según su tipo
        files.forEach((fileItem) => {
          const fieldName = `${fileItem.type}_files`
          formData.append(fieldName, fileItem.file)
        })

        const response = await createProcessRun(formData)
        setResult(response)

        // Si se creó un documento, redirigir a su página de detalles
        if (response.document_id) {
          // Pequeño delay para que el usuario vea el mensaje de éxito
          setTimeout(() => {
            router.push(`/documents/${response.document_id}`)
          }, 1500)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        setIsSubmitting(false)
      }
    })
  }

  return (
    <div className="p-8">
      <div className="mx-auto max-w-6xl">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Columna izquierda: Árbol de carpetas */}
          <div className="lg:col-span-1">
            {!selectedWorkspaceId ? (
              <Card>
                <CardBody>
                  <p className="text-sm text-ink-600">
                    Seleccioná un espacio de trabajo en el encabezado para continuar.
                  </p>
                </CardBody>
              </Card>
            ) : (
              <>
                <div className="mb-2">
                  <label className="mb-2 block text-sm font-semibold text-ink-700">
                    Carpeta <span className="text-danger">*</span>
                  </label>
                  {!folderId && (
                    <p className="mb-2 text-xs text-danger">Debés seleccionar una carpeta para continuar</p>
                  )}
                </div>
                <Card>
                  <CardBody className="p-4">
                    <FolderTree
                      workspaceId={selectedWorkspaceId}
                      selectedFolderId={folderId}
                      onSelectFolder={(id) => setFolderId(id || '')}
                      showSelectable={true}
                      showCrud={true}
                      showDocuments={false}
                    />
                  </CardBody>
                </Card>
              </>
            )}
          </div>

          {/* Columna derecha: Formulario */}
          <div className="lg:col-span-2">
            <Card>
              <CardBody className="p-8">
                <h1 className="mb-6 text-h1 text-ink-900">Nuevo proceso</h1>

                {!selectedWorkspaceId ? (
                  <div className="rounded-md border border-warning-bd bg-warning-bg p-4">
                    <p className="text-sm text-ink-700">
                      Seleccioná un espacio de trabajo en el encabezado para crear un proceso.
                    </p>
                  </div>
                ) : (
                  <div className="mb-4 rounded-md border border-info-bd bg-info-bg p-4">
                    <p className="text-sm font-semibold text-ink-700">Espacio de trabajo</p>
                    <p className="text-sm text-ink-600">{selectedWorkspace?.name}</p>
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                  <ProcessNameInput
                    value={processName}
                    onChange={setProcessName}
                  />

                  <ModeSelector
                    value={mode}
                    onChange={setMode}
                  />

                  <OptionalFields
                    detailLevel={detailLevel}
                    contextText={contextText}
                    description={description}
                    onDetailLevelChange={setDetailLevel}
                    onContextTextChange={setContextText}
                    onDescriptionChange={setDescription}
                  />

                  <div className="border-t border-ink-200 pt-6">
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-h3 text-ink-900">Archivos</h3>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => setIsModalOpen(true)}
                      >
                        <Plus />
                        Agregar archivo
                      </Button>
                    </div>

                    <FileList files={files} onRemove={handleRemoveFile} />
                  </div>

                  <div className="border-t border-ink-200 pt-6">
                    <div className="flex gap-4">
                      <Button
                        type="submit"
                        variant="create"
                        size="lg"
                        disabled={isSubmitting || !processName.trim() || files.length === 0 || !selectedWorkspaceId || !folderId}
                      >
                        {isSubmitting ? 'Procesando...' : 'Generar documento'}
                      </Button>

                      <a href="/" className={buttonVariants({ variant: 'secondary', size: 'lg' })}>
                        Cancelar
                      </a>
                    </div>
                  </div>
                </form>

                {error && (
                  <div className="mt-6 rounded-md border border-danger-bd bg-danger-bg p-4 text-danger">
                    <p className="font-semibold">Error</p>
                    <p className="mt-1 text-sm">{error}</p>
                  </div>
                )}

                {result && (
                  <div className="mt-6 rounded-md border border-success-bd bg-success-bg p-4">
                    <p className="font-semibold text-success-fg">¡Documento generado exitosamente!</p>
                    <p className="mt-2 text-sm text-ink-700">Run ID: {result.run_id}</p>
                    {result.artifacts && (
                      <div className="mt-4 flex flex-col items-start gap-1">
                        {result.artifacts.json && (
                          <Button variant="ghost" size="sm" onClick={() => openArtifactFromRun(result.artifacts.json!, 'json')}>
                            <FileText />
                            Ver JSON
                          </Button>
                        )}
                        {result.artifacts.markdown && (
                          <Button variant="ghost" size="sm" onClick={() => openArtifactFromRun(result.artifacts.markdown!, 'markdown')}>
                            <FileText />
                            Ver Markdown
                          </Button>
                        )}
                        {result.artifacts.pdf && (
                          <Button variant="ghost" size="sm" onClick={() => openArtifactFromRun(result.artifacts.pdf!, 'pdf')}>
                            <FileText />
                            Ver PDF
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      </div>

      <FileUploadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onAdd={handleAddFile}
      />

      <ModalComponent />
    </div>
  )
}
