/**
 * Tipos y datos demo del wizard "Nuevo documento".
 * Replace API calls in production — ver TODO(wire) en NuevoDocumentoWizard.
 */

// ---- Evidence types ----

export type EvidenceTipo = "Audio" | "Video" | "PDF" | "Imagen" | "Documento";

export interface EvidenceTypeDef {
  tipo: EvidenceTipo;
  /** Extensiones aceptadas, mostradas como ayuda */
  formats: string;
  /** Nombre de archivo demo (usado al "seleccionar" en el modal) */
  sample: string;
  /** Chips resultado una vez procesada la evidencia */
  chips: string[];
  /** Descripción de una línea */
  help: string;
  /** Placeholder del campo descripción */
  placeholder: string;
  /** Etiquetas del pipeline de procesamiento (última = "Listo") */
  steps: string[];
}

export const EVIDENCE_TYPES: Record<EvidenceTipo, EvidenceTypeDef> = {
  Audio: {
    tipo: "Audio",
    formats: ".m4a, .mp3, .wav, .ogg, .opus, .aac",
    sample: "grabacion-cajero.m4a",
    chips: ["Audio transcripto", "Idioma: ES", "0:48"],
    help: "Reuniones, entrevistas o notas de voz",
    placeholder: "Ej: Entrevista al cajero",
    steps: ["Audio guardado", "Transcribiendo…", "Detectando idioma…", "Listo"],
  },
  Video: {
    tipo: "Video",
    formats: ".mp4, .mov, .webm",
    sample: "video-cierre.mp4",
    chips: ["Audio transcripto", "Idioma: ES", "2:40"],
    help: "Grabaciones de pantalla o del proceso",
    placeholder: "Ej: Cierre filmado en caja",
    steps: ["Video guardado", "Transcribiendo audio…", "Detectando idioma…", "Listo"],
  },
  PDF: {
    tipo: "PDF",
    formats: ".pdf",
    sample: "documento.pdf",
    chips: ["Texto extraído", "PDF procesado", "8 págs"],
    help: "Manuales, instructivos o políticas",
    placeholder: "Ej: Manual operativo 2023",
    steps: ["PDF guardado", "Extrayendo texto…", "Procesando páginas…", "Listo"],
  },
  Imagen: {
    tipo: "Imagen",
    formats: ".jpg, .png, .webp, .heic",
    sample: "foto-caja.jpg",
    chips: ["OCR completado", "1 imagen"],
    help: "Fotos, capturas o planillas escaneadas",
    placeholder: "Ej: Foto de la planilla",
    steps: ["Imagen guardada", "OCR en proceso…", "Detectando texto…", "Listo"],
  },
  Documento: {
    tipo: "Documento",
    formats: ".doc, .docx, .txt, .md",
    sample: "notas-proceso.docx",
    chips: ["Texto extraído", "Idioma: ES"],
    help: "Word, texto o notas",
    placeholder: "Ej: Notas del proceso",
    steps: ["Documento guardado", "Extrayendo texto…", "Detectando idioma…", "Listo"],
  },
};

export interface Evidence {
  id: string;
  tipo: EvidenceTipo;
  title: string;
  /** true mientras corre el pipeline demo; luego false */
  processing: boolean;
  /** Chips resultado (se muestran cuando !processing) */
  chips: string[];
}

// TODO(wire): reemplazar con evidencias reales del tenant/documento en curso
export const INITIAL_EVIDENCE: Evidence[] = [
  {
    id: "entrevista",
    tipo: "Audio",
    title: "Entrevista al cajero",
    processing: false,
    chips: ["Audio transcripto", "Idioma: ES", "1:32"],
  },
  {
    id: "manual",
    tipo: "PDF",
    title: "Manual operativo 2023",
    processing: false,
    chips: ["Texto extraído", "PDF procesado", "42 págs"],
  },
  {
    id: "fotos",
    tipo: "Imagen",
    title: "Planilla + POS (fotos)",
    processing: false,
    chips: ["OCR completado", "3 imágenes"],
  },
];

// TODO(wire): reemplazar con árbol de carpetas real del workspace
export const FOLDERS: string[] = [
  "Procesos / Caja",
  "Procesos / Turnos",
  "RRHH / Liquidación de Sueldos",
  "Contabilidad / Cierres mensuales",
];

export const CONTEXT_EXAMPLES: string[] = [
  "Es un reemplazo del procedimiento anterior",
  "Aplica solo al turno noche",
  "Incluye el manejo del fondo fijo",
];

export const DETAIL_LEVELS = [
  { value: "", label: "Automático (recomendado)" },
  { value: "Básico", label: "Básico — pasos esenciales" },
  { value: "Estándar", label: "Estándar — equilibrado" },
  { value: "Detallado", label: "Detallado — con excepciones" },
];

export interface Approver {
  id: string;
  name: string;
  role: string;
  initials: string;
  sel: boolean;
}

// TODO(wire): reemplazar con aprobadores reales de la carpeta destino (governance config)
export const APPROVERS: Approver[] = [
  { id: "lucia", name: "Lucía Gómez", role: "Gerente", initials: "LG", sel: true },
  { id: "juan", name: "Juan Pérez", role: "Supervisor de turno", initials: "JP", sel: true },
  { id: "pablo", name: "Pablo Rodríguez", role: "Dueño", initials: "PR", sel: false },
];

/** Etiquetas del pipeline de generación del overlay */
export const GEN_STEPS: string[] = [
  "Procesando evidencias",
  "Transcribiendo audio",
  "Analizando documentos",
  "Organizando secciones",
  "Generando borrador",
];

/** Devuelve el path SVG del icono por tipo de evidencia */
export function evidenceIconPath(tipo: EvidenceTipo): string {
  const map: Record<EvidenceTipo, string> = {
    Audio:
      "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4",
    Video:
      "M23 7l-7 5 7 5V7zM3 5h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
    PDF: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
    Imagen: "M3 3h18v18H3zM8.5 11l2.5 3 3.5-4.5L21 17",
    Documento:
      "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h4",
  };
  return map[tipo];
}

/** Formatea segundos a "m:ss" */
export function formatSecs(n: number): string {
  const m = Math.floor(n / 60);
  const s = n % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
