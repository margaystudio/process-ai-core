'use client'

import { useState, useRef, useCallback } from 'react'
import {
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  getFileExtension,
  fileMatchesType,
  type FileType,
} from '@/lib/fileUploadValidation'

export type { FileType } from '@/lib/fileUploadValidation'

const TYPE_OPTIONS: { value: FileType; label: string; extensions: string[] }[] = [
  { value: 'audio', label: 'Audio', extensions: ['.m4a', '.mp3', '.wav'] },
  { value: 'text', label: 'Documento', extensions: ['.txt', '.md'] },
  { value: 'image', label: 'Imagen', extensions: ['.png', '.jpg', '.jpeg', '.webp'] },
  { value: 'video', label: 'Otro', extensions: ['.mp4', '.mov', '.mkv'] },
]

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

  const sizeError = file && file.size > MAX_FILE_SIZE_BYTES
  const typeError = file && !fileMatchesType(file, type)
  const showFileErrors = touchedDropzone && file && (sizeError || typeError)
  const canSubmit = file && !sizeError && !typeError && type

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
    if (fileInputRef.current) fileInputRef.current.value = ''
    setTouchedDropzone(false)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !file) return
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

            {/* Dropzone o tarjeta de archivo */}
            <div>
              <span className="block text-sm font-medium text-gray-700 mb-1.5">
                Archivo
              </span>

              {!file ? (
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

            {/* CTA */}
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={!canSubmit}
                className="flex-1 px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                Subir archivo
              </button>
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
