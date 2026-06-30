// components/Chip.tsx
// Chip de filtro estilo pill. Activo = tint indigo + borde. Inactivo = surface + line.
// Usado en la Biblioteca para filtrar por estado de documento.
import * as React from "react";
import { cn } from "../cn";

export interface ChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export function Chip({ active, className, children, ...props }: ChipProps) {
  return (
    <button
      type="button"
      className={cn(
        "h-8 rounded-pill px-3.5 text-[12.5px] font-bold transition-colors",
        active
          ? "border-[1.5px] border-indigo-light bg-indigo-tint text-indigo"
          : "border border-line bg-surface text-ink-500 hover:border-indigo-light hover:text-ink-700",
        className
      )}
      aria-pressed={active}
      {...props}
    >
      {children}
    </button>
  );
}
