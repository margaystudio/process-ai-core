// EvidenceCard — reusable evidence row with type variants + processing/done states.
// Used in Step 1 (evidence list) and reused (compact) in Step 2's generation summary.
import React from "react";
import { Evidence, evidenceIconPath, Icon } from "./data";

export function EvidenceCard({ evidence, onRemove }: { evidence: Evidence; onRemove?: (id: string) => void }) {
  return (
    <div className="flex items-center gap-3 rounded-[11px] border border-line p-[11px_13px] animate-in">
      <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] bg-indigo-tint text-indigo">
        <Icon d={evidenceIconPath(evidence.tipo)} size={17} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] font-semibold text-ink-700">{evidence.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {/* type tag */}
          <span className="rounded-[5px] bg-indigo-tint px-1.5 py-px text-[9.5px] font-extrabold uppercase tracking-[.04em] text-indigo">{evidence.tipo}</span>
          {/* processing… */}
          {evidence.processing ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-amber">
              <Spinner size={12} className="text-amber" />Procesando…
            </span>
          ) : (
            // result chips (e.g. "Audio transcripto", "Idioma: ES", "1:32")
            evidence.chips.map((c) => (
              <span key={c} className="inline-flex items-center gap-1 rounded-md border border-[#C7E3D2] bg-[#EAF5EE] px-[7px] py-0.5 text-[10.5px] font-semibold text-[#3E7D5A]">
                <Icon d="M20 6L9 17l-5-5" size={9} className="text-green-bright" strokeWidth={3} />{c}
              </span>
            ))
          )}
        </div>
      </div>
      {onRemove && (
        <button onClick={() => onRemove(evidence.id)} title="Quitar" className="grid h-7 w-7 flex-shrink-0 self-start place-items-center rounded-[7px] border border-line bg-surface">
          <Icon d="M18 6L6 18M6 6l12 12" size={13} className="text-ink-400" strokeWidth={2.2} />
        </button>
      )}
    </div>
  );
}

/** Compact variant for Step 2 summary (no remove, smaller). */
export function EvidenceCardCompact({ evidence }: { evidence: Evidence }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-line-soft p-[6px_9px]">
      <span className="grid h-[22px] w-[22px] flex-shrink-0 place-items-center rounded-md bg-indigo-tint text-indigo"><Icon d={evidenceIconPath(evidence.tipo)} size={13} /></span>
      <div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold text-ink-700">{evidence.title}</div></div>
      <span className="text-[9.5px] font-extrabold uppercase tracking-[.04em] text-ink-400">{evidence.tipo}</span>
    </div>
  );
}

export function Spinner({ size = 15, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} className={"animate-spin " + className} style={{ animationDuration: ".8s" }}>
      <path d="M21 12a9 9 0 1 1-6.2-8.5" />
    </svg>
  );
}
