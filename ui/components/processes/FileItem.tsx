import { FileType } from './FileUploadModal'

export interface FileItemData {
  id: string
  file: File
  type: FileType
  description: string
}

interface FileItemProps {
  item: FileItemData
  onRemove: (id: string) => void
}

export default function FileItem({ item, onRemove }: FileItemProps) {
  const getTypeLabel = (type: FileType): string => {
    switch (type) {
      case 'audio':
        return '🎵 Audio'
      case 'video':
        return '🎬 Video'
      case 'image':
        return '🖼️ Imagen'
      case 'text':
        return '📄 Texto'
    }
  }

  const getPreview = () => {
    if (item.type === 'image') {
      return (
        <img
          src={URL.createObjectURL(item.file)}
          alt={item.description || item.file.name}
          className="w-20 h-20 object-cover rounded"
        />
      )
    }
    return (
      <div className="w-20 h-20 bg-gray-100 rounded flex items-center justify-center text-2xl">
        {item.type === 'audio' && '🎵'}
        {item.type === 'video' && '🎬'}
        {item.type === 'text' && '📄'}
      </div>
    )
  }

  return (
    <div className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
      <div className="flex-shrink-0">
        {getPreview()}
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-900 truncate">{item.file.name}</p>
            <p className="text-sm text-gray-500 mt-1">{getTypeLabel(item.type)}</p>
            {item.description && (
              <p className="text-sm text-gray-600 mt-1">{item.description}</p>
            )}
            <p className="text-xs text-gray-400 mt-1">
              {(item.file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
          
          <button
            type="button"
            onClick={() => onRemove(item.id)}
            className="flex-shrink-0 text-red-600 hover:text-red-700 p-1"
            title="Eliminar archivo"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

