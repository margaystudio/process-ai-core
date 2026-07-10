/**
 * InheritancePill — Margay Design System.
 *
 * Pill que comunica el origen de una configuración en el árbol de carpetas:
 *   "base"      → Configuración base (no heredada, no personalizada).
 *   "inherited" → Heredado de [nombre de carpeta padre].
 *   "custom"    → Personalizado (diferente a lo que heredaría).
 *
 * La lógica pura vive en `ui/lib/inheritancePill.ts` para ser testeable
 * sin DOM (env: node).
 *
 * @example
 * <InheritancePill kind="inherited" from="Carpeta Raíz" />
 */
import * as React from "react";
import { cn } from "../cn";
import {
  deriveInheritancePill,
  type InheritanceKind,
  type InheritancePillInput,
  type InheritancePillDerived,
} from "../../../lib/inheritancePill";

// Re-exportamos para que los consumidores del componente tengan acceso directo.
export {
  deriveInheritancePill,
  type InheritanceKind,
  type InheritancePillInput,
  type InheritancePillDerived,
};

// ─── Estilos por variante ──────────────────────────────────────────────────

const variantClasses: Record<InheritanceKind, string> = {
  // Azul info: configuración que viene de la base del sistema.
  base: "bg-info-bg text-info border border-info-bd",
  // Verde success: herencia activa desde un padre.
  inherited: "bg-success-bg text-success-fg border border-success-bd",
  // Naranja warning: configuración local que difiere del padre.
  custom: "bg-warning-bg text-warning border border-warning-bd",
};

// ─── Componente ────────────────────────────────────────────────────────────

export interface InheritancePillProps extends InheritancePillInput {
  className?: string;
}

export function InheritancePill({ kind, from, className }: InheritancePillProps) {
  const { label, variant } = deriveInheritancePill({ kind, from });

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-pill px-2.5 py-1 text-xs font-semibold leading-none",
        variantClasses[variant],
        className
      )}
    >
      {label}
    </span>
  );
}
