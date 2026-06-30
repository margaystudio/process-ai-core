"use client";

import { WizardIcon } from "./WizardIcon";
import { Spinner } from "./Spinner";

/**
 * Pipeline vertical de procesamiento reutilizable.
 * done = check verde · active = spinner ámbar · todo = punto gris
 */
export function ProcessingSteps({
  steps,
  current,
}: {
  steps: string[];
  current: number;
}) {
  return (
    <div className="flex flex-col gap-[11px] px-1 py-[14px]">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={label} className="flex items-center gap-[11px]">
            <span
              className={
                "grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-full " +
                (done
                  ? "bg-success"
                  : active
                  ? "bg-warning-bg"
                  : "bg-surface-track")
              }
            >
              {done && (
                <WizardIcon
                  d="M20 6L9 17l-5-5"
                  size={14}
                  className="text-white"
                  strokeWidth={2.8}
                />
              )}
              {active && <Spinner size={15} className="text-warning" />}
            </span>
            <span
              className={
                "text-sm " +
                (done
                  ? "font-semibold text-success-fg"
                  : active
                  ? "font-bold text-ink-900"
                  : "font-medium text-ink-300")
              }
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
