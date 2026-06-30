'use client'

/**
 * /documents/new — Nuevo documento con IA
 * Flujo de 3 fases: input → generating → review
 * Cableado a createProcessRun (formData) → document_id → submitVersionForReview
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Mic, Video, FileText, Image as ImageIcon, Radio,
  ArrowLeft, Sparkles, Send, X, Trash2, Music,
} from 'lucide-react'
import { Button } from '@/shared/ui/components'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserId } from '@/hooks/useUserId'
import {
  createProcessRun,
  getDocument,
  getDocumentVersions,
  submitVersionForReview,
  getVersionPreviewPdfUrl,
  type DocumentVersion,
  type Document,
} from '@/lib/api'
import FolderTree from '@/components/processes/FolderTree'
import DocumentTypeSelector from '@/components/processes/DocumentTypeSelector'
import { FileItemData } from '@/components/processes/FileItem'
import { type FileType } from '@/lib/fileUploadValidation'
import { formatFileSize } from '@/lib/fileUploadValidation'

// ---- Tipos ----------------------------------------------------------------

type Phase = 'input' | 'generating' | 'review'

type DetailLevel = 'breve' | 'estandar' | 'detallado'
const DETAIL_LABELS: Record<DetailLevel, string> = {
  breve:    'Conciso',
  estandar: 'Equilibrado',
  detallado:'Detallado',
}

// ---- Helpers de grabación ------------------------------------------------

function getPreferredAudioMime(): { mime: string; ext: string } {
  if (typeof window === 'undefined') return { mime: 'audio/webm', ext: '.webm' }
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  const mime = candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? 'audio/webm'
  const ext = mime.startsWith('audio/ogg') ? '.ogg' : '.webm'
  return { mime, ext }
}

function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
}

// ---- Icono SVG inline (feather-style) ------------------------------------

function SvgIcon({
  d,
  size = 16,
  className = '',
  strokeWidth = 2,
}: {
  d: string
  size?: number
  className?: string
  strokeWidth?: number
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {d.split('M').filter(Boolean).map((seg, i) => (
        <path key={i} d={'M' + seg} />
      ))}
    </svg>
  )
}

// ---- Componente de grabación inline --------------------------------------

interface RecorderPanelProps {
  onAdd: (file: File) => void
}

function RecorderPanel({ onAdd }: RecorderPanelProps) {
  const [state, setState] = useState<'idle' | 'recording' | 'done'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    if (state !== 'recording') return
    setElapsed(0)
    const id = setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [state])

  useEffect(() => {
    if (blob) {
      const url = URL.createObjectURL(blob)
      setBlobUrl(url)
      return () => URL.revokeObjectURL(url)
    }
    setBlobUrl(null)
    return undefined
  }, [blob])

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const start = useCallback(async () => {
    setError(null)
    setBlob(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const { mime } = getPreferredAudioMime()
      const rec = new MediaRecorder(stream, { mimeType: mime })
      recorderRef.current = rec
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = () => {
        if (chunksRef.current.length > 0) setBlob(new Blob(chunksRef.current, { type: mime }))
        stopStream()
        setState('done')
      }
      rec.start()
      setState('recording')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'No se pudo acceder al micrófono'
      // Friendly messages for common errors
      if (msg.includes('Permission denied') || msg.includes('NotAllowed')) {
        setError('Permiso de micrófono denegado. Habilitá el acceso en la configuración del navegador.')
      } else if (msg.includes('NotFound') || msg.includes('Requested device not found')) {
        setError('No se encontró un micrófono. Conectá uno e intentá de nuevo.')
      } else if (!MediaRecorder) {
        setError('Tu navegador no soporta grabación de audio. Usá Chrome, Edge o Firefox actualizados.')
      } else {
        setError(msg)
      }
    }
  }, [stopStream])

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }, [])

  const confirm = useCallback(() => {
    if (!blob) return
    const { ext } = getPreferredAudioMime()
    const file = new File([blob], `grabacion-${Date.now()}${ext}`, { type: blob.type })
    onAdd(file)
    setBlob(null)
    setState('idle')
  }, [blob, onAdd])

  const discard = useCallback(() => {
    setBlob(null)
    setState('idle')
    stopStream()
  }, [stopStream])

  return (
    <div className="rounded-[12px] border border-line bg-surface p-4">
      {error && (
        <p className="mb-3 text-[12px] text-danger" role="alert">{error}</p>
      )}

      {state === 'idle' && !blob && (
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <span className="grid h-10 w-10 place-items-center rounded-[10px] bg-indigo-tint text-indigo">
            <Mic size={18} aria-hidden="true" />
          </span>
          <p className="text-[12.5px] text-ink-500">
            Grabá audio directo desde el navegador.<br />Se agregará como evidencia de audio.
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={start}
            className="gap-2"
          >
            <span className="h-2.5 w-2.5 rounded-full bg-danger" aria-hidden="true" />
            Iniciar grabación
          </Button>
        </div>
      )}

      {state === 'recording' && (
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <span className="grid h-10 w-10 place-items-center rounded-[10px] bg-danger-bg text-danger">
            <span className="h-4 w-4 animate-pulse rounded-full bg-danger" aria-label="Grabando" />
          </span>
          <p className="font-bold text-ink-900">Grabando…&nbsp;
            <span className="font-mono text-ink-700">{fmtTime(elapsed)}</span>
          </p>
          <Button type="button" size="sm" onClick={stop}>
            Detener
          </Button>
        </div>
      )}

      {state === 'done' && blob && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 rounded-[10px] border border-line bg-surface px-3 py-2.5">
            <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-indigo-tint text-indigo">
              <Music size={16} aria-hidden="true" />
            </span>
            <div className="flex-1">
              <p className="text-[12.5px] font-bold text-ink-900">Grabación lista</p>
              <p className="text-[11px] text-ink-400">{formatFileSize(blob.size)}</p>
            </div>
          </div>
          {blobUrl && <audio controls src={blobUrl} className="w-full" aria-label="Previsualización de la grabación" />}
          <div className="flex gap-2">
            <Button type="button" size="sm" className="flex-1" onClick={confirm}>
              Usar grabación
            </Button>
            <Button type="button" variant="secondary" size="sm" className="flex-1" onClick={discard}>
              Descartar
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Celda del grid de evidencias ----------------------------------------

type EvidenceKind = 'audio' | 'video' | 'pdf' | 'image' | 'record'

const EVIDENCE_CELLS: { kind: EvidenceKind; label: string; fileType?: FileType; accept?: string }[] = [
  { kind: 'audio',  label: 'Audio',       fileType: 'audio', accept: '.m4a,.mp3,.wav,.ogg,.opus,.aac' },
  { kind: 'video',  label: 'Video',       fileType: 'video', accept: '.mp4,.mov,.mkv' },
  { kind: 'pdf',    label: 'PDF / Word',  fileType: 'text',  accept: '.pdf,.docx,.doc,.txt,.md' },
  { kind: 'image',  label: 'Imagen',      fileType: 'image', accept: '.png,.jpg,.jpeg,.webp' },
  { kind: 'record', label: 'Grabar ahora' },
]

function EvidenceIcon({ kind }: { kind: EvidenceKind }) {
  switch (kind) {
    case 'audio':  return <Mic size={18} aria-hidden="true" />
    case 'video':  return <Video size={18} aria-hidden="true" />
    case 'pdf':    return <FileText size={18} aria-hidden="true" />
    case 'image':  return <ImageIcon size={18} aria-hidden="true" />
    case 'record': return <Radio size={18} aria-hidden="true" />
  }
}

// ---- Ítem de archivo adjunto (compacto) -----------------------------------

function AttachedFile({ item, onRemove }: { item: FileItemData; onRemove: (id: string) => void }) {
  const icons: Record<FileType, React.ReactNode> = {
    audio: <Music size={14} aria-hidden="true" />,
    video: <Video size={14} aria-hidden="true" />,
    text:  <FileText size={14} aria-hidden="true" />,
    image: <ImageIcon size={14} aria-hidden="true" />,
  }
  return (
    <div className="flex items-center gap-2 rounded-[9px] border border-line bg-surface px-3 py-2">
      <span className="text-ink-400">{icons[item.type]}</span>
      <span className="min-w-0 flex-1 truncate text-[12px] font-semibold text-ink-800" title={item.file.name}>
        {item.file.name}
      </span>
      <span className="flex-shrink-0 text-[11px] text-ink-400">{formatFileSize(item.file.size)}</span>
      <button
        type="button"
        onClick={() => onRemove(item.id)}
        className="flex-shrink-0 rounded p-0.5 text-ink-400 hover:text-danger focus-visible:ring-2 focus-visible:ring-danger"
        aria-label={`Quitar ${item.file.name}`}
      >
        <X size={13} aria-hidden="true" />
      </button>
    </div>
  )
}

// ---- Skeleton del borrador generado --------------------------------------

function DraftSkeleton() {
  return (
    <div className="mt-6 animate-pulse space-y-4 rounded-[14px] border border-line bg-surface p-7 shadow-card">
      <div className="h-6 w-24 rounded-pill bg-ink-100" />
      <div className="h-6 w-2/3 rounded bg-ink-100" />
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-ink-100" />
        <div className="h-4 w-5/6 rounded bg-ink-100" />
        <div className="h-4 w-4/6 rounded bg-ink-100" />
      </div>
      <div className="h-4 w-1/3 rounded bg-ink-100" />
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-ink-100" />
        <div className="h-4 w-3/4 rounded bg-ink-100" />
      </div>
    </div>
  )
}

// ---- Pantalla principal --------------------------------------------------

export default function NewDocumentPage() {
  const router = useRouter()
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const userId = useUserId()

  // ---- Estado del formulario ----
  const [title, setTitle] = useState('')
  const [folderId, setFolderId] = useState('')
  const [documentType, setDocumentType] = useState('procedimiento')
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('estandar')
  // TODO(arquitectura): tytoEnabled no tiene efecto en backend aún.
  // Cuando se implemente, enviar como campo al createProcessRun o al documento.
  const [tytoEnabled, setTytoEnabled] = useState(true)
  const [files, setFiles] = useState<FileItemData[]>([])
  const [showRecorder, setShowRecorder] = useState(false)

  // ---- Estado de fases ----
  const [phase, setPhase] = useState<Phase>('input')
  const [error, setError] = useState<string | null>(null)

  // ---- Estado de la fase review ----
  const [reviewDoc, setReviewDoc] = useState<Document | null>(null)
  const [reviewVersion, setReviewVersion] = useState<DocumentVersion | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // ---- Refs para file inputs ----
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  // ---- Handlers de archivos ----

  const addFile = useCallback((file: File, type: FileType) => {
    const item: FileItemData = {
      id: `${Date.now()}-${Math.random()}`,
      file,
      type,
      description: '',
    }
    setFiles((prev) => [...prev, item])
    setShowRecorder(false)
  }, [])

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const handleCellClick = (cell: typeof EVIDENCE_CELLS[number]) => {
    if (cell.kind === 'record') {
      setShowRecorder((v) => !v)
      return
    }
    const ref = fileInputRefs.current[cell.kind]
    ref?.click()
  }

  const handleFileInputChange = (
    e: React.ChangeEvent<HTMLInputElement>,
    fileType: FileType
  ) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) addFile(selectedFile, fileType)
    // Reset input para permitir seleccionar el mismo archivo de nuevo
    e.target.value = ''
  }

  // ---- Generar borrador ----

  const handleGenerate = async () => {
    if (!title.trim() || !folderId || !selectedWorkspaceId) return

    setError(null)
    setPhase('generating')

    try {
      const formData = new FormData()
      formData.append('process_name', title.trim())
      formData.append('mode', 'operativo')
      formData.append('folder_id', folderId)
      formData.append('document_type', documentType)
      formData.append('detail_level', detailLevel)

      files.forEach((f) => {
        // video → video_files, image → image_files, text → text_files, audio → audio_files
        const fieldName = `${f.type}_files`
        formData.append(fieldName, f.file)
      })

      const result = await createProcessRun(formData)

      if (!result.document_id) {
        throw new Error('La generación no devolvió un documento. Intentá de nuevo.')
      }

      // Cargar el documento y su versión DRAFT
      setReviewLoading(true)
      const [doc, versions] = await Promise.all([
        getDocument(result.document_id),
        getDocumentVersions(result.document_id),
      ])
      setReviewDoc(doc)
      const draft = versions.find((v) => v.version_status === 'DRAFT') ?? versions[0] ?? null
      setReviewVersion(draft)
      setReviewLoading(false)
      setPhase('review')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setPhase('input')
    }
  }

  // ---- Enviar a aprobación ----

  const handleSubmitForReview = async () => {
    if (!reviewDoc || !reviewVersion) return
    setSubmitError(null)
    setSubmitting(true)
    try {
      await submitVersionForReview(
        reviewDoc.id,
        reviewVersion.id,
        userId ?? undefined,
        selectedWorkspaceId ?? undefined,
      )
      router.push(`/documents/${reviewDoc.id}`)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Error al enviar a aprobación')
      setSubmitting(false)
    }
  }

  // ---- Validaciones de habilitación del botón generar ----
  const canGenerate = Boolean(title.trim() && folderId && selectedWorkspaceId)

  // ---- Render ----

  return (
    <div data-module="process" className="min-h-full">
      <div className="mx-auto max-w-[760px] px-6 pb-[60px] pt-8">

        {/* ============================================================
            FASE: input
        ============================================================ */}
        {phase === 'input' && (
          <div className="animate-in">
            <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">
              Paso 1 · Nuevo documento
            </div>
            <h1 className="text-[25px] font-extrabold text-ink-900">
              Creá conocimiento desde evidencias
            </h1>
            <p className="mt-1.5 text-[13px] text-ink-400">
              Sumá evidencias y la IA redacta un borrador estructurado. Vos revisás y decidís antes de enviarlo a aprobación.
            </p>

            {/* Sin workspace */}
            {!selectedWorkspaceId && (
              <div className="mt-6 rounded-[12px] border border-warning-bd bg-warning-bg px-4 py-3">
                <p className="text-[13px] text-ink-700">
                  Seleccioná un espacio de trabajo en el encabezado para continuar.
                </p>
              </div>
            )}

            {/* ---- Título ---- */}
            <div className="mt-6 rounded-[14px] border border-line bg-surface p-5 shadow-card">
              <label htmlFor="doc-title" className="mb-1.5 block text-[13px] font-bold text-ink-900">
                Título del documento <span className="text-danger">*</span>
              </label>
              <input
                id="doc-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ej: Cierre de caja diario"
                className="h-[46px] w-full rounded-[10px] border border-line-input px-3.5 text-sm font-semibold text-ink-900 outline-none placeholder:font-normal placeholder:text-ink-400 focus:border-indigo focus:ring-[3px] focus:ring-indigo-tint"
                aria-required="true"
                disabled={!selectedWorkspaceId}
              />
            </div>

            {/* ---- Carpeta + Tipo de documento ---- */}
            {selectedWorkspaceId && (
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Carpeta */}
                <div className="rounded-[14px] border border-line bg-surface p-5 shadow-card">
                  <div className="mb-2">
                    <label className="text-[13px] font-bold text-ink-900">
                      Carpeta <span className="text-danger">*</span>
                    </label>
                    {!folderId && title && (
                      <p className="mt-0.5 text-[11px] text-danger">Seleccioná una carpeta para continuar</p>
                    )}
                  </div>
                  <FolderTree
                    workspaceId={selectedWorkspaceId}
                    selectedFolderId={folderId}
                    onSelectFolder={(id) => setFolderId(id ?? '')}
                    showSelectable={true}
                    showCrud={false}
                    showDocuments={false}
                  />
                </div>

                {/* Tipo de documento */}
                <div className="rounded-[14px] border border-line bg-surface p-5 shadow-card">
                  <DocumentTypeSelector
                    value={documentType}
                    onChange={setDocumentType}
                    label="Tipo de documento"
                  />
                </div>
              </div>
            )}

            {/* ---- Evidencias ---- */}
            <div className="mb-2 mt-[18px] text-[13px] font-bold text-ink-900">Evidencias</div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {EVIDENCE_CELLS.map((cell) => {
                const isRecordActive = cell.kind === 'record' && showRecorder
                return (
                  <button
                    key={cell.kind}
                    type="button"
                    onClick={() => handleCellClick(cell)}
                    className={
                      'flex flex-col items-center gap-2 rounded-[12px] border bg-surface px-2 py-4 transition-colors ' +
                      (isRecordActive
                        ? 'border-indigo bg-indigo-tint'
                        : 'border-line hover:border-indigo-light')
                    }
                    aria-pressed={isRecordActive}
                    aria-label={cell.label}
                  >
                    <span
                      className={
                        'grid h-9 w-9 place-items-center rounded-[10px] ' +
                        (isRecordActive
                          ? 'bg-indigo text-white'
                          : 'bg-indigo-tint text-indigo')
                      }
                    >
                      <EvidenceIcon kind={cell.kind} />
                    </span>
                    <span className="text-[11.5px] font-bold text-ink-700">{cell.label}</span>
                  </button>
                )
              })}

              {/* File inputs ocultos (no para 'record') */}
              {EVIDENCE_CELLS.filter((c) => c.kind !== 'record').map((cell) => (
                <input
                  key={`input-${cell.kind}`}
                  ref={(el) => { fileInputRefs.current[cell.kind] = el }}
                  type="file"
                  accept={cell.accept}
                  className="sr-only"
                  aria-hidden="true"
                  tabIndex={-1}
                  onChange={(e) => handleFileInputChange(e, cell.fileType!)}
                />
              ))}
            </div>

            {/* Panel de grabación */}
            {showRecorder && (
              <div className="mt-3">
                <RecorderPanel onAdd={(file) => addFile(file, 'audio')} />
              </div>
            )}

            {/* Lista de archivos adjuntos */}
            {files.length > 0 && (
              <div className="mt-3 flex flex-col gap-1.5">
                {files.map((f) => (
                  <AttachedFile key={f.id} item={f} onRemove={removeFile} />
                ))}
              </div>
            )}

            {/* ---- Opciones avanzadas ---- */}
            <details className="mt-[18px] rounded-[14px] border border-line bg-surface p-5 shadow-card">
              <summary className="cursor-pointer select-none text-[13px] font-bold text-ink-900 marker:content-none">
                Opciones avanzadas
              </summary>

              <div className="mt-4 flex flex-col gap-4">
                {/* Nivel de detalle */}
                <div>
                  <div className="mb-2 text-[12.5px] font-bold text-ink-700">Nivel de detalle</div>
                  <div
                    role="radiogroup"
                    aria-label="Nivel de detalle"
                    className="inline-flex items-center gap-0.5 rounded-lg bg-surface-track p-0.5"
                  >
                    {(Object.keys(DETAIL_LABELS) as DetailLevel[]).map((level) => (
                      <button
                        key={level}
                        type="button"
                        role="radio"
                        aria-checked={detailLevel === level}
                        onClick={() => setDetailLevel(level)}
                        className={
                          'rounded-md px-3.5 py-1.5 text-[12.5px] font-bold transition-colors ' +
                          (detailLevel === level
                            ? 'bg-surface text-ink-800 shadow-card'
                            : 'text-ink-400 hover:text-ink-700')
                        }
                      >
                        {DETAIL_LABELS[level]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Toggle Tyto */}
                {/* TODO(arquitectura): tytoEnabled no tiene efecto en backend aún.
                    Cuando se implemente, enviarlo como setting al crear el documento. */}
                <div className="flex items-center justify-between rounded-[12px] border border-line bg-surface px-4 py-3">
                  <div>
                    <div className="text-[13px] font-bold text-ink-900">
                      Disponible para consultas inteligentes
                    </div>
                    <div className="text-[12px] text-ink-400">
                      Tyto podrá usar este documento al responder.
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={tytoEnabled}
                    onClick={() => setTytoEnabled((v) => !v)}
                    aria-label="Disponible para consultas inteligentes"
                    className={
                      'relative h-[26px] w-[46px] flex-shrink-0 rounded-pill transition-colors ' +
                      (tytoEnabled ? 'bg-indigo' : 'bg-ink-300')
                    }
                  >
                    <span
                      className={
                        'absolute top-[3px] h-5 w-5 rounded-full bg-white shadow transition-all ' +
                        (tytoEnabled ? 'left-[23px]' : 'left-[3px]')
                      }
                    />
                  </button>
                </div>
              </div>
            </details>

            {/* ---- Error ---- */}
            {error && (
              <div
                role="alert"
                className="mt-4 rounded-[12px] border border-danger-bd bg-danger-bg px-4 py-3"
              >
                <p className="text-[13px] font-semibold text-danger">Error al generar</p>
                <p className="mt-0.5 text-[12.5px] text-danger">{error}</p>
              </div>
            )}

            {/* ---- CTA ---- */}
            <div className="mt-6 flex justify-end">
              <Button
                type="button"
                variant="create"
                size="lg"
                onClick={handleGenerate}
                disabled={!canGenerate}
                className="gap-2"
              >
                <Sparkles size={17} aria-hidden="true" />
                Generar borrador con IA
              </Button>
            </div>
          </div>
        )}

        {/* ============================================================
            FASE: generating
        ============================================================ */}
        {phase === 'generating' && (
          <div className="flex flex-col items-center justify-center py-32 text-center animate-in">
            <span className="mb-5 grid h-16 w-16 place-items-center rounded-[18px] bg-indigo text-white shadow-card">
              <SvgIcon
                d="M21 12a9 9 0 1 1-6.2-8.5"
                size={32}
                className="animate-spin"
                strokeWidth={2.4}
              />
            </span>
            <div className="text-lg font-extrabold text-ink-900">Redactando el borrador…</div>
            <div className="mt-1.5 text-[13px] text-ink-400">
              La IA estructura las evidencias en un documento. Vos lo revisás antes de continuar.
            </div>
          </div>
        )}

        {/* ============================================================
            FASE: review
        ============================================================ */}
        {phase === 'review' && (
          <div className="animate-in">
            <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">
              Paso 2 · Revisión del borrador
            </div>
            <h1 className="text-[25px] font-extrabold text-ink-900">Revisá lo que generó la IA</h1>
            <p className="mt-1.5 text-[13px] text-ink-400">
              Editá lo que necesites. Nada se publica: al confirmar entra al circuito de aprobación como borrador.
            </p>

            {reviewLoading ? (
              <DraftSkeleton />
            ) : reviewDoc ? (
              <div className="mt-6 rounded-[14px] border border-line bg-surface p-7 shadow-card">
                <span className="inline-flex items-center gap-1.5 rounded-pill border border-indigo-border bg-indigo-tint px-3 py-1 text-[11px] font-bold text-indigo">
                  <Sparkles size={11} aria-hidden="true" />
                  Borrador generado por IA
                </span>
                <h2 className="mt-3 text-lg font-extrabold text-ink-900">{reviewDoc.name}</h2>
                {reviewDoc.description && (
                  <p className="mt-2 text-sm leading-7 text-ink-700">{reviewDoc.description}</p>
                )}
                {reviewVersion && (
                  <div className="mt-4 rounded-[10px] border border-line bg-surface-app px-4 py-3">
                    <div className="flex items-center justify-between">
                      <div className="text-[12px] text-ink-500">
                        Versión DRAFT generada
                      </div>
                      {reviewDoc && reviewVersion && (
                        <a
                          href={getVersionPreviewPdfUrl(reviewDoc.id, reviewVersion.id)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-[12px] font-bold text-indigo hover:underline"
                        >
                          <FileText size={13} aria-hidden="true" />
                          Ver PDF completo
                        </a>
                      )}
                    </div>
                    <div className="mt-1.5 text-[11px] text-ink-400">
                      Estado: {reviewVersion.version_status} · Tipo: {reviewDoc.document_type}
                    </div>
                  </div>
                )}
                <p className="mt-4 text-[12.5px] text-ink-500">
                  Podés abrir el documento completo para editarlo antes de enviarlo a aprobación.
                </p>
              </div>
            ) : (
              <div className="mt-6 rounded-[14px] border border-danger-bd bg-danger-bg px-4 py-4">
                <p className="text-[13px] text-danger">
                  No se pudo cargar el borrador. Podés ir directamente al documento generado.
                </p>
              </div>
            )}

            {/* Error de submit */}
            {submitError && (
              <div role="alert" className="mt-4 rounded-[12px] border border-danger-bd bg-danger-bg px-4 py-3">
                <p className="text-[13px] text-danger">{submitError}</p>
              </div>
            )}

            {/* Acciones */}
            <div className="mt-6 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => { setPhase('input'); setSubmitError(null) }}
                className="inline-flex h-[46px] items-center gap-1.5 rounded-[11px] border border-line bg-surface px-[18px] text-[13.5px] font-bold text-ink-500 transition-colors hover:bg-surface-hover focus-visible:ring-2 focus-visible:ring-action-ring"
              >
                <ArrowLeft size={16} aria-hidden="true" />
                Volver a editar
              </button>
              <Button
                type="button"
                variant="create"
                size="lg"
                onClick={handleSubmitForReview}
                disabled={submitting || !reviewDoc || !reviewVersion}
                className="gap-2"
              >
                <Send size={16} aria-hidden="true" />
                {submitting ? 'Enviando…' : 'Enviar a aprobación'}
              </Button>
            </div>

            {/* Atajo: abrir el documento generado */}
            {reviewDoc && (
              <div className="mt-4 text-center">
                <a
                  href={`/documents/${reviewDoc.id}`}
                  className="text-[12px] text-indigo hover:underline"
                >
                  Abrir el documento completo para editar
                </a>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
