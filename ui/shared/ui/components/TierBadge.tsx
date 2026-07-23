// components/TierBadge.tsx
// Nivel de confianza de una fuente citada por Tyto (aprobado/referencia/inferido).
// Copy fijo — nunca usar la palabra "verificado": Tyto no valida documentos,
// solo cita la red aprobada y marca honestamente lo que no lo está.
import * as React from "react";
import { cn } from "../cn";

export type TytoTier = "aprobado" | "referencia" | "inferido";

interface TierMeta {
  label: string;
  text: string;
  bg: string;
  border: string;
  dot: string;
}

const TIER_META: Record<TytoTier, TierMeta> = {
  aprobado: {
    label: "Fuente aprobada",
    text: "var(--success-fg)",
    bg: "var(--success-bg)",
    border: "var(--success-bd)",
    dot: "var(--success)",
  },
  referencia: {
    label: "Referencia no validada",
    text: "var(--warning)",
    bg: "var(--warning-bg)",
    border: "var(--warning-bd)",
    dot: "var(--warning)",
  },
  inferido: {
    label: "Inferido",
    text: "var(--danger)",
    bg: "var(--danger-bg)",
    border: "var(--danger-bd)",
    dot: "var(--danger)",
  },
};

function resolveTier(tier: string): TytoTier {
  return tier === "aprobado" || tier === "referencia" || tier === "inferido"
    ? tier
    : "inferido";
}

export function tierMeta(tier: string): TierMeta {
  return TIER_META[resolveTier(tier)];
}

/** Badge con punto de color + copy exacto del nivel de confianza. */
export function TierBadge({ tier, className }: { tier: string; className?: string }) {
  const m = tierMeta(tier);
  return (
    <span
      className={cn(
        "inline-flex flex-shrink-0 items-center gap-1.5 whitespace-nowrap rounded-pill border px-2.5 py-[5px] text-[11px] font-extrabold",
        className
      )}
      style={{ color: m.text, background: m.bg, borderColor: m.border }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: m.dot }} aria-hidden="true" />
      {m.label}
    </span>
  );
}

/** Punto de color aislado (legend, marcadores de cita inline resueltos). */
export function TierDot({ tier, className }: { tier: string; className?: string }) {
  const m = tierMeta(tier);
  return (
    <span
      className={cn("inline-block h-2 w-2 rounded-full", className)}
      style={{ background: m.dot }}
      aria-hidden="true"
    />
  );
}
