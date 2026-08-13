// components/ModuleSwitcher.tsx
// El lockup del topbar: emblema + nombre + descriptor del módulo actual, que abre el
// menú de módulos.
//
// Presentación pura: no hace fetch, no conoce servicios, no decide qué mostrar. La app
// pasa `modules` (los que quiere mostrar, ya resueltos los permisos) y la librería pinta
// eso y nada más. El NOMBRE lo trae la app en `ModuleRef.name` — la librería no mantiene
// un mapa de nombres. Lo que sí aporta: el emblema, el color y el descriptor.
//
// Los destinos son enlaces reales (<a href>) porque cada módulo es un subdominio: no hay
// router en común. Y abren en pestaña nueva: saltar de módulo no puede costarte lo que
// tenías a medio hacer en el actual. Van a la `entryUrl` pelada: el cliente activo NO
// viaja en la URL, viaja
// en la cookie compartida de `.margaystudio.io`, que todos los módulos ya leen. Se probó
// ponerlo en el path (`${entryUrl}/${slug}`, hasta 0.11.0) y era una promesa que ningún
// módulo cumplía: ninguno rutea ese segmento, así que cada salto caía en 404.
"use client";
import * as React from "react";
import { ChevronDown, Check } from "lucide-react";
import { ModuleEmblem, MODULE_DESC, isModuleKey } from "./ModuleEmblem";
import { cn } from "../cn";

/**
 * Un módulo, tal como lo declara la app. `key` es `string` y no `ModuleKey` a propósito:
 * la lista de módulos la define la app, no la librería.
 */
export interface ModuleRef {
  /** Si coincide con un emblema conocido, se usa; si no, va tile neutro. */
  key: string;
  /** Se pinta tal cual. La librería no lo deriva ni lo completa. */
  name: string;
  /** Origen del módulo. La barra final, si viene, se ignora. */
  entryUrl: string;
  /**
   * Marca la fila como no aplicable al cliente activo. La librería solo lo pinta:
   * quién está disponible lo decide la app.
   */
  unavailable?: boolean;
}

/** Cliente/organización. `id` es lo que maneja la app; `name` lo que se pinta. */
export interface TenantRef {
  id: string;
  name: string;
  slug: string;
}

/**
 * Marca del cliente, para los módulos white-label. Cuando viene, el lockup habla del
 * CLIENTE (su nombre y su bajada) en vez del módulo: es lo que el usuario de ese cliente
 * espera ver arriba a la izquierda. El menú no cambia — adentro, el módulo actual sigue
 * saliendo con su nombre y su descriptor de plataforma.
 */
export interface BrandRef {
  name: string;
  subtitle?: string;
}

export function ModuleSwitcher({
  module,
  modules,
  brand,
  hubUrl,
  logoSrc = "/brand/margay-icon-48.png",
}: {
  /** Clave del módulo actual: fija el emblema del lockup. */
  module: string;
  /** Si falta —o trae uno solo— el lockup no abre menú. */
  modules?: ModuleRef[];
  /** Marca del cliente (white-label). Sin esto, el lockup habla del módulo. */
  brand?: BrandRef;
  /** Si falta, el menú no muestra la salida al Hub. */
  hubUrl?: string;
  logoSrc?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  // Un solo módulo (o ninguno) no es un menú: es un lockup y punto.
  const abrible = (modules?.length ?? 0) > 1;
  const actual = modules?.find((m) => m.key === module);

  React.useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const desc = isModuleKey(module) ? MODULE_DESC[module] : undefined;

  // Con marca de cliente manda el cliente; si no, el módulo. En los dos casos el bloque
  // es el mismo: título arriba, bajada abajo.
  const titulo = brand?.name ?? actual?.name;
  const bajada = brand ? brand.subtitle : desc;

  const lockup = (
    <>
      <Tile moduleKey={module} />
      {/* Sin registro y sin marca no hay nombre: el lockup queda solo con el emblema. La
          bajada va con el título — sola, se leería como si fuera el nombre. */}
      {titulo && (
        <span className="min-w-0 text-left leading-tight">
          <span className="block truncate text-h3 font-bold text-ink-900">{titulo}</span>
          {bajada && <span className="hidden truncate text-xs text-ink-500 lg:block">{bajada}</span>}
        </span>
      )}
    </>
  );

  if (!abrible) {
    return <div className="flex min-w-0 items-center gap-3">{lockup}</div>;
  }

  return (
    <div className="relative min-w-0" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="-mx-1.5 flex min-w-0 items-center gap-3 rounded-md px-1.5 py-1 transition-colors hover:bg-ink-100"
      >
        {lockup}
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-ink-400 transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Cambiar de módulo"
          className="absolute left-0 z-50 mt-1 w-[304px] max-w-[calc(100vw-2rem)] rounded-lg border border-ink-200 bg-white p-1.5 shadow-md"
        >
          {modules?.map((m) => {
            const esActual = m.key === module;
            const descFila = isModuleKey(m.key) ? MODULE_DESC[m.key] : undefined;
            const contenido = (
              <>
                <Tile moduleKey={m.key} caja="h-9 w-9" glifo={20} />
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-sm font-bold text-ink-800">{m.name}</span>
                  {descFila && (
                    <span className="block truncate text-xs text-ink-500">{descFila}</span>
                  )}
                </span>
                {m.unavailable ? (
                  <span className="shrink-0 text-xs text-ink-500">No disponible</span>
                ) : (
                  esActual && <Check className="h-4 w-4 shrink-0 text-accent" />
                )}
              </>
            );
            const clases = cn(
              "flex items-center gap-3 rounded-md px-2 py-2",
              esActual ? "bg-ink-100" : "transition-colors hover:bg-ink-100",
              m.unavailable && "opacity-60"
            );

            // El módulo actual no es un destino: ya estás ahí. Con apertura en pestaña
            // nueva, un link acá sería un duplicado de la pestaña que ya tenés abierta.
            return esActual ? (
              <div key={m.key} role="menuitem" aria-current="page" className={clases}>
                {contenido}
              </div>
            ) : (
              <a
                key={m.key}
                href={hrefDe(m)}
                role="menuitem"
                // Pestaña nueva: saltar de módulo no puede costarte lo que tenías a medio
                // hacer en este. `noopener` va explícito y no por el default del browser.
                target="_blank"
                rel="noopener noreferrer"
                className={clases}
              >
                {contenido}
              </a>
            );
          })}

          {/* El Hub no es un módulo: sin emblema, con el logo Margay, siempre al final. */}
          {hubUrl && (
            <div className="mt-1.5 border-t border-ink-200 pt-1.5">
              <a
                href={hubUrl}
                role="menuitem"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-ink-100"
              >
                <img src={logoSrc} alt="" className="h-9 w-9 shrink-0 rounded-md" />
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-sm font-bold text-ink-800">Hub</span>
                  <span className="block truncate text-xs text-ink-500">Plataforma Margay</span>
                </span>
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Tile del emblema. Clave conocida → emblema + acento del módulo (vía `data-module`
 * propio, así cada fila sale en SU color y no en el del módulo actual). Clave
 * desconocida → tile neutro, nunca un error.
 */
function Tile({
  moduleKey,
  caja = "h-[34px] w-[34px]",
  glifo = 22,
}: {
  moduleKey: string;
  caja?: string;
  glifo?: number;
}) {
  if (!isModuleKey(moduleKey)) {
    return (
      <span
        className={cn("grid shrink-0 place-items-center rounded-md bg-ink-100 text-ink-400", caja)}
      >
        {/* Marcador de la misma familia (grilla 48, trazo 3, radio ≥ 4) para una clave
            que la librería todavía no dibuja. */}
        <svg
          viewBox="0 0 48 48"
          width={glifo}
          height={glifo}
          fill="none"
          stroke="currentColor"
          strokeWidth={3}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="12" y="12" width="24" height="24" rx="6" />
        </svg>
      </span>
    );
  }

  return (
    <span
      data-module={moduleKey}
      className={cn(
        "grid shrink-0 place-items-center rounded-md bg-accent-tint text-accent-ink",
        caja
      )}
    >
      <ModuleEmblem module={moduleKey} size={glifo} />
    </span>
  );
}

/** La `entryUrl` pelada, sin barra final. El cliente activo va por la cookie compartida. */
export function hrefDe(m: ModuleRef) {
  return m.entryUrl.replace(/\/+$/, "");
}
