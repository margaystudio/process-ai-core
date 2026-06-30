// components/StatusBadge.tsx
// Badge de estado de documento (Aprobado / Pendiente / Borrador / Archivado).
// Usa los tokens semánticos de color del design system, sin hex sueltos.
import * as React from "react";

export type DocumentEstado = "Aprobado" | "Pendiente" | "Borrador" | "Archivado";

/** Mapa de estado API → etiqueta visible */
export const ESTADO_LABEL: Record<string, DocumentEstado> = {
  approved:           "Aprobado",
  pending_validation: "Pendiente",
  draft:              "Borrador",
  rejected:           "Borrador",   // rechazado vuelve a flujo de borrador
  archived:           "Archivado",
};

interface ToneTokens {
  text: string;
  bg: string;
  border: string;
  dot: string;
}

function estadoTone(e: DocumentEstado): ToneTokens {
  switch (e) {
    case "Aprobado":
      return {
        text: "var(--success-fg)",
        bg: "var(--success-bg)",
        border: "var(--success-bd)",
        dot: "var(--success)",
      };
    case "Pendiente":
      return {
        text: "var(--warning)",
        bg: "var(--warning-bg)",
        border: "var(--warning-bd)",
        dot: "var(--warning)",
      };
    case "Archivado":
      return {
        text: "var(--ink-500)",
        bg: "var(--ink-100)",
        border: "var(--ink-200)",
        dot: "var(--ink-400)",
      };
    default: // Borrador
      return {
        text: "var(--info)",
        bg: "var(--info-bg)",
        border: "var(--info-bd)",
        dot: "var(--indigo-light)",
      };
  }
}

/**
 * Badge de estado de documento con punto de color.
 * Acepta tanto el estado en español del prototipo como el estado de API.
 */
export function StatusBadge({ estado }: { estado: DocumentEstado | string }) {
  // Resolver: si viene en API status, convertir; si ya es la etiqueta, usar directo
  const resolved: DocumentEstado =
    (ESTADO_LABEL[estado] as DocumentEstado | undefined) ??
    (["Aprobado", "Pendiente", "Borrador", "Archivado"].includes(estado)
      ? (estado as DocumentEstado)
      : "Borrador");

  const t = estadoTone(resolved);
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-pill border px-3 py-[5px] text-[11.5px] font-extrabold"
      style={{ color: t.text, background: t.bg, borderColor: t.border }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: t.dot }}
        aria-hidden="true"
      />
      {resolved}
    </span>
  );
}

/** Etiqueta de versión inline — fondo con tono del estado. */
export function VersionPill({
  estado,
  label,
}: {
  estado: DocumentEstado | string;
  label: string;
}) {
  const resolved: DocumentEstado =
    (ESTADO_LABEL[estado] as DocumentEstado | undefined) ??
    (["Aprobado", "Pendiente", "Borrador", "Archivado"].includes(estado)
      ? (estado as DocumentEstado)
      : "Borrador");
  const t = estadoTone(resolved);
  return (
    <span
      className="rounded-md px-2 py-0.5 text-[10.5px] font-bold"
      style={{ color: t.text, background: t.bg }}
    >
      {label}
    </span>
  );
}
