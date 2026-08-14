'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  FileText,
  RotateCw,
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
  getDocumentTypes,
  getDocumentVersions,
  getFolderGovernance,
  importDocuments,
  listDocuments,
  listFolders,
  submitVersionForReview,
  type Document,
  type DocumentType,
} from '@/lib/api'
import {
  EXTENSIONS_BY_TYPE,
  MAX_FILE_SIZE_BYTES,
  formatFileSize,
  getFileExtension,
} from '@/lib/fileUploadValidation'
import {
  consecuenciaImportacion,
  resolverTipoPorDefecto,
  tipoEfectivoDeFila,
  tipoRequiereAprobacion,
} from '@/lib/importDocumentType'
import { Badge, Spinner } from '@/shared/ui/components'
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
  /**
   * Tipo documental elegido puntualmente para ESTA fila. `null` = sigue el
   * default del lote (`batchDocumentType`) — ver `tipoEfectivoDeFila`. Se
   * fija recién cuando el usuario toca el selector de la fila, así un cambio
   * posterior en el default del lote no le pisa una elección explícita.
   */
  documentTypeOverride: string | null
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
  // "approved" (verde) usa los tokens semánticos success-* — `green-border` /
  // `green-bg` / `green-text` no existen en el design system (el color `green`
  // del preset solo define DEFAULT+50..700), esas clases no generaban CSS y el
  // tono quedaba invisible.
  if (status === 'approved') return 'border-success-bd bg-success-bg text-success-fg'
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
  // Resumen de la última corrida de importación (cuántos entraron / fallaron),
  // para no dejar que el usuario lo deduzca de los colores de cada fila.
  const [importSummary, setImportSummary] = useState<{ ok: number; failed: number } | null>(null)
  // Tipo documental del lote: default para toda fila que no tenga su propio
  // override. Arranca en el default duro (nunca vacío) y se corrige al
  // default efectivo de la carpeta apenas resuelve su gobierno.
  const [batchDocumentType, setBatchDocumentType] = useState(resolverTipoPorDefecto(null))

  const { canManage: canAdminister, loading: canAdministerLoading } = useCanManageWorkspace()

  const foldersAsync = useAsync(
    async () => {
      if (!selectedWorkspaceId) return []
      return listFolders(selectedWorkspaceId)
    },
    [selectedWorkspaceId]
  )

  const documentTypesAsync = useAsync(() => getDocumentTypes(false), [])
  const documentTypes: DocumentType[] = documentTypesAsync.data ?? []

  // Gobierno efectivo de la carpeta elegida: ya resuelve la herencia (si la
  // carpeta no define default_document_type, sube al ancestro más cercano),
  // así el selector precarga exactamente lo que el backend va a aplicar.
  const folderGovernanceAsync = useAsync(
    async () => {
      if (!folderId) return null
      return getFolderGovernance(folderId)
    },
    [folderId]
  )

  useEffect(() => {
    if (folderGovernanceAsync.status === 'success' || folderGovernanceAsync.status === 'error') {
      // En error no dejamos el selector vacío: mostramos el mismo default
      // "a ciegas" que aplicaría el backend si tampoco pudiera leer el gobierno.
      setBatchDocumentType(
        resolverTipoPorDefecto(folderGovernanceAsync.status === 'success' ? folderGovernanceAsync.data : null)
      )
    }
  }, [folderGovernanceAsync.status, folderGovernanceAsync.data])

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
          documentTypeOverride: null,
        }))
      return additions.length ? [...current, ...additions] : current
    })
  }, [pendingAsync.data])

  useEffect(() => {
    setItems([])
    setPageError(null)
    setImportSummary(null)
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
        // Sin override: sigue el default del lote hasta que la fila lo pise.
        documentTypeOverride: null,
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

  /**
   * Corre la importación para un lote de items ya marcados 'queued'. Único
   * punto que llama a `importDocuments` — lo usan tanto el botón principal
   * (lote completo) como "Reintentar" por fila (lote de 1), así ambos caminos
   * comparten la misma regla: solo procesa lo que está 'queued' en `targets`,
   * nunca lo que ya importó ('imported'/'pending_validation'/'approved').
   */
  const runImportForItems = useCallback(
    async (targets: ImportItem[]) => {
      if (!folderId) {
        setPageError('Elegí una carpeta destino')
        return
      }
      const runnable = targets.filter((item) => item.file && item.status === 'queued')
      if (!runnable.length) return

      setRunning(true)
      setPageError(null)
      let ok = 0
      let failed = 0
      for (const item of runnable) {
        updateItem(item.id, { status: 'importing', error: null })
        try {
          const formData = new FormData()
          formData.append('folder_id', folderId)
          // El tipo documental decide si el archivo pide aprobación o entra
          // vigente directamente (ver resolucion.py) — `requires_approval` ya
          // no existe como parámetro, se ignoraría si lo mandáramos. Se manda
          // siempre explícito, aunque coincida con el default de la carpeta,
          // para que lo que se ve en la fila sea justo lo que se aplica.
          formData.append('document_type', tipoEfectivoDeFila(item.documentTypeOverride, batchDocumentType))
          formData.append('files', item.file as File)
          const [document] = await importDocuments(formData)
          // Si el tipo no pide aprobación, el backend ya lo dejó vigente
          // ('approved') de una: no pasa por el borrador a enviar a revisión.
          const approvedDeInmediato = document.status === 'approved'
          updateItem(item.id, {
            document,
            status: approvedDeInmediato ? 'approved' : 'imported',
            selected: !approvedDeInmediato,
          })
          ok += 1
        } catch (error) {
          updateItem(item.id, {
            status: 'error',
            selected: false,
            error: error instanceof Error ? error.message : 'Error al importar',
          })
          failed += 1
        }
      }
      setRunning(false)
      setImportSummary({ ok, failed })
    },
    [folderId, batchDocumentType, updateItem]
  )

  /**
   * Botón principal: procesa 'queued' Y 'error' (antes solo 'queued', por eso
   * un archivo fallido quedaba trabado para siempre — ver bug original).
   * Nunca toca 'imported'/'pending_validation'/'approved': ese es el filtro
   * que evita volver a duplicar un documento que ya entró.
   */
  const importAll = async () => {
    if (!folderId) {
      setPageError('Elegí una carpeta destino')
      return
    }
    const targets = items.filter(
      (item) => (item.status === 'queued' || item.status === 'error') && item.file
    )
    if (!targets.length) {
      setPageError('Agregá al menos un archivo para importar')
      return
    }
    targets.forEach((item) => {
      if (item.status === 'error') updateItem(item.id, { status: 'queued', error: null })
    })
    await runImportForItems(targets.map((item) => ({ ...item, status: 'queued', error: null })))
  }

  /** Reintento individual: solo aplica a un item en 'error', conserva el File. */
  const retryItem = useCallback(
    (id: string) => {
      const item = items.find((candidate) => candidate.id === id)
      if (!item || item.status !== 'error' || !item.file) return
      updateItem(id, { status: 'queued', error: null })
      void runImportForItems([{ ...item, status: 'queued', error: null }])
    },
    [items, runImportForItems, updateItem]
  )

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
  const erroredCount = items.filter((item) => item.status === 'error').length
  const retryableCount = queuedCount + erroredCount
  // El label refleja qué va a pasar al apretar el botón: si todo lo pendiente
  // falló antes, "Reintentar N"; si hay una mezcla, se aclaran los reintentos.
  const importButtonLabel =
    erroredCount > 0 && queuedCount === 0
      ? `Reintentar ${erroredCount}`
      : erroredCount > 0
        ? `Importar ${retryableCount} (${erroredCount} reintentos)`
        : `Importar ${queuedCount}`
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
  const documentTypesLoading = documentTypesAsync.status === 'idle' || documentTypesAsync.status === 'loading'
  const governanceLoading = folderGovernanceAsync.status === 'idle' || folderGovernanceAsync.status === 'loading'

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
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
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
          </div>

          <div>
            <label
              htmlFor="import-document-type"
              className="mb-2 block text-[13px] font-bold text-ink-900"
            >
              Tipo documental (todos los archivos)
            </label>
            {documentTypesLoading || governanceLoading ? (
              <div className="h-11 animate-pulse rounded-[10px] bg-ink-100" />
            ) : documentTypesAsync.status === 'error' ? (
              <div className="flex items-center justify-between gap-2 rounded-[10px] border border-danger-bd bg-danger-bg px-3 py-2 text-[12.5px] font-semibold text-danger">
                <span>{documentTypesAsync.error}</span>
                <button
                  type="button"
                  onClick={documentTypesAsync.reload}
                  className="shrink-0 underline underline-offset-2"
                >
                  Reintentar
                </button>
              </div>
            ) : (
              <select
                id="import-document-type"
                value={batchDocumentType}
                onChange={(event) => setBatchDocumentType(event.target.value)}
                className="h-11 w-full rounded-[10px] border border-line-input bg-surface px-3.5 text-sm font-semibold text-ink-800 outline-none focus:border-indigo focus:ring-[3px] focus:ring-indigo/10"
              >
                {documentTypes.map((type) => (
                  <option key={type.key} value={type.key}>
                    {type.label}
                  </option>
                ))}
              </select>
            )}
            {!documentTypesLoading && !governanceLoading && documentTypesAsync.status !== 'error' ? (
              <p className="mt-1.5 text-[11px] text-ink-400">
                {consecuenciaImportacion(tipoRequiereAprobacion(batchDocumentType, documentTypes))}
                {' · se puede pisar archivo por archivo.'}
              </p>
            ) : null}
          </div>
        </div>
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
              // Solo se puede elegir/cambiar el tipo mientras el archivo no
              // viajó todavía: una vez importado, el tipo ya quedó resuelto
              // (y reflejado) del lado del backend.
              const typeEditable = Boolean(item.file) && (item.status === 'queued' || item.status === 'error')
              const itemDocumentType = tipoEfectivoDeFila(item.documentTypeOverride, batchDocumentType)
              const itemRequiresApproval = tipoRequiereAprobacion(itemDocumentType, documentTypes)
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
                    {typeEditable && !documentTypesLoading ? (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <label htmlFor={`document-type-${item.id}`} className="sr-only">
                          Tipo documental de {item.fileName}
                        </label>
                        <select
                          id={`document-type-${item.id}`}
                          value={itemDocumentType}
                          disabled={running || documentTypesAsync.status !== 'success'}
                          onChange={(event) =>
                            updateItem(item.id, { documentTypeOverride: event.target.value })
                          }
                          className="h-8 rounded-[8px] border border-line-input bg-surface px-2 text-[11.5px] font-semibold text-ink-700 outline-none focus:border-indigo focus:ring-[2px] focus:ring-indigo/10 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {documentTypes.map((type) => (
                            <option key={type.key} value={type.key}>
                              {type.label}
                            </option>
                          ))}
                        </select>
                        <Badge variant={itemRequiresApproval ? 'warning' : 'success'} dot={false}>
                          {consecuenciaImportacion(itemRequiresApproval)}
                        </Badge>
                      </div>
                    ) : null}
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
                    {busy ? <Spinner size="xs" /> : null}
                    {item.status === 'approved' ? <Check className="h-3 w-3" /> : null}
                    {STATUS_LABELS[item.status]}
                  </span>
                  {item.status === 'error' ? (
                    <button
                      type="button"
                      disabled={running}
                      onClick={() => retryItem(item.id)}
                      className="mt-0.5 inline-flex h-7 flex-shrink-0 items-center gap-1.5 rounded-[8px] border border-danger-bd bg-surface px-2.5 text-[11.5px] font-bold text-danger hover:bg-danger-bg disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <RotateCw className="h-3.5 w-3.5" />
                      Reintentar
                    </button>
                  ) : null}
                  {(item.status === 'queued' || item.status === 'error') ? (
                    <button
                      type="button"
                      disabled={running}
                      onClick={() =>
                        setItems((current) => current.filter((candidate) => candidate.id !== item.id))
                      }
                      className="mt-1 rounded-md p-1 text-ink-300 hover:bg-surface-hover hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
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
            {retryableCount > 0 ? (
              <button
                type="button"
                disabled={running || !folderId}
                onClick={() => void importAll()}
                className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-ink-800 px-4 text-[13px] font-bold text-white disabled:opacity-50"
              >
                <Upload className="h-4 w-4" />
                {importButtonLabel}
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

      {/* Resumen de la última corrida: cuántos entraron y cuántos fallaron,
          en vez de dejar que el usuario lo deduzca de los colores de cada fila. */}
      {importSummary && !running ? (
        <div
          role="status"
          className={cn(
            'mt-4 flex items-start justify-between gap-3 rounded-[12px] border px-4 py-3 text-[12.5px]',
            importSummary.failed > 0
              ? 'border-danger-bd bg-danger-bg text-danger'
              : 'border-success-bd bg-success-bg text-success-fg'
          )}
        >
          <div>
            <p className="font-extrabold">
              {importSummary.ok} {importSummary.ok === 1 ? 'archivo importado' : 'archivos importados'}
              {importSummary.failed > 0 ? `, ${importSummary.failed} con error` : ''}
            </p>
            {importSummary.failed > 0 ? (
              <p className="mt-0.5">
                Usá &quot;Reintentar&quot; en cada archivo, o el botón principal para reintentarlos todos.
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => setImportSummary(null)}
            className="flex-shrink-0 text-[11.5px] font-bold underline underline-offset-2 hover:no-underline"
          >
            Cerrar
          </button>
        </div>
      ) : null}

      {pendingAsync.status === 'loading' && folderId ? (
        <div className="mt-4 flex items-center gap-2 text-[12px] text-ink-400">
          <Spinner size="sm" />
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
