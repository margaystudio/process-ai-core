/**
 * Lógica pura de InheritancePill — sin imports de React.
 * Importable desde tests (env: node) sin procesar JSX.
 *
 * El componente visual en shared/ui/components/InheritancePill.tsx
 * re-exporta estos tipos y esta función.
 */

export type InheritanceKind = "base" | "inherited" | "custom";

export interface InheritancePillInput {
  kind: InheritanceKind;
  /** Nombre del contexto del que se hereda (requerido cuando kind === "inherited"). */
  from?: string;
}

export interface InheritancePillDerived {
  label: string;
  variant: InheritanceKind;
}

/**
 * Función pura: dado el kind y el nombre opcional de la fuente,
 * devuelve el label a mostrar y la variante visual.
 */
export function deriveInheritancePill({
  kind,
  from,
}: InheritancePillInput): InheritancePillDerived {
  switch (kind) {
    case "base":
      return { label: "Configuración base", variant: "base" };
    case "inherited":
      return {
        label: from ? `Heredado de ${from}` : "Heredado",
        variant: "inherited",
      };
    case "custom":
      return { label: "Personalizado", variant: "custom" };
  }
}
