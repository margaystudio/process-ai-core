// components/ModuleEmblem.tsx
// Emblema monolínea por módulo (familia, grilla 48×48). Trazo = currentColor,
// así se tiñe con text-accent / text-accent-ink según el contexto data-module.
import * as React from "react";

const PATHS = {
  hub: (
    <>
      <circle cx="24" cy="24" r="5" />
      <circle cx="24" cy="24" r="13" opacity={0.5} />
    </>
  ),
  process: (
    <>
      <circle cx="11" cy="13" r="3.2" />
      <circle cx="11" cy="35" r="3.2" />
      <circle cx="37" cy="24" r="3.2" />
      <path d="M14 14l20 9M14 34l20 -9" />
    </>
  ),
  oms: (
    <>
      <path d="M13 14h14l8 10-8 10H13" />
      <path d="M11 24h13" />
    </>
  ),
  gpu: <path d="M8 24h6l4 -12 6 24 4 -12h6" />,
  insights: (
    <>
      <path d="M6 24c5 -9 31 -9 36 0c-5 9 -31 9 -36 0z" />
      <circle cx="24" cy="24" r="6" />
    </>
  ),
} as const;

export type ModuleKey = keyof typeof PATHS;

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
