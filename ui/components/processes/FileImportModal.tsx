'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, X, FileText } from 'lucide-react'
import { Button } from '@/shared/ui/components'
import { cn } from '@/shared/ui/cn'
import FolderSelector from '@/components/processes/FolderSelector'
import { importDocuments } from '@/lib/api'
import {
  EXTENSIONS_BY_TYPE,
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  getFileExtension,
} from '@/lib/fileUploadValidation'

const IMPORT_EXTENSIONS = EXTENSIONS_BY_TYPE.text
const ACCEPT = IMPORT_EXTENSIONS.join(',')

interface FileImportModalProps {
  workspaceId: string
  defaultFolderId?: string | null
  open: boolean
  onClose: () => void
  onImported?: () => void
}

export default function FileImportModal({
  workspaceId,
  defaultFolderId,
  open,
  onClose,
  onImported,
}: FileImportModalProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [folderId, setFolderId] = useState(defaultFolderId ?? '')
  const [files, setFiles] = useState<File[]>([])
  const [requiresApproval, setRequiresApproval] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setFolderId(defaultFolderId ?? '')
    }
  }, [open, defaultFolderId])

  const resetAndClose = useCallback(() => {
    setFiles([])
    setError(null)
    setRequiresApproval(true)
    onClose()
  }, [onClose])

  const validateAndAdd = useCallback((incoming: FileList | File[]) => {
    const next: File[] = []
    const rejected: string[] = []

    Array.from(incoming).forEach((file) => {
      const ext = getFileExtension(file.name)
      if (!IMPORT_EXTENSIONS.includes(ext)) {
        rejected.push(`${file.name} (formato no permitido)`)
        return
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejected.push(`${file.name} (supera ${formatFileSize(MAX_FILE_SIZE_BYTES)})`)
        return
      }
      next.push(file)
    })

    if (rejected.length) {
      setError(rejected.join('. '))
    } else {
      setError(null)
    }
    if (next.length) {
      setFiles((prev) => [...prev, ...next])
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      if (e.dataTransfer.files?.length) {
        validateAndAdd(e.dataTransfer.files)
      }
    },
    [validateAndAdd]
  )

  const handleSubmit = async () => {
    if (!folderId) {
      setError('Seleccioná una carpeta destino')
      return
    }
    if (!files.length) {
      setError('Agregá al menos un archivo')
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('folder_id', folderId)
      formData.append('requires_approval', requiresApproval ? 'true' : 'false')
      files.forEach((file) => formData.append('files', file))

      await importDocuments(formData)
      onImported?.()
      resetAndClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al importar')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="w-full max-w-lg rounded-lg bg-white shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-modal-title"
      >
        <div className="flex items-center justify-between border-b border-ink-200 px-6 py-4">
          <h2 id="import-modal-title" className="text-h3 text-ink-900">
            Importar archivos
          </h2>
          <button
            type="button"
            onClick={resetAndClose}
            className="rounded-md p-1 text-ink-500 hover:bg-ink-100 hover:text-ink-800"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 px-6 py-5">
          <FolderSelector
            workspaceId={workspaceId}
            value={folderId}
            onChange={setFolderId}
            required
          />

          <div
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-8 transition-colors',
              dragOver ? 'border-accent bg-accent/5' : 'border-ink-300 bg-ink-50 hover:border-ink-400'
            )}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="mb-2 h-8 w-8 text-ink-400" />
            <p className="text-sm font-medium text-ink-700">
              Arrastrá archivos o hacé clic para seleccionar
            </p>
            <p className="mt-1 text-xs text-ink-500">
              {IMPORT_EXTENSIONS.join(', ')} — máx. {formatFileSize(MAX_FILE_SIZE_BYTES)} c/u
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) validateAndAdd(e.target.files)
                e.target.value = ''
              }}
            />
          </div>

          {files.length > 0 && (
            <ul className="max-h-40 space-y-2 overflow-y-auto">
              {files.map((file, index) => (
                <li
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between rounded-md border border-ink-200 bg-white px-3 py-2 text-sm"
                >
                  <span className="flex min-w-0 items-center gap-2 text-ink-800">
                    <FileText className="h-4 w-4 shrink-0 text-ink-400" />
                    <span className="truncate">{file.name}</span>
                    <span className="shrink-0 text-ink-500">({formatFileSize(file.size)})</span>
                  </span>
                  <button
                    type="button"
                    className="ml-2 text-ink-400 hover:text-danger"
                    onClick={() => setFiles((prev) => prev.filter((_, i) => i !== index))}
                    aria-label={`Quitar ${file.name}`}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <label className="flex cursor-pointer items-start gap-3 rounded-md border border-ink-200 bg-ink-50 px-4 py-3">
            <input
              type="checkbox"
              checked={requiresApproval}
              onChange={(e) => setRequiresApproval(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-ink-300 text-accent focus:ring-action-ring"
            />
            <span>
              <span className="block text-sm font-medium text-ink-800">Requiere aprobación</span>
              <span className="block text-xs text-ink-500">
                Si está desmarcado, el archivo queda aprobado y disponible de inmediato.
              </span>
            </span>
          </label>

          {error && (
            <p className="rounded-md border border-danger-bd bg-danger-bg px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-ink-200 px-6 py-4">
          <Button type="button" variant="secondary" onClick={resetAndClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button type="button" variant="create" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Importando…' : 'Importar'}
          </Button>
        </div>
      </div>
    </div>
  )
}
