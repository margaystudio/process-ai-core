/**
 * Skeleton — Margay Design System.
 *
 * Extensión local de este módulo (como Dialog/Tabs): no vive todavía en la fuente
 * margay-ui, candidata a subirse cuando el resto de los módulos la necesite.
 *
 * El primitivo para TODA carga de contenido o de página: un bloque que pulsa en el
 * lugar exacto donde va a aparecer el dato real (título, línea de texto, avatar, fila
 * de tabla). Se compone, no se configura por variantes — armá la forma con `className`
 * (alto, ancho, radio) igual que armarías el layout real.
 *
 * Nunca pantallas en blanco ni spinners para esto. El spinner (`<Spinner>`) es SOLO
 * para una acción puntual dentro de un control (botón guardando, import procesando);
 * para todo lo demás —el shell, una lista, un preview— va acá.
 *
 * @example
 * <Skeleton className="h-4 w-1/2" />                 // línea de texto
 * <Skeleton className="h-10 w-10 rounded-full" />     // avatar
 * <Skeleton className="h-96 w-full rounded-lg" />     // bloque de contenido (preview, PDF)
 */
import * as React from "react";
import { cn } from "../cn";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-ink-100", className)}
      {...props}
    />
  );
}
