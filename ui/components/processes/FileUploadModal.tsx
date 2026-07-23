'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { Music, FileText, Image as ImageIcon, Paperclip, X } from 'lucide-react'
import { Button } from '@/shared/ui/components'
import { cn } from '@/shared/ui/cn'
import {
  EXTENSIONS_BY_TYPE,
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  getFileExtension,
  fileMatchesType,
  type FileType,
} from '@/lib/fileUploadValidation'

export type { FileType } from '@/lib/fileUploadValidation'

const TYPE_OPTIONS: { value: FileType; label: string; extensions: readonly string[] }[] = [
  { value: 'audio', label: 'Audio', extensions: EXTENSIONS_BY_TYPE.audio },
  { value: 'text', label: 'Documento', extensions: EXTENSIONS_BY_TYPE.text },
  { value: 'image', label: 'Imagen', extensions: EXTENSIONS_BY_TYPE.image },
  { value: 'video', label: 'Otro', extensions: EXTENSIONS_BY_TYPE.video },
]

const selectClass =
  'h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'
const inputClass =
  'h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800 placeholder:text-ink-500 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'

function formatRecordingTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

/** Negocia el mime de grabación una sola vez y devuelve mime + extensión derivada. */
function getPreferredAudioMimeType(): { mime: string; ext: string } {
  if (typeof window === 'undefined') return { mime: 'audio/webm', ext: '.webm' }
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
  ]
  const mime = candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? 'audio/webm'
  const ext = mime.startsWith('audio/ogg') ? '.ogg' : '.webm'
  return { mime, ext }
}

function getAcceptForType(fileType: FileType): string {
  const opt = TYPE_OPTIONS.find((o) => o.value === fileType)
  return opt ? opt.extensions.join(',') : ''
}

function getExtensionsLabel(fileType: FileType): string {
  const opt = TYPE_OPTIONS.find((o) => o.value === fileType)
  return opt ? opt.extensions.join(', ') : ''
}

function getTypeCategoryForIcon(fileType: FileType): 'audio' | 'document' | 'image' | 'other' {
  switch (fileType) {
    case 'audio':
      return 'audio'
    case 'text':
      return 'document'
    case 'image':
      return 'image'
    default:
      return 'other'
  }
}

function CategoryIcon({ category, className }: { category: 'audio' | 'document' | 'image' | 'other'; className?: string }) {
  if (category === 'audio') return <Music className={className} />
  if (category === 'document') return <FileText className={className} />
  if (category === 'image') return <ImageIcon className={className} />
  return <Paperclip className={className} />
}

interface FileUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (file: File, type: FileType, description: string) => void
}

export default function FileUploadModal({ isOpen, onClose, onAdd }: FileUploadModalProps) {
  const [type, setType] = useState<FileType>('audio')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [touchedDropzone, setTouchedDropzone] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Grabación de audio
  const [audioSource, setAudioSource] = useState<'file' | 'record'>('file')
  const [isRecording, setIsRecording] = useState(false)
  const [recordingElapsedSeconds, setRecordingElapsedSeconds] = useState(0)
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
  const [recordError, setRecordError] = useState<string | null>(null)
  const [recordedBlobUrl, setRecordedBlobUrl] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    if (!isRecording) return
    setRecordingElapsedSeconds(0)
    const interval = setInterval(() => {
      setRecordingElapsedSeconds((s) => s + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [isRecording])

  useEffect(() => {
    if (recordedBlob) {
      const url = URL.createObjectURL(recordedBlob)
      setRecordedBlobUrl(url)
      return () => URL.revokeObjectURL(url)
    }
    setRecordedBlobUrl(null)
    return undefined
  }, [recordedBlob])

  const sizeError = Boolean(file && file.size > MAX_FILE_SIZE_BYTES)
  const typeError = Boolean(file && !fileMatchesType(file, type))
  const showFileErrors = touchedDropzone && Boolean(file) && (sizeError || typeError)
  const canSubmitFile = audioSource === 'file' && Boolean(file) && !sizeError && !typeError
  const canSubmitRecording = type === 'audio' && audioSource === 'record' && Boolean(recordedBlob)
  const canSubmit = canSubmitFile || canSubmitRecording

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const startRecording = useCallback(async () => {
    setRecordError(null)
    setRecordedBlob(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      // Negociar mime una sola vez y reutilizarlo en MediaRecorder y en el Blob final
      const { mime } = getPreferredAudioMimeType()
      const recorder = new MediaRecorder(stream, { mimeType: mime })
      mediaRecorderRef.current = recorder
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        if (chunksRef.current.length > 0) {
          setRecordedBlob(new Blob(chunksRef.current, { type: mime }))
        }
        stopStream()
      }
      recorder.start()
      setIsRecording(true)
    } catch (err) {
      setRecordError(err instanceof Error ? err.message : 'No se pudo acceder al micrófono')
      setIsRecording(false)
    }
  }, [stopStream])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
  }, [])

  // Nota: NO es un hook de React (no llama a ningún hook adentro) — es un
  // callback memoizado. Se renombra para no matchear la convención `use*`
  // (el linter de rules-of-hooks lo tomaba, por nombre, como un hook llamado
  // condicionalmente dentro de handleSubmit).
  const applyRecording = useCallback(() => {
    if (!recordedBlob) return
    // Derivar extensión del mime real del blob (consistente con lo negociado en startRecording)
    const ext = recordedBlob.type.startsWith('audio/ogg') ? '.ogg' : '.webm'
    const recordingFile = new File(
      [recordedBlob],
      `grabacion-${Date.now()}${ext}`,
      { type: recordedBlob.type }
    )
    onAdd(recordingFile, 'audio', description)
    setRecordedBlob(null)
    setAudioSource('file')
    onClose()
  }, [recordedBlob, description, onAdd, onClose])

  const discardRecording = useCallback(() => {
    setRecordedBlob(null)
    setRecordError(null)
    stopStream()
  }, [stopStream])

  useEffect(() => {
    if (!isOpen) {
      if (isRecording) stopRecording()
      stopStream()
      setRecordedBlob(null)
      setRecordError(null)
      setRecordingElapsedSeconds(0)
      setAudioSource('file')
    }
  }, [isOpen, isRecording, stopRecording, stopStream])

  const handleFileSelect = useCallback(
    (selectedFile: File | null) => {
      if (!selectedFile) {
        setFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
        return
      }
      setFile(selectedFile)
      setTouchedDropzone(true)
    },
    []
  )

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    handleFileSelect(f ?? null)
  }

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const f = e.dataTransfer.files?.[0]
      if (f) handleFileSelect(f)
    },
    [handleFileSelect]
  )

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }, [])

  const onDropzoneClick = () => {
    fileInputRef.current?.click()
  }

  const onDropzoneKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      fileInputRef.current?.click()
    }
  }

  const handleRemoveFile = () => {
    handleFileSelect(null)
    setTouchedDropzone(false)
  }

  const handleTypeChange = (newType: FileType) => {
    setType(newType)
    setFile(null)
    setRecordedBlob(null)
    setRecordError(null)
    setAudioSource('file')
    if (fileInputRef.current) fileInputRef.current.value = ''
    setTouchedDropzone(false)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    if (type === 'audio' && audioSource === 'record' && recordedBlob) {
      applyRecording()
      setDescription('')
      setType('audio')
      return
    }
    if (!file) return
    onAdd(file, type, description)
    setFile(null)
    setDescription('')
    setType('audio')
    setTouchedDropzone(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
    onClose()
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose()
  }

  if (!isOpen) return null

  const accept = getAcceptForType(type)
  const extensionsLabel = getExtensionsLabel(type)
  const category = file ? getTypeCategoryForIcon(type) : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="file-upload-modal-title"
    >
      <div className="w-full max-w-md overflow-hidden rounded-xl bg-white shadow-lg">
        <div className="p-6">
          <h2 id="file-upload-modal-title" className="mb-6 text-h2 text-ink-900">
            Agregar archivo
          </h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Tipo de archivo */}
            <div>
              <label htmlFor="file-type" className="mb-1.5 block text-sm font-semibold text-ink-700">
                Tipo de archivo
              </label>
              <select
                id="file-type"
                value={type}
                onChange={(e) => handleTypeChange(e.target.value as FileType)}
                className={selectClass}
                aria-describedby="file-type-formats"
              >
                {TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p id="file-type-formats" className="mt-1.5 text-sm text-ink-500">
                Formatos permitidos: {extensionsLabel}
              </p>
            </div>

            {/* Descripción opcional */}
            <div>
              <label htmlFor="file-description" className="mb-1.5 block text-sm font-semibold text-ink-700">
                Descripción (opcional)
              </label>
              <input
                type="text"
                id="file-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={inputClass}
                placeholder="Ej: Reunión de relevamiento"
              />
            </div>

            {/* Para audio: elegir subir o grabar */}
            {type === 'audio' && (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setAudioSource('file')}
                  className={cn(
                    'flex-1 rounded-md px-4 py-2 text-sm font-semibold transition-colors',
                    audioSource === 'file' ? 'bg-action text-action-on' : 'bg-ink-100 text-ink-700 hover:bg-ink-150'
                  )}
                >
                  Subir archivo
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAudioSource('record')
                    setFile(null)
                    setTouchedDropzone(false)
                    if (fileInputRef.current) fileInputRef.current.value = ''
                  }}
                  className={cn(
                    'flex-1 rounded-md px-4 py-2 text-sm font-semibold transition-colors',
                    audioSource === 'record' ? 'bg-action text-action-on' : 'bg-ink-100 text-ink-700 hover:bg-ink-150'
                  )}
                >
                  Grabar audio
                </button>
              </div>
            )}

            {/* Dropzone o grabación o tarjeta de archivo */}
            <div>
              <span className="mb-1.5 block text-sm font-semibold text-ink-700">
                {audioSource === 'record' && type === 'audio' ? 'Grabación' : 'Archivo'}
              </span>

              {type === 'audio' && audioSource === 'record' ? (
                <div className="space-y-3">
                  {recordError && (
                    <p className="text-sm text-danger" role="alert">
                      {recordError}
                    </p>
                  )}
                  {!recordedBlob ? (
                    <div className="rounded-xl border-2 border-dashed border-ink-300 p-6 text-center">
                      {!isRecording ? (
                        <>
                          <p className="mb-4 text-ink-600">
                            Presioná Grabar para comenzar la grabación
                          </p>
                          <Button type="button" variant="danger" onClick={startRecording} disabled={isRecording}>
                            <span className="h-3 w-3 animate-pulse rounded-full bg-danger" />
                            Grabar
                          </Button>
                        </>
                      ) : (
                        <>
                          <p className="mb-4 flex items-center justify-center gap-2 text-ink-600">
                            <span className="h-3 w-3 animate-pulse rounded-full bg-danger" />
                            Grabando... {formatRecordingTime(recordingElapsedSeconds)}
                          </p>
                          <Button type="button" onClick={stopRecording}>
                            Detener
                          </Button>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3 rounded-xl border border-ink-200 bg-ink-50 p-4">
                        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-ink-200 bg-white text-ink-500">
                          <Music className="h-5 w-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold text-ink-900">Grabación lista</p>
                          <p className="text-sm text-ink-500">
                            {formatFileSize(recordedBlob.size)}
                          </p>
                        </div>
                      </div>
                      {recordedBlobUrl && (
                        <audio controls src={recordedBlobUrl} className="w-full" />
                      )}
                      <div className="flex gap-2">
                        <Button type="button" className="flex-1" onClick={applyRecording}>
                          Usar grabación
                        </Button>
                        <Button type="button" variant="secondary" className="flex-1" onClick={discardRecording}>
                          Descartar
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ) : !file ? (
                <>
                  <div
                    onClick={onDropzoneClick}
                    onKeyDown={onDropzoneKeyDown}
                    onDrop={onDrop}
                    onDragOver={onDragOver}
                    onDragLeave={onDragLeave}
                    role="button"
                    tabIndex={0}
                    className={cn(
                      'relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center outline-none transition-colors focus:ring-[3px] focus:ring-action-ring',
                      dragOver
                        ? 'border-accent bg-accent-tint'
                        : 'border-ink-300 bg-ink-50 hover:border-ink-400'
                    )}
                    aria-label="Arrastrá tu archivo aquí o seleccioná uno"
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      id="file-input"
                      accept={accept}
                      onChange={onInputChange}
                      className="sr-only"
                      aria-hidden
                    />
                    <p className="font-semibold text-ink-700">Arrastrá tu archivo aquí</p>
                    <p className="mt-1 text-sm text-ink-500">o</p>
                    <span className="mt-3 inline-block rounded-md bg-ink-200 px-4 py-2 text-sm font-semibold text-ink-800 transition-colors hover:bg-ink-150">
                      Seleccionar archivo
                    </span>
                  </div>

                  <p className="mt-2 text-xs text-ink-500">
                    Máximo: {formatFileSize(MAX_FILE_SIZE_BYTES)}
                  </p>

                  {showFileErrors && (
                    <div className="mt-2 space-y-1 text-sm text-danger" role="alert">
                      {sizeError && (
                        <p>El archivo supera el tamaño máximo permitido.</p>
                      )}
                      {typeError && (
                        <p>El tipo de archivo no coincide con &quot;{TYPE_OPTIONS.find((o) => o.value === type)?.label}&quot;. Permitidos: {extensionsLabel}</p>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div
                  className="flex items-start gap-3 rounded-xl border border-ink-200 bg-ink-50 p-4"
                  role="status"
                  aria-label={`Archivo seleccionado: ${file.name}`}
                >
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-ink-200 bg-white text-ink-500">
                    {category && <CategoryIcon category={category} className="h-5 w-5" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-ink-900" title={file.name}>
                      {file.name}
                    </p>
                    <p className="mt-0.5 text-sm text-ink-500">
                      {formatFileSize(file.size)}
                      {getFileExtension(file.name) && (
                        <span className="ml-1">· {getFileExtension(file.name)}</span>
                      )}
                    </p>
                    {(sizeError || typeError) && (
                      <p className="mt-1 text-sm text-danger">
                        {sizeError && 'Supera el tamaño máximo. '}
                        {typeError && 'Tipo no permitido para esta categoría.'}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={handleRemoveFile}
                    className="flex-shrink-0 rounded-md p-2 text-ink-500 transition-colors hover:bg-danger-bg hover:text-danger"
                    title="Quitar archivo"
                    aria-label="Quitar archivo"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              )}
            </div>

            {/* CTA: cuando hay grabación lista, los botones están inline; solo mostramos Cancelar */}
            <div className="flex gap-3 pt-2">
              {!(type === 'audio' && audioSource === 'record' && recordedBlob) && (
                <Button type="submit" className="flex-1" disabled={!canSubmit}>
                  Subir archivo
                </Button>
              )}
              <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
                Cancelar
              </Button>
            </div>

            <p className="pt-1 text-center text-xs text-ink-500">
              Este archivo se utilizará como contexto para generar o actualizar el documento.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
