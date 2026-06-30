// Reusable UI primitives — match the prototype's badge/chip/button conventions.
import React from "react";
import { Icon, ICONS, estadoTone, Estado } from "../lib/data";

export function StatusBadge({ estado }: { estado: Estado }) {
  const t = estadoTone(estado);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-pill border px-3 py-[5px] text-[11.5px] font-extrabold whitespace-nowrap"
      style={{ color: t.text, background: t.bg, borderColor: t.border }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.dot }} />
      {estado}
    </span>
  );
}

/** Tinted pill used for "Heredado", "Personalizado", versions, etc. */
export function TintPill({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center rounded-md border px-2 py-0.5 text-[10.5px] font-extrabold"
      style={{ color, background: `${color}14`, borderColor: `${color}33` }}
    >
      {children}
    </span>
  );
}

export function Chip({ active, children, onClick }: { active?: boolean; children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className={
        "h-8 rounded-pill px-3.5 text-[12.5px] font-bold transition-colors " +
        (active
          ? "border-[1.5px] border-indigo-light bg-indigo-tint text-indigo"
          : "border border-line bg-surface text-ink-500 hover:border-indigo-light")
      }
    >
      {children}
    </button>
  );
}

export function PrimaryButton({ children, onClick, className = "" }: { children: React.ReactNode; onClick?: () => void; className?: string }) {
  return (
    <button onClick={onClick} className={"inline-flex h-[46px] items-center gap-2 rounded-[11px] bg-ink-800 px-5 text-sm font-bold text-white " + className}>
      {children}
    </button>
  );
}

export function GhostButton({ children, onClick, className = "" }: { children: React.ReactNode; onClick?: () => void; className?: string }) {
  return (
    <button onClick={onClick} className={"inline-flex h-[46px] items-center gap-2 rounded-[11px] border border-line bg-surface px-5 text-sm font-bold text-ink-700 " + className}>
      {children}
    </button>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={"rounded-[14px] border border-line bg-surface shadow-card " + className}>{children}</div>;
}

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 text-xs font-bold uppercase tracking-[.06em] text-ink-400">{children}</div>;
}

export { Icon, ICONS };
