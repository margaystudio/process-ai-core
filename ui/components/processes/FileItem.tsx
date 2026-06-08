import { Music, Video, Image as ImageIcon, FileText, Trash2 } from 'lucide-react'
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

const TYPE_META: Record<FileType, { label: string; Icon: typeof Music }> = {
  audio: { label: 'Audio', Icon: Music },
  video: { label: 'Video', Icon: Video },
  image: { label: 'Imagen', Icon: ImageIcon },
  text: { label: 'Texto', Icon: FileText },
}

export default function FileItem({ item, onRemove }: FileItemProps) {
  const meta = TYPE_META[item.type]

  const preview = item.type === 'image' ? (
    <img
      src={URL.createObjectURL(item.file)}
      alt={item.description || item.file.name}
      className="h-20 w-20 rounded object-cover"
    />
  ) : (
    <div className="flex h-20 w-20 items-center justify-center rounded bg-ink-100 text-ink-500">
      <meta.Icon className="h-7 w-7" />
    </div>
  )

  return (
    <div className="flex items-start gap-4 rounded-lg border border-ink-200 p-4 transition-colors hover:bg-ink-50">
      <div className="flex-shrink-0">{preview}</div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-ink-900">{item.file.name}</p>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-500">
              <meta.Icon className="h-3.5 w-3.5" />
              {meta.label}
            </p>
            {item.description && (
              <p className="mt-1 text-sm text-ink-600">{item.description}</p>
            )}
            <p className="mt-1 text-xs text-ink-400">
              {(item.file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>

          <button
            type="button"
            onClick={() => onRemove(item.id)}
            className="flex-shrink-0 rounded-md p-1 text-danger hover:bg-danger-bg"
            title="Eliminar archivo"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
