// components/OptionSet.tsx
// Selección de UNA opción (radio cards). Se tiñe con el acento del módulo activo.
import * as React from "react";
import { cn } from "../cn";

export interface Option {
  value: string;
  label: string;
}

export function OptionSet({
  options,
  value,
  onChange,
  columns,
  className,
}: {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  /** nº de columnas; por defecto una por opción */
  columns?: number;
  className?: string;
}) {
  // Responsive: 1 columna en mobile, `columns` (o una por opción) desde sm.
  // El nº de columnas va por CSS var para no romper el escaneo de clases de Tailwind.
  const cols = columns ?? options.length;
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-2.5 sm:[grid-template-columns:repeat(var(--option-cols),minmax(0,1fr))]",
        className
      )}
      style={{ ["--option-cols" as string]: String(cols) }}
      role="radiogroup"
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md border-[1.5px] border-ink-300 bg-white px-3.5 py-3 text-center text-body font-semibold text-ink-700 transition-colors hover:border-ink-400",
            value === o.value && "border-accent bg-accent-tint text-accent-ink"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
