'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  FileText,
  Loader2,
  Send,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useAsync } from '@/hooks/useAsync'
import { useCanManageWorkspace } from '@/hooks/useHasPermission'
import {
  approveDocumentValidation,
  getDocumentVersions,
  importDocuments,
  listDocuments,
  listFolders,
  submitVersionForReview,
  type Document,
} from '@/lib/api'
import {
  EXTENSIONS_BY_TYPE,
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  getFileExtension,
} from '@/lib/fileUploadValidation'
import { cn } from '@/shared/ui/cn'

type ImportStatus =
  | 'queued'
  | 'importing'
  | 'imported'
  | 'sending'
  | 'pending_validation'
  | 'approving'
  | 'approved'
  | 'error'

interface ImportItem {
  id: string
  file: File | null
  fileName: string
  size: number | null
  document: Document | null
  status: ImportStatus
  selected: boolean
  error: string | null
}

const IMPORT_EXTENSIONS = EXTENSIONS_BY_TYPE.text
const ACCEPT = IMPORT_EXTENSIONS.join(',')

const STATUS_LABELS: Record<ImportStatus, string> = {
  queued: 'Listo para importar',
  importing: 'Importando…',
  imported: 'Importado · Borrador',
  sending: 'Enviando…',
  pending_validation: 'Pendiente de aprobación',
  approving: 'Aprobando…',
  approved: 'Aprobado',
  error: 'Requiere atención',
}

function isImportedDocument(document: Document): boolean {
  return document.description?.startsWith('Archivo importado:') ?? false
}

function itemTone(status: ImportStatus): string {
  if (status === 'approved') return 'border-green-border bg-green-bg text-green-text'
  if (status === 'error') return 'border-danger-bd bg-danger-bg text-danger'
  if (status === 'pending_validation') return 'border-amber-border bg-amber-bg text-[#7A5600]'
  if (status === 'importing' || status === 'sending' || status === 'approving') {
    return 'border-indigo-border bg-indigo-tint text-indigo'
  }
  return 'border-line bg-surface-track text-ink-500'
}

export default function ImportPage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const {
    selectedWorkspaceId,
    currentUser,
  } = useWorkspace()
  const [folderId, setFolderId] = useState('')
  const [items, setItems] = useState<ImportItem[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [running, setRunning] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)

  const { canManage: canAdminister, loading: canAdministerLoading } = useCanManageWorkspace()

  const foldersAsync = useAsync(
    async () => {
      if (!selectedWorkspaceId) return []
      return listFolders(selectedWorkspaceId)
    },
    [selectedWorkspaceId]
  )

  const pendingAsync = useAsync(
    async () => {
      if (!selectedWorkspaceId || !folderId) return []
      const documents = await listDocuments(selectedWorkspaceId, folderId, 'process')
      return documents.filter(
        (document) =>
          document.status === 'pending_validation' && isImportedDocument(document)
      )
    },
    [selectedWorkspaceId, folderId]
  )

  useEffect(() => {
    const pending = pendingAsync.data ?? []
    if (!pending.length) return
    setItems((current) => {
      const known = new Set(current.map((item) => item.document?.id).filter(Boolean))
      const additions = pending
        .filter((document) => !known.has(document.id))
        .map<ImportItem>((document) => ({
          id: `document-${document.id}`,
          file: null,
          fileName: document.name,
          size: null,
          document,
          status: 'pending_validation',
          selected: false,
          error: null,
        }))
      return additions.length ? [...current, ...additions] : current
    })
  }, [pendingAsync.data])

  useEffect(() => {
    setItems([])
    setPageError(null)
  }, [folderId, selectedWorkspaceId])

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const accepted: ImportItem[] = []
    const rejected: string[] = []
    Array.from(incoming).forEach((file) => {
      const extension = getFileExtension(file.name)
      if (!IMPORT_EXTENSIONS.includes(extension)) {
        rejected.push(`${file.name}: formato no permitido`)
        return
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        rejected.push(`${file.name}: supera ${formatFileSize(MAX_FILE_SIZE_BYTES)}`)
        return
      }
      accepted.push({
        id: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
        file,
        fileName: file.name,
        size: file.size,
        document: null,
        status: 'queued',
        selected: true,
        error: null,
      })
    })
    setItems((current) => [...current, ...accepted])
    setPageError(rejected.length ? rejected.join('. ') : null)
  }, [])

  const updateItem = useCallback((id: string, patch: Partial<ImportItem>) => {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item))
    )
  }, [])

  const importQueued = async () => {
    if (!folderId) {
      setPageError('Elegí una carpeta destino')
      return
    }
    const queued = items.filter((item) => item.status === 'queued' && item.file)
    if (!queued.length) {
      setPageError('Agregá al menos un archivo para importar')
      return
    }

    setRunning(true)
    setPageError(null)
    for (const item of queued) {
      updateItem(item.id, { status: 'importing', error: null })
      try {
        const formData = new FormData()
        formData.append('folder_id', folderId)
        formData.append('requires_approval', 'true')
        formData.append('files', item.file as File)
        const [document] = await importDocuments(formData)
        updateItem(item.id, {
          document,
          status: 'imported',
          selected: true,
        })
      } catch (error) {
        updateItem(item.id, {
          status: 'error',
          selected: false,
          error: error instanceof Error ? error.message : 'Error al importar',
        })
      }
    }
    setRunning(false)
  }

  const sendSelectedForApproval = async () => {
    const selected = items.filter(
      (item) => item.selected && item.status === 'imported' && item.document
    )
    if (!selected.length) return

    setRunning(true)
    setPageError(null)
    for (const item of selected) {
      updateItem(item.id, { status: 'sending', error: null })
      try {
        const document = item.document as Document
        const versions = await getDocumentVersions(document.id)
        const draft = versions.find((version) => version.version_status === 'DRAFT')
        if (!draft) throw new Error('No se encontró el borrador importado')
        await submitVersionForReview(
          document.id,
          draft.id,
          currentUser?.id,
          selectedWorkspaceId ?? undefined,
          [],
          'Importación por lote'
        )
        updateItem(item.id, {
          status: 'pending_validation',
          selected: false,
          document: { ...document, status: 'pending_validation' },
        })
      } catch (error) {
        updateItem(item.id, {
          status: 'imported',
          error: error instanceof Error ? error.message : 'Error al enviar a aprobación',
        })
      }
    }
    setRunning(false)
    pendingAsync.reload()
  }

  const approveSelected = async () => {
    const selected = items.filter(
      (item) =>
        item.selected && item.status === 'pending_validation' && item.document
    )
    if (!selected.length) return

    setRunning(true)
    setPageError(null)
    for (const item of selected) {
      updateItem(item.id, { status: 'approving', error: null })
      try {
        // deferFreeze: el lote no congela el PDF dentro de cada request.
        // Congelar cuesta un render + una subida; en un lote secuencial son
        // minutos sin cancelación. El artefacto lo produce el barrido
        // (tools/freeze_pending_pdfs.py) o la primera apertura, lo que pase
        // antes — y sale idéntico, porque el acta ya está congelada en la
        // versión.
        await approveDocumentValidation(
          (item.document as Document).id,
          undefined,
          undefined,
          undefined,
          true
        )
        updateItem(item.id, {
          status: 'approved',
          selected: false,
          document: { ...(item.document as Document), status: 'approved' },
        })
      } catch (error) {
        updateItem(item.id, {
          status: 'pending_validation',
          error: error instanceof Error ? error.message : 'Error al aprobar',
        })
      }
    }
    setRunning(false)
  }

  const queuedCount = items.filter((item) => item.status === 'queued').length
  const importableCount = items.filter((item) => item.file !== null).length
  const processedCount = items.filter(
    (item) => item.file !== null && item.status !== 'queued' && item.status !== 'importing'
  ).length
  const progress = importableCount
    ? Math.round((processedCount / importableCount) * 100)
    : 0
  const selectedDrafts = items.filter(
    (item) => item.selected && item.status === 'imported'
  ).length
  const selectedPending = items.filter(
    (item) => item.selected && item.status === 'pending_validation'
  ).length
  const hasActiveItems = items.length > 0

  const folders = foldersAsync.data ?? []
  const folderName = folders.find((folder) => folder.id === folderId)?.name

  if (canAdministerLoading) {
    return (
      <main className="mx-auto max-w-[760px] px-6 py-12">
        <div className="h-40 animate-pulse rounded-lg bg-ink-100" aria-busy="true" />
      </main>
    )
  }

  if (!canAdminister) {
    return (
      <main className="mx-auto max-w-[760px] px-6 py-12">
        <div className="rounded-[13px] border border-danger-bd bg-danger-bg px-6 py-8 text-center">
          <ShieldCheck className="mx-auto h-8 w-8 text-danger" />
          <h1 className="mt-3 text-lg font-extrabold text-ink-900">Acceso restringido</h1>
          <p className="mt-1 text-[13px] text-ink-500">
            Se requieren permisos de administración del workspace para importar por lote.
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-[900px] px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-1.5 text-xs font-bold uppercase tracking-[.1em] text-indigo">
            Importación por lote
          </div>
          <h1 className="text-[25px] font-extrabold text-ink-900">
            Incorporá documentación existente
          </h1>
          <p className="mt-1.5 text-[13px] text-ink-400">
            Elegí una carpeta, cargá los archivos y seguí su circuito de aprobación.
          </p>
        </div>
      </div>

      <div className="mb-5 flex items-start gap-3 rounded-[13px] border border-indigo-border bg-indigo-tint px-[18px] py-3.5">
        <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-[9px] border border-indigo-border bg-surface text-indigo">
          <ShieldCheck className="h-[18px] w-[18px]" />
        </span>
        <div>
          <p className="text-[13px] font-extrabold text-ink-800">
            El documento original siempre se conserva
          </p>
          <p className="text-xs leading-relaxed text-ink-500">
            Process AI genera una representación derivada. La fuente oficial nunca cambia.
          </p>
        </div>
      </div>

      <section className="mb-4 rounded-[14px] border border-line bg-surface p-5 shadow-card">
        <label htmlFor="import-folder" className="mb-2 block text-[13px] font-bold text-ink-900">
          Carpeta destino
        </label>
        {foldersAsync.status === 'idle' || foldersAsync.status === 'loading' ? (
          <div className="h-11 animate-pulse rounded-[10px] bg-ink-100" />
        ) : foldersAsync.status === 'error' ? (
          <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-sm text-danger">
            {foldersAsync.error}
          </div>
        ) : (
          <select
            id="import-folder"
            value={folderId}
            onChange={(event) => setFolderId(event.target.value)}
            className="h-11 w-full rounded-[10px] border border-line-input bg-surface px-3.5 text-sm font-semibold text-ink-800 outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
          >
            <option value="">Seleccionar carpeta…</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.path || folder.name}
              </option>
            ))}
          </select>
        )}
      </section>

      <section
        className={cn(
          'mb-4 rounded-[16px] border-2 border-dashed px-6 py-10 text-center transition-colors',
          dragOver
            ? 'border-indigo bg-indigo-tint'
            : 'border-line-input bg-surface-hover'
        )}
        onDragOver={(event) => {
          event.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragOver(false)
          if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files)
        }}
      >
        <span className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-[14px] bg-indigo-tint text-indigo">
          <Upload className="h-7 w-7" />
        </span>
        <h2 className="text-base font-extrabold text-ink-900">Arrastrá tus archivos acá</h2>
        <p className="mb-4 mt-1 text-[13px] text-ink-400">
          {IMPORT_EXTENSIONS.join(', ')} · máximo {formatFileSize(MAX_FILE_SIZE_BYTES)} por archivo
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex h-[42px] items-center gap-2 rounded-[10px] bg-ink-800 px-[18px] text-[13.5px] font-bold text-white"
        >
          Seleccionar archivos
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(event) => {
            if (event.target.files?.length) addFiles(event.target.files)
            event.target.value = ''
          }}
        />
      </section>

      {hasActiveItems ? (
        <section className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
          <div className="border-b border-line px-5 py-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-[13px] font-extrabold text-ink-900">
                  Documentos {folderName ? `· ${folderName}` : ''}
                </h2>
                <p className="mt-0.5 text-[11.5px] text-ink-400">
                  Progreso y estado de aprobación por archivo.
                </p>
              </div>
              {importableCount > 0 ? (
                <span className="font-mono text-[12px] font-extrabold text-indigo">
                  {progress}%
                </span>
              ) : null}
            </div>
            {importableCount > 0 ? (
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-line-soft">
                <div
                  className="h-full rounded-full bg-indigo transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            ) : null}
          </div>

          <div className="divide-y divide-line-soft">
            {items.map((item) => {
              const busy = ['importing', 'sending', 'approving'].includes(item.status)
              const selectable = ['imported', 'pending_validation'].includes(item.status)
              return (
                <div key={item.id} className="flex items-start gap-3 px-5 py-3.5">
                  <input
                    type="checkbox"
                    checked={item.selected}
                    disabled={!selectable || running}
                    onChange={(event) =>
                      updateItem(item.id, { selected: event.target.checked })
                    }
                    aria-label={`Seleccionar ${item.fileName}`}
                    className="mt-2 h-4 w-4 rounded border-line-input text-indigo focus:ring-indigo"
                  />
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[9px] bg-indigo-tint text-indigo">
                    <FileText className="h-[18px] w-[18px]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-bold text-ink-800">{item.fileName}</p>
                    <p className="mt-0.5 text-[11px] text-ink-400">
                      {item.size != null ? formatFileSize(item.size) : 'Importado previamente'}
                    </p>
                    {item.error ? (
                      <p className="mt-1.5 text-[11.5px] font-semibold text-danger">{item.error}</p>
                    ) : null}
                  </div>
                  <span
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10.5px] font-extrabold',
                      itemTone(item.status)
                    )}
                  >
                    {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                    {item.status === 'approved' ? <Check className="h-3 w-3" /> : null}
                    {STATUS_LABELS[item.status]}
                  </span>
                  {item.status === 'queued' ? (
                    <button
                      type="button"
                      onClick={() =>
                        setItems((current) => current.filter((candidate) => candidate.id !== item.id))
                      }
                      className="mt-1 rounded-md p-1 text-ink-300 hover:bg-surface-hover hover:text-danger"
                      aria-label={`Quitar ${item.fileName}`}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  ) : null}
                </div>
              )
            })}
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2.5 border-t border-line px-5 py-4">
            {queuedCount > 0 ? (
              <button
                type="button"
                disabled={running || !folderId}
                onClick={() => void importQueued()}
                className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white disabled:opacity-50"
              >
                <Upload className="h-4 w-4" />
                Importar {queuedCount}
              </button>
            ) : null}
            {selectedDrafts > 0 ? (
              <button
                type="button"
                disabled={running}
                onClick={() => void sendSelectedForApproval()}
                className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-indigo px-4 text-[13px] font-bold text-white disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                Enviar a aprobación ({selectedDrafts})
              </button>
            ) : null}
            {selectedPending > 0 ? (
              <button
                type="button"
                disabled={running}
                onClick={() => void approveSelected()}
                className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-green px-4 text-[13px] font-bold text-white disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                Aprobar seleccionados ({selectedPending})
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      {pendingAsync.status === 'loading' && folderId ? (
        <div className="mt-4 flex items-center gap-2 text-[12px] text-ink-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Buscando importaciones pendientes…
        </div>
      ) : null}

      {(pageError || pendingAsync.error) ? (
        <div className="mt-4 rounded-[11px] border border-danger-bd bg-danger-bg px-4 py-3 text-[12.5px] font-semibold text-danger">
          {pageError || pendingAsync.error}
        </div>
      ) : null}

      <div className="mt-5 flex items-start gap-2.5 rounded-[12px] border border-amber-border bg-amber-bg px-4 py-3 text-[12.5px] leading-relaxed text-[#7A5600]">
        <AlertTriangle className="mt-0.5 h-[18px] w-[18px] shrink-0" />
        <div>
          <p className="font-extrabold">Importado no significa aprobado.</p>
          <p>Tyto no usará estos documentos hasta que sean aprobados.</p>
          <p className="mt-1 text-[11.5px]">
            Quien importó una versión no puede aprobarla: debe hacerlo otro usuario autorizado.
          </p>
        </div>
      </div>
    </main>
  )
}
