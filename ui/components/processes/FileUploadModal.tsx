'use client'

import { useState, useRef } from 'react'

export type FileType = 'audio' | 'video' | 'image' | 'text'

interface FileUploadModalProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (file: File, type: FileType, description: string) => void
}

export default function FileUploadModal({ isOpen, onClose, onAdd }: FileUploadModalProps) {
  const [type, setType] = useState<FileType>('audio')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOpen) return null

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      setFile(selectedFile)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (file) {
      onAdd(file, type, description)
      // Reset form
      setFile(null)
      setDescription('')
      setType('audio')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      onClose()
    }
  }

  const getAcceptTypes = (fileType: FileType): string => {
    switch (fileType) {
      case 'audio':
        return '.m4a,.mp3,.wav'
      case 'video':
        return '.mp4,.mov,.mkv'
      case 'image':
        return '.png,.jpg,.jpeg,.webp'
      case 'text':
        return '.txt,.md'
      default:
        return ''
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h2 className="text-xl font-semibold mb-4">Agregar Archivo</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="file-type" className="block text-sm font-medium text-gray-700 mb-2">
              Tipo de Archivo *
            </label>
            <select
              id="file-type"
              value={type}
              onChange={(e) => {
                setType(e.target.value as FileType)
                setFile(null)
                if (fileInputRef.current) {
                  fileInputRef.current.value = ''
                }
              }}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="audio">Audio (.m4a, .mp3, .wav)</option>
              <option value="video">Video (.mp4, .mov, .mkv)</option>
              <option value="image">Imagen (.png, .jpg, .jpeg, .webp)</option>
              <option value="text">Texto (.txt, .md)</option>
            </select>
          </div>

          <div>
            <label htmlFor="file-description" className="block text-sm font-medium text-gray-700 mb-2">
              Descripción (opcional)
            </label>
            <input
              type="text"
              id="file-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Ej: Reunión de relevamiento"
            />
          </div>

          <div>
            <label htmlFor="file-input" className="block text-sm font-medium text-gray-700 mb-2">
              Seleccionar Archivo *
            </label>
            <input
              ref={fileInputRef}
              type="file"
              id="file-input"
              accept={getAcceptTypes(type)}
              onChange={handleFileSelect}
              required
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
            {file && (
              <p className="mt-2 text-sm text-gray-600">
                Seleccionado: <span className="font-medium">{file.name}</span> ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="submit"
              disabled={!file}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Agregar
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


