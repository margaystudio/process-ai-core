// ProcessingSteps — vertical pipeline shown while an evidence/file is processed.
// done = green check, active = amber spinner, todo = grey dot.
import React from "react";
import { Icon } from "./data";
import { Spinner } from "./EvidenceCard";

export function ProcessingSteps({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex flex-col gap-[11px] px-1 py-[14px]">
      {steps.map((label, i) => {
        const done = i < current, active = i === current;
        return (
          <div key={label} className="flex items-center gap-[11px]">
            <span className={"grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-full " + (done ? "bg-green" : active ? "bg-amber-bg" : "bg-surface-track")}>
              {done && <Icon d="M20 6L9 17l-5-5" size={14} className="text-white" strokeWidth={2.8} />}
              {active && <Spinner size={15} className="text-amber" />}
            </span>
            <span className={"text-sm " + (done ? "font-semibold text-green-text" : active ? "font-bold text-ink-900" : "font-medium text-ink-300")}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}
