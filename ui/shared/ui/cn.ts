import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// El preset define tamaños de tipografía propios (text-display/h1/h2/h3/body/label,
// además de sm/xs). tailwind-merge no los conoce y, si no se los registramos, trata
// p.ej. `text-body` como un `text-{color}` y lo hace colisionar con `text-action-on`
// (descartando el color). Los declaramos en el grupo font-size para que no choquen.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["display", "h1", "h2", "h3", "body", "sm", "xs", "label"] }],
    },
  },
});

/** Combina clases de Tailwind resolviendo conflictos (estándar shadcn/ui). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
