'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import {
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  getFileExtension,
  fileMatchesType,
  type FileType,
} from '@/lib/fileUploadValidation'

export type { FileType } from '@/lib/fileUploadValidation'

const TYPE_OPTIONS: { value: FileType; label: string; extensions: string[] }[] = [
  { value: 'audio', label: 'Audio', extensions: ['.m4a', '.mp3', '.wav', '.webm', '.ogg'] },
  { value: 'text', label: 'Documento', extensions: ['.txt', '.md'] },
  { value: 'image', label: 'Imagen', extensions: ['.png', '.jpg', '.jpeg', '.webp'] },
  { value: 'video', label: 'Otro', extensions: ['.mp4', '.mov', '.mkv'] },
]

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

  const useRecording = useCallback(() => {
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
      useRecording()
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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="file-upload-modal-title"
    >
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full overflow-hidden">
        <div className="p-6">
          <h2 id="file-upload-modal-title" className="text-xl font-semibold text-gray-900 mb-6">
            Agregar Archivo
          </h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Tipo de archivo */}
            <div>
              <label htmlFor="file-type" className="block text-sm font-medium text-gray-700 mb-1.5">
                Tipo de archivo
              </label>
              <select
                id="file-type"
                value={type}
                onChange={(e) => handleTypeChange(e.target.value as FileType)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-gray-900 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                aria-describedby="file-type-formats"
              >
                {TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p id="file-type-formats" className="mt-1.5 text-sm text-gray-500">
                Formatos permitidos: {extensionsLabel}
              </p>
            </div>

            {/* Descripción opcional */}
            <div>
              <label htmlFor="file-description" className="block text-sm font-medium text-gray-700 mb-1.5">
                Descripción (opcional)
              </label>
              <input
                type="text"
                id="file-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ej: Reunión de relevamiento"
              />
            </div>

            {/* Para audio: elegir subir o grabar */}
            {type === 'audio' && (
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setAudioSource('file')}
                  className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    audioSource === 'file'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
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
                  className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    audioSource === 'record'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Grabar audio
                </button>
              </div>
            )}

            {/* Dropzone o grabación o tarjeta de archivo */}
            <div>
              <span className="block text-sm font-medium text-gray-700 mb-1.5">
                {audioSource === 'record' && type === 'audio' ? 'Grabación' : 'Archivo'}
              </span>

              {type === 'audio' && audioSource === 'record' ? (
                <div className="space-y-3">
                  {recordError && (
                    <p className="text-sm text-red-600" role="alert">
                      {recordError}
                    </p>
                  )}
                  {!recordedBlob ? (
                    <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center">
                      {!isRecording ? (
                        <>
                          <p className="text-gray-600 mb-4">
                            Presioná Grabar para comenzar la grabación
                          </p>
                          <button
                            type="button"
                            onClick={startRecording}
                            disabled={isRecording}
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                          >
                            <span className="w-3 h-3 rounded-full bg-white animate-pulse" />
                            Grabar
                          </button>
                        </>
                      ) : (
                        <>
                          <p className="text-gray-600 mb-4 flex items-center justify-center gap-2">
                            <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
                            Grabando... {formatRecordingTime(recordingElapsedSeconds)}
                          </p>
                          <button
                            type="button"
                            onClick={stopRecording}
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gray-800 text-white font-medium rounded-lg hover:bg-gray-900 focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                          >
                            Detener
                          </button>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-3 p-4 rounded-xl border border-gray-200 bg-gray-50">
                        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center text-lg">
                          🎵
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900">Grabación lista</p>
                          <p className="text-sm text-gray-500">
                            {formatFileSize(recordedBlob.size)}
                          </p>
                        </div>
                      </div>
                      {recordedBlobUrl && (
                        <audio controls src={recordedBlobUrl} className="w-full" />
                      )}
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={useRecording}
                          className="flex-1 px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        >
                          Usar grabación
                        </button>
                        <button
                          type="button"
                          onClick={discardRecording}
                          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
                        >
                          Descartar
                        </button>
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
                    className={`
                      relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
                      transition-colors outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                      ${dragOver
                        ? 'border-blue-500 bg-blue-50/50'
                        : 'border-gray-300 bg-gray-50/50 hover:border-gray-400 hover:bg-gray-50'
                      }
                    `}
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
                    <p className="text-gray-700 font-medium">Arrastrá tu archivo aquí</p>
                    <p className="text-sm text-gray-500 mt-1">o</p>
                    <span className="inline-block mt-3 px-4 py-2 rounded-lg bg-gray-200 text-gray-800 text-sm font-medium hover:bg-gray-300 transition-colors">
                      Seleccionar archivo
                    </span>
                  </div>

                  <p className="mt-2 text-xs text-gray-500">
                    Máximo: {formatFileSize(MAX_FILE_SIZE_BYTES)}
                  </p>

                  {showFileErrors && (
                    <div className="mt-2 space-y-1 text-sm text-red-600" role="alert">
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
                  className="flex items-start gap-3 p-4 rounded-xl border border-gray-200 bg-gray-50"
                  role="status"
                  aria-label={`Archivo seleccionado: ${file.name}`}
                >
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center text-lg">
                    {category === 'audio' && '🎵'}
                    {category === 'document' && '📄'}
                    {category === 'image' && '🖼️'}
                    {category === 'other' && '📎'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate" title={file.name}>
                      {file.name}
                    </p>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {formatFileSize(file.size)}
                      {getFileExtension(file.name) && (
                        <span className="ml-1">· {getFileExtension(file.name)}</span>
                      )}
                    </p>
                    {(sizeError || typeError) && (
                      <p className="text-sm text-red-600 mt-1">
                        {sizeError && 'Supera el tamaño máximo. '}
                        {typeError && 'Tipo no permitido para esta categoría.'}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={handleRemoveFile}
                    className="flex-shrink-0 p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Quitar archivo"
                    aria-label="Quitar archivo"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              )}
            </div>

            {/* CTA: cuando hay grabación lista, los botones están inline; solo mostramos Cancelar */}
            <div className="flex gap-3 pt-2">
              {!(type === 'audio' && audioSource === 'record' && recordedBlob) && (
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                >
                  Subir archivo
                </button>
              )}
              <button
                type="button"
                onClick={onClose}
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 focus:ring-2 focus:ring-gray-300 focus:ring-offset-2"
              >
                Cancelar
              </button>
            </div>

            <p className="text-xs text-gray-500 text-center pt-1">
              Este archivo se utilizará como contexto para generar o actualizar el documento.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
