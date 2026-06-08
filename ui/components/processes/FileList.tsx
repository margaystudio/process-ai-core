import { FileItemData } from './FileItem'
import FileItem from './FileItem'

interface FileListProps {
  files: FileItemData[]
  onRemove: (id: string) => void
}

export default function FileList({ files, onRemove }: FileListProps) {
  if (files.length === 0) {
    return (
      <div className="py-8 text-center text-ink-500">
        <p>No hay archivos agregados</p>
        <p className="mt-1 text-sm">Hacé clic en "Agregar archivo" para comenzar</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {files.map((file) => (
        <FileItem key={file.id} item={file} onRemove={onRemove} />
      ))}
    </div>
  )
}
