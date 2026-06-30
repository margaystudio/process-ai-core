// Shared types, demo data and small helpers for the Process AI screens.
// NOTE: all data here is DEMO data lifted from the prototype. Replace with API calls.

import React from "react";

export type Estado = "Aprobado" | "Pendiente" | "Borrador" | "Archivado";

export interface Doc {
  id: string;
  name: string;
  estado: Estado;
  carpeta: string; // "Procesos / Caja"
  version: string; // "v3" | "—"
  by: string;
  fecha: string;
}

export interface Folder {
  id: string;
  name: string;
  parent: string | null;
  icon: FolderIconKind;
  color: string;
  docs: number;
}

export type FolderIconKind = "flow" | "shield" | "box" | "contract" | "folder" | "chart";

// ---- estado → tono (badge tint convention) ----
export function estadoTone(e: Estado) {
  switch (e) {
    case "Aprobado":
      return { text: "#1E7A47", bg: "#E7F4ED", border: "#B9E0C9", dot: "#2F9E62" };
    case "Pendiente":
      return { text: "#9A6A00", bg: "#FBF3DD", border: "#F0DCA0", dot: "#9A6A00" };
    case "Archivado":
      return { text: "#8A8F91", bg: "#F2F4F5", border: "#E5E8EA", dot: "#AEB3B5" };
    default: // Borrador
      return { text: "#5664A6", bg: "rgba(173,185,223,.16)", border: "#D2CFE6", dot: "#7E8BC4" };
  }
}

// ---- demo documents ----
export const DOCS: Doc[] = [
  { id: "cierre", name: "Cierre de caja", estado: "Aprobado", carpeta: "Procesos / Caja", version: "v3", by: "Lucía Gómez", fecha: "hoy" },
  { id: "arqueo", name: "Arqueo de turno", estado: "Borrador", carpeta: "Procesos / Caja", version: "—", by: "Martín Díaz", fecha: "hace 1 h" },
  { id: "apertura", name: "Manual de apertura de estación", estado: "Aprobado", carpeta: "Procesos / Caja", version: "v2", by: "Lucía Gómez", fecha: "ayer" },
  { id: "relevo", name: "Relevo de caja", estado: "Pendiente", carpeta: "Procesos / Caja", version: "—", by: "Martín Díaz", fecha: "hace 3 h" },
  { id: "devol", name: "Procedimiento de devoluciones", estado: "Aprobado", carpeta: "Comercial", version: "v2", by: "Ana Torres", fecha: "hace 2 días" },
  { id: "liq", name: "Liquidación de sueldos", estado: "Aprobado", carpeta: "RRHH / Liquidación", version: "v5", by: "Lucía Gómez", fecha: "1 jun" },
  { id: "arq2021", name: "Arqueo de caja (2021)", estado: "Archivado", carpeta: "Procesos / Caja", version: "v1", by: "Lucía Gómez", fecha: "mar 2021" },
  { id: "polold", name: "Política de turnos (derogada)", estado: "Archivado", carpeta: "Procesos / Turnos", version: "v2", by: "Juan Pérez", fecha: "ago 2022" },
];

// ---- demo folder tree ----
export const FOLDERS: Folder[] = [
  { id: "procesos", name: "Procesos", parent: null, icon: "flow", color: "#48569C", docs: 120 },
  { id: "caja", name: "Caja", parent: "procesos", icon: "box", color: "#48569C", docs: 32 },
  { id: "turnos", name: "Turnos", parent: "procesos", icon: "flow", color: "#48569C", docs: 18 },
  { id: "rrhh", name: "RRHH", parent: null, icon: "shield", color: "#2F9E62", docs: 64 },
  { id: "liquidacion", name: "Liquidación de Sueldos", parent: "rrhh", icon: "chart", color: "#2F9E62", docs: 22 },
  { id: "comercial", name: "Comercial", parent: null, icon: "chart", color: "#C99A2E", docs: 41 },
  { id: "contratos", name: "Contratos", parent: null, icon: "contract", color: "#2E8B8B", docs: 37 },
  { id: "proveedores", name: "Proveedores", parent: "contratos", icon: "contract", color: "#2E8B8B", docs: 12 },
  { id: "seguridad", name: "Seguridad", parent: null, icon: "shield", color: "#CB4242", docs: 28 },
];

// Build "Procesos / Caja" style path for a folder.
export function folderPath(f: Folder, all = FOLDERS): string {
  const parts: string[] = [];
  let cur: Folder | undefined = f;
  while (cur) {
    parts.unshift(cur.name);
    cur = cur.parent ? all.find((x) => x.id === cur!.parent) : undefined;
  }
  return parts.join(" / ");
}

// Feather/Lucide-style folder glyphs by kind.
export const FOLDER_ICON_PATHS: Record<FolderIconKind, string> = {
  flow: "M5 3h6v6H5zM13 15h6v6h-6zM8 9v3a3 3 0 0 0 3 3h2",
  shield: "M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z",
  box: "M21 8l-9-5-9 5 9 5 9-5zM3 8v8l9 5 9-5V8",
  contract: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h4",
  folder: "M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-7l-2-2H5a2 2 0 0 0-2 2z",
  chart: "M3 3v18h18M7 14l4-4 3 3 5-6",
};

/** Small inline icon helper (Feather style). Swap for your icon library. */
export function Icon({ d, size = 16, className = "", strokeWidth = 2 }: { d: string; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
      {d.split("M").filter(Boolean).map((seg, i) => (
        <path key={i} d={"M" + seg} />
      ))}
    </svg>
  );
}

export const ICONS = {
  doc: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
  search: "M11 11m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0M21 21l-4-4",
  check: "M20 6L9 17l-5-5",
  inbox: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  folder: FOLDER_ICON_PATHS.folder,
  plus: "M12 5v14M5 12h14",
  upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  chart: "M3 3v18h18M7 14l4-4 3 3 5-6",
  list: "M4 7h16M4 12h16M4 17h10",
  users: "M17 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M22 21v-2a4 4 0 0 0-3-3.87",
  tyto: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0",
  chevronR: "M9 18l6-6-6-6",
  dots: "M12 5m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0M12 19m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0",
};
