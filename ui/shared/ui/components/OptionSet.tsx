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
  return (
    <div
      className={cn("grid gap-2.5", className)}
      style={{ gridTemplateColumns: `repeat(${columns ?? options.length}, minmax(0,1fr))` }}
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
