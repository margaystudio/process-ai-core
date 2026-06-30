"use client";

import { Evidence, evidenceIconPath } from "./data";
import { WizardIcon } from "./WizardIcon";
import { Spinner } from "./Spinner";

/**
 * Card de evidencia completa — usada en el paso 1.
 * Muestra tipo + título + chips de resultado (o spinner mientras procesa).
 */
export function EvidenceCard({
  evidence,
  onRemove,
}: {
  evidence: Evidence;
  onRemove?: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-[11px] border border-line p-[11px_13px] animate-in">
      <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] bg-indigo-tint text-indigo">
        <WizardIcon d={evidenceIconPath(evidence.tipo)} size={17} />
      </span>

      <div className="min-w-0 flex-1">
        <div className="truncate text-[13.5px] font-semibold text-ink-700">
          {evidence.title}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          {/* Tipo */}
          <span className="rounded-[5px] bg-indigo-tint px-1.5 py-px text-[9.5px] font-extrabold uppercase tracking-[.04em] text-indigo">
            {evidence.tipo}
          </span>

          {/* Estado: procesando o chips resultado */}
          {evidence.processing ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-warning">
              <Spinner size={12} className="text-warning" />
              Procesando…
            </span>
          ) : (
            evidence.chips.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1 rounded-md border border-success-bd bg-success-bg px-[7px] py-0.5 text-[10.5px] font-semibold text-success-fg"
              >
                <WizardIcon
                  d="M20 6L9 17l-5-5"
                  size={9}
                  className="text-success"
                  strokeWidth={3}
                />
                {c}
              </span>
            ))
          )}
        </div>
      </div>

      {onRemove && (
        <button
          type="button"
          onClick={() => onRemove(evidence.id)}
          title="Quitar evidencia"
          aria-label={`Quitar ${evidence.title}`}
          className="grid h-7 w-7 flex-shrink-0 self-start place-items-center rounded-[7px] border border-line bg-surface transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
        >
          <WizardIcon
            d="M18 6L6 18M6 6l12 12"
            size={13}
            className="text-ink-400"
            strokeWidth={2.2}
          />
        </button>
      )}
    </div>
  );
}

/**
 * Variante compacta — usada en el resumen de generación del paso 2.
 */
export function EvidenceCardCompact({ evidence }: { evidence: Evidence }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-line-soft p-[6px_9px]">
      <span className="grid h-[22px] w-[22px] flex-shrink-0 place-items-center rounded-md bg-indigo-tint text-indigo">
        <WizardIcon d={evidenceIconPath(evidence.tipo)} size={13} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-semibold text-ink-700">
          {evidence.title}
        </div>
      </div>
      <span className="text-[9.5px] font-extrabold uppercase tracking-[.04em] text-ink-400">
        {evidence.tipo}
      </span>
    </div>
  );
}
