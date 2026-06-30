// Demo data + types for the "Nuevo documento" authoring wizard.
// Lifted from the prototype. Replace with API calls in production.
import React from "react";

// ---- evidence types (audio / video / pdf / image / document) ----
export type EvidenceTipo = "Audio" | "Video" | "PDF" | "Imagen" | "Documento";

export interface EvidenceTypeDef {
  tipo: EvidenceTipo;
  formats: string;        // accepted extensions, shown as help text
  sample: string;         // demo filename used when "selecting" a file
  chips: string[];        // result badges once processing is done (e.g. "Audio transcripto", "Idioma: ES")
  help: string;           // one-line description
  placeholder: string;    // description input placeholder
  steps: string[];        // processing pipeline labels (last one = "Listo")
}

export const EVIDENCE_TYPES: Record<EvidenceTipo, EvidenceTypeDef> = {
  Audio: { tipo: "Audio", formats: ".m4a, .mp3, .wav, .ogg, .opus, .aac", sample: "grabacion-cajero.m4a", chips: ["Audio transcripto", "Idioma: ES", "0:48"], help: "Reuniones, entrevistas o notas de voz", placeholder: "Ej: Entrevista al cajero", steps: ["Audio guardado", "Transcribiendo…", "Detectando idioma…", "Listo"] },
  Video: { tipo: "Video", formats: ".mp4, .mov, .webm", sample: "video-cierre.mp4", chips: ["Audio transcripto", "Idioma: ES", "2:40"], help: "Grabaciones de pantalla o del proceso", placeholder: "Ej: Cierre filmado en caja", steps: ["Video guardado", "Transcribiendo audio…", "Detectando idioma…", "Listo"] },
  PDF: { tipo: "PDF", formats: ".pdf", sample: "documento.pdf", chips: ["Texto extraído", "PDF procesado", "8 págs"], help: "Manuales, instructivos o políticas", placeholder: "Ej: Manual operativo 2023", steps: ["PDF guardado", "Extrayendo texto…", "Procesando páginas…", "Listo"] },
  Imagen: { tipo: "Imagen", formats: ".jpg, .png, .webp, .heic", sample: "foto-caja.jpg", chips: ["OCR completado", "1 imagen"], help: "Fotos, capturas o planillas escaneadas", placeholder: "Ej: Foto de la planilla", steps: ["Imagen guardada", "OCR en proceso…", "Detectando texto…", "Listo"] },
  Documento: { tipo: "Documento", formats: ".doc, .docx, .txt, .md", sample: "notas-proceso.docx", chips: ["Texto extraído", "Idioma: ES"], help: "Word, texto o notas", placeholder: "Ej: Notas del proceso", steps: ["Documento guardado", "Extrayendo texto…", "Detectando idioma…", "Listo"] },
};

export interface Evidence {
  id: string;
  tipo: EvidenceTipo;
  title: string;
  processing: boolean;   // true while pipeline runs, then false
  chips: string[];       // result badges (shown when !processing)
}

export const INITIAL_EVIDENCE: Evidence[] = [
  { id: "entrevista", tipo: "Audio", title: "Entrevista al cajero", processing: false, chips: ["Audio transcripto", "Idioma: ES", "1:32"] },
  { id: "manual", tipo: "PDF", title: "Manual operativo 2023", processing: false, chips: ["Texto extraído", "PDF procesado", "42 págs"] },
  { id: "fotos", tipo: "Imagen", title: "Planilla + POS (fotos)", processing: false, chips: ["OCR completado", "3 imágenes"] },
];

export const FOLDERS = [
  "Procesos / Caja",
  "Procesos / Turnos",
  "RRHH / Liquidación de Sueldos",
  "Contabilidad / Cierres mensuales",
];

export const CONTEXT_EXAMPLES = [
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

export interface Approver { id: string; name: string; role: string; initials: string; sel: boolean; }
export const APPROVERS: Approver[] = [
  { id: "lucia", name: "Lucía Gómez", role: "Gerente", initials: "LG", sel: true },
  { id: "juan", name: "Juan Pérez", role: "Supervisor de turno", initials: "JP", sel: true },
  { id: "pablo", name: "Pablo Rodríguez", role: "Dueño", initials: "PR", sel: false },
];

// Generation pipeline shown in the "redactando" full-screen state.
export const GEN_STEPS = ["Procesando evidencias", "Transcribiendo audio", "Analizando documentos", "Organizando secciones", "Generando borrador"];

// ---- icons (Feather/Lucide style) ----
export const ICONS = {
  audio: "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4",
  video: "M23 7l-7 5 7 5V7zM3 5h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
  pdf: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
  imagen: "M3 3h18v18H3zM8.5 11l2.5 3 3.5-4.5L21 17",
  documento: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h4",
  folder: "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
  plus: "M12 5v14M5 12h14",
  close: "M18 6L6 18M6 6l12 12",
  check: "M20 6L9 17l-5-5",
  chevron: "M9 18l6-6-6-6",
  upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  spark: "M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z",
  arrowR: "M5 12h14M13 6l6 6-6 6",
  redo: "M3 2v6h6M3.51 15a9 9 0 1 0 2.13-9.36L3 8",
  edit: "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z",
  info: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 16v-4M12 8h.01",
};

export function evidenceIconPath(tipo: EvidenceTipo): string {
  return { Audio: ICONS.audio, Video: ICONS.video, PDF: ICONS.pdf, Imagen: ICONS.imagen, Documento: ICONS.documento }[tipo];
}

/** Inline icon helper — swap for lucide-react if preferred. */
export function Icon({ d, size = 16, className = "", strokeWidth = 2 }: { d: string; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
      {d.split("M").filter(Boolean).map((seg, i) => <path key={i} d={"M" + seg} />)}
    </svg>
  );
}

export function formatSecs(n: number): string {
  const m = Math.floor(n / 60), s = n % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
