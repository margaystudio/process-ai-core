// components/ModuleEmblem.tsx
// Emblemas de módulo. Familia monolínea, grilla 48×48, un solo trazo,
// caja óptica pareja (~34×32) y círculos nunca por debajo de radio 4.
// Trazo = currentColor: se tiñe con text-accent / text-accent-ink según el contexto.
import * as React from "react";

const PATHS = {
  /** Ombú · Visión 360 del negocio — la copa ancha */
  ombu: (
    <>
      <path d="M6 30C8 21 15 14 24 14s16 7 18 16" />
      <path d="M24 30v10" />
      <path d="M12 40h24" />
    </>
  ),
  /** Arrayán · Conocimiento y procesos — nodos enlazados */
  arrayan: (
    <>
      <circle cx="12" cy="13" r="5" />
      <circle cx="12" cy="35" r="5" />
      <circle cx="37" cy="24" r="5" />
      <path d="M16.7 15.3 32.4 21.6" />
      <path d="M16.7 32.7 32.4 26.4" />
    </>
  ),
  /** GPU Operaciones · Objetivos, ETL y monitoreo — el pulso */
  gpu: <path d="M6 24h7l5-15 8 30 5-15h11" />,
  /** Timbó · Clientes, oportunidades y ventas — anillos, el cliente al centro */
  timbo: (
    <>
      <circle cx="24" cy="24" r="4" />
      <path d="M24 13.5a10.5 10.5 0 1 1-7.4 3.1" />
      <path d="M24 7a17 17 0 1 1-12 5" />
    </>
  ),
  /** Ceibo · Capa semántica y chat — la flor */
  ceibo: (
    <>
      <path d="M24 42V26" />
      <path d="M24 26C13 25 6 19 7 11c9-1 17 6 17 15z" />
      <path d="M24 26c11-1 18-7 17-15-9-1-17 6-17 15z" />
    </>
  ),
  /** Pindó · Recepción y gestión de pedidos — la corona de la palma */
  pindo: (
    <>
      <circle cx="24" cy="24" r="4" />
      <path d="M24 20V6" />
      <path d="M27.5 22 40 15" />
      <path d="M27.5 26 40 33" />
      <path d="M24 28v14" />
      <path d="M20.5 26 8 33" />
      <path d="M20.5 22 8 15" />
    </>
  ),
  /** Margay Data · Infraestructura y calidad de datos — capas apiladas */
  data: (
    <>
      <path d="M24 8 40 16 24 24 8 16z" />
      <path d="M8 24l16 8 16-8" />
      <path d="M8 32l16 8 16-8" />
    </>
  ),
} as const;

export type ModuleKey = keyof typeof PATHS;

/**
 * Descriptor de cada módulo: copy de identidad, no dato de negocio. No varía por cliente
 * ni por app, así que vive acá y no en el registro que sirve cada plataforma. El nombre,
 * en cambio, lo trae la app (`ModuleRef.name`): la librería no mantiene un mapa de nombres.
 */
export const MODULE_DESC: Record<ModuleKey, string> = {
  ombu: "Visión 360 del negocio",
  arrayan: "Conocimiento y procesos",
  gpu: "Objetivos, ETL y monitoreo",
  timbo: "Clientes, oportunidades y ventas",
  ceibo: "Capa semántica y chat",
  pindo: "Recepción y gestión de pedidos",
  data: "Infraestructura y calidad de datos",
};

/**
 * ¿Esta clave tiene emblema propio? La lista de módulos la define la app, así que el
 * chrome tiene que tolerar claves que la librería todavía no conoce: se pintan con tile
 * neutro en vez de romper. Agregar un módulo nunca puede tirar abajo el switcher.
 */
export function isModuleKey(key: string): key is ModuleKey {
  return key in PATHS;
}

export function ModuleEmblem({
  module,
  size = 22,
  className,
}: {
  module: ModuleKey;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {PATHS[module]}
    </svg>
  );
}
