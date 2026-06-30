"use client";

import { WizardIcon } from "./WizardIcon";

export const WIZARD_STEPS = [
  "Nuevo documento",
  "Revisión",
  "Enviar a aprobación",
] as const;

export interface WizardFooter {
  primaryLabel: string;
  hint: string;
  onPrimary: () => void;
  onBack?: () => void;
  disabled?: boolean;
  hideBack?: boolean;
}

/**
 * Shell compartido por todos los pasos del wizard:
 *   - Stepper superior (1 · 2 · 3)
 *   - Slot de contenido scrollable
 *   - Barra de acción inferior (Atrás / hint / botón primario)
 */
export function WizardContainer({
  step,
  children,
  footer,
}: {
  step: number; // 1..3
  children: React.ReactNode;
  footer?: WizardFooter | null;
}) {
  return (
    <div className="flex h-full flex-col">
      {/* Stepper */}
      <div className="flex flex-shrink-0 items-center border-b border-line bg-surface px-[30px] py-3.5">
        {WIZARD_STEPS.map((label, i) => {
          const n = i + 1;
          const state =
            n < step ? "done" : n === step ? "current" : "todo";
          return (
            <div key={label} className="flex items-center">
              {i > 0 && (
                <div
                  className="mx-1.5 h-0.5 min-w-[18px] flex-1 rounded"
                  style={{
                    background: n <= step ? "#9ECBB0" : "#E5E8EA",
                  }}
                />
              )}
              <div className="flex items-center gap-2">
                <span
                  className={
                    "grid h-7 w-7 flex-shrink-0 place-items-center rounded-full text-[12.5px] font-extrabold " +
                    (state === "done"
                      ? "bg-success text-white"
                      : state === "current"
                      ? "bg-ink-800 text-white"
                      : "border-[1.5px] border-line-input bg-surface text-ink-300")
                  }
                >
                  {state === "done" ? (
                    <WizardIcon
                      d="M20 6L9 17l-5-5"
                      size={14}
                      strokeWidth={3}
                    />
                  ) : (
                    n
                  )}
                </span>
                <span
                  className={
                    "whitespace-nowrap text-[12.5px] font-bold " +
                    (state === "current"
                      ? "text-ink-900"
                      : state === "done"
                      ? "text-success-fg"
                      : "text-ink-300")
                  }
                >
                  {label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Contenido (scrollable) */}
      <div className="min-h-0 flex-1 overflow-y-auto bg-surface-app">
        {children}
      </div>

      {/* Barra de acción */}
      {footer && (
        <div className="flex flex-shrink-0 items-center gap-4 border-t border-line bg-surface px-[30px] py-3.5">
          {!footer.hideBack && (
            <button
              type="button"
              onClick={footer.onBack}
              className="inline-flex h-11 items-center gap-1.5 rounded-[11px] border border-line bg-surface px-[18px] text-[13.5px] font-bold text-ink-500 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
            >
              <WizardIcon d="M19 12H5M11 18l-6-6 6-6" size={16} />
              Atrás
            </button>
          )}
          <span className="ml-auto text-[12.5px] text-ink-400">
            {footer.hint}
          </span>
          <button
            type="button"
            onClick={footer.onPrimary}
            disabled={footer.disabled}
            className={
              "inline-flex h-11 min-w-[130px] items-center justify-center gap-2 rounded-[11px] px-5 text-sm font-bold text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action " +
              (footer.disabled
                ? "cursor-not-allowed bg-ink-300"
                : "bg-ink-800 hover:bg-ink-900 active:bg-action-press")
            }
          >
            {footer.primaryLabel}
            <WizardIcon
              d="M5 12h14M13 6l6 6-6 6"
              size={17}
              strokeWidth={2.2}
            />
          </button>
        </div>
      )}
    </div>
  );
}
