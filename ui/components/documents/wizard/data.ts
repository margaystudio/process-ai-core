/**
 * Tipos y datos de configuración del wizard "Nuevo documento".
 * Los datos demo de INITIAL_EVIDENCE fueron eliminados — las evidencias arrancan vacías.
 */

import type { FileType } from '@/lib/fileUploadValidation'

// ---- Tipos de evidencia ----

export type EvidenceTipo = 'Audio' | 'Video' | 'PDF' | 'Imagen' | 'Documento'

/** Mapeo de tipo de evidencia del wizard al FileType del sistema */
export const EVIDENCE_TIPO_TO_FILE_TYPE: Record<EvidenceTipo, FileType> = {
  Audio:     'audio',
  Video:     'video',
  PDF:       'text',
  Imagen:    'image',
  Documento: 'text',
}

/** Mapeo de FileType al campo del FormData que espera el backend */
export const FILE_TYPE_TO_FORM_FIELD: Record<FileType, string> = {
  audio: 'audio_files',
  video: 'video_files',
  image: 'image_files',
  text:  'text_files',
}

export interface EvidenceTypeDef {
  tipo: EvidenceTipo
  /** Extensiones aceptadas para el <input type="file"> */
  accept: string
  /** Etiqueta de ayuda */
  help: string
  /** Placeholder del campo descripción */
  placeholder: string
  /** FileType del sistema */
  fileType: FileType
}

export const EVIDENCE_TYPES: Record<EvidenceTipo, EvidenceTypeDef> = {
  Audio: {
    tipo: 'Audio',
    accept: '.m4a,.mp3,.wav,.ogg,.opus,.aac',
    help: 'Reuniones, entrevistas o notas de voz',
    placeholder: 'Ej: Entrevista al cajero',
    fileType: 'audio',
  },
  Video: {
    tipo: 'Video',
    accept: '.mp4,.mov,.webm',
    help: 'Grabaciones de pantalla o del proceso',
    placeholder: 'Ej: Cierre filmado en caja',
    fileType: 'video',
  },
  PDF: {
    tipo: 'PDF',
    accept: '.pdf,.doc,.docx',
    help: 'Manuales, instructivos o políticas',
    placeholder: 'Ej: Manual operativo 2023',
    fileType: 'text',
  },
  Imagen: {
    tipo: 'Imagen',
    accept: '.jpg,.jpeg,.png,.webp,.heic',
    help: 'Fotos, capturas o planillas escaneadas',
    placeholder: 'Ej: Foto de la planilla',
    fileType: 'image',
  },
  Documento: {
    tipo: 'Documento',
    accept: '.doc,.docx,.txt,.md',
    help: 'Word, texto o notas',
    placeholder: 'Ej: Notas del proceso',
    fileType: 'text',
  },
}

/**
 * Una evidencia es un archivo real aportado por el usuario.
 * No hay estado de procesamiento en el frontend — el procesamiento ocurre en el backend
 * al momento de llamar a createProcessRun.
 */
export interface Evidence {
  /** ID único local */
  id: string
  tipo: EvidenceTipo
  /** FileType del sistema (para el FormData del backend) */
  fileType: FileType
  /** Nombre para mostrar (descripción del usuario o nombre del archivo) */
  title: string
  /** Archivo real — se agrega al FormData al generar */
  file: File
}

// ---- Aprobadores (demo hasta cablear Step 3) ----

export interface Approver {
  id: string
  name: string
  role: string
  initials: string
  sel: boolean
}

/** TODO(wire): reemplazar con aprobadores reales de la governance config de la carpeta destino */
export const APPROVERS: Approver[] = [
  { id: 'lucia', name: 'Lucía Gómez',      role: 'Gerente',              initials: 'LG', sel: true  },
  { id: 'juan',  name: 'Juan Pérez',        role: 'Supervisor de turno',  initials: 'JP', sel: true  },
  { id: 'pablo', name: 'Pablo Rodríguez',   role: 'Dueño',                initials: 'PR', sel: false },
]

export const CONTEXT_EXAMPLES: string[] = [
  'Es un reemplazo del procedimiento anterior',
  'Aplica solo al turno noche',
  'Incluye el manejo del fondo fijo',
]

export const DETAIL_LEVELS = [
  { value: '',          label: 'Automático (recomendado)' },
  { value: 'breve',     label: 'Conciso — pasos esenciales' },
  { value: 'estandar',  label: 'Equilibrado' },
  { value: 'detallado', label: 'Detallado — con excepciones' },
]

// ---- Etiquetas del pipeline de generación (overlay) ----

export const GEN_STEPS: string[] = [
  'Procesando evidencias',
  'Transcribiendo audio',
  'Analizando documentos',
  'Organizando secciones',
  'Generando borrador',
]

// ---- Paths SVG de íconos por tipo ----

export function evidenceIconPath(tipo: EvidenceTipo): string {
  const map: Record<EvidenceTipo, string> = {
    Audio:
      'M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4',
    Video:
      'M23 7l-7 5 7 5V7zM3 5h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z',
    PDF: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6',
    Imagen: 'M3 3h18v18H3zM8.5 11l2.5 3 3.5-4.5L21 17',
    Documento:
      'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h4',
  }
  return map[tipo]
}

/** Formatea bytes en KB / MB */
export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024).toFixed(1)} KB`
}

/** Formatea segundos a "m:ss" */
export function formatSecs(n: number): string {
  const m = Math.floor(n / 60)
  const s = n % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

/** Negocia el mejor mimetype para MediaRecorder */
export function getPreferredAudioMime(): { mime: string; ext: string } {
  if (typeof window === 'undefined') return { mime: 'audio/webm', ext: '.webm' }
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  const mime = candidates.find((m) => MediaRecorder.isTypeSupported(m)) ?? 'audio/webm'
  const ext = mime.startsWith('audio/ogg') ? '.ogg' : '.webm'
  return { mime, ext }
}
