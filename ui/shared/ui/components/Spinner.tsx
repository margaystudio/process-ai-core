/**
 * Spinner — Margay Design System.
 *
 * Extensión local de este módulo (como Dialog/Tabs): no vive todavía en la fuente
 * margay-ui, candidata a subirse cuando el resto de los módulos la necesite.
 *
 * ÚNICO spinner del sistema. Se usa SOLO para una acción en curso dentro de un
 * control: un botón guardando, una fila procesando, una búsqueda en progreso. Nunca
 * para carga de página o de contenido — eso es `<Skeleton>`, y nunca a pantalla
 * completa (eso incluye al viejo `LoadingOverlay` con el logo del margay girando,
 * retirado del sistema).
 *
 * Sin `label`, es puramente decorativo (`aria-hidden`): asume que hay un texto visible
 * al lado ("Guardando…", "Descargando…") que ya comunica el estado. Con `label`, agrega
 * ese texto para lectores de pantalla (spinner solo, sin caption visible).
 *
 * @example
 * <Button disabled={saving}>
 *   {saving ? <Spinner size="sm" /> : <Save />}
 *   {saving ? 'Guardando…' : 'Guardar'}
 * </Button>
 *
 * <Spinner size="md" label="Buscando…" />
 */
import * as React from "react";
import { Loader2 } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../cn";

const spinnerVariants = cva("animate-spin", {
  variants: {
    size: {
      xs: "h-3 w-3",
      sm: "h-4 w-4",
      md: "h-5 w-5",
      lg: "h-8 w-8",
    },
  },
  defaultVariants: { size: "sm" },
});

export interface SpinnerProps
  extends React.SVGAttributes<SVGSVGElement>,
    VariantProps<typeof spinnerVariants> {
  /** Texto para lectores de pantalla cuando no hay caption visible al lado. */
  label?: string;
}

export function Spinner({ size, className, label, ...props }: SpinnerProps) {
  return (
    <>
      <Loader2 className={cn(spinnerVariants({ size }), className)} aria-hidden="true" {...props} />
      {label && <span className="sr-only">{label}</span>}
    </>
  );
}

export { spinnerVariants };
