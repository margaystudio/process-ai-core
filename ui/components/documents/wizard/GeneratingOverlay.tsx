"use client";

import { GEN_STEPS } from "./data";
import { WizardIcon } from "./WizardIcon";
import { Spinner } from "./Spinner";

/**
 * Overlay a pantalla completa mostrado entre el paso 1 y el paso 2
 * mientras la IA genera el borrador.
 * TODO(wire): reemplazar la simulación setTimeout/setInterval con la llamada real a
 *             createProcessRun — el overlay debería mostrar el progreso real o
 *             mantenerse hasta que la API responda.
 */
export function GeneratingOverlay({ current }: { current: number }) {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-surface-app px-6">
      <span className="relative mb-[18px] grid h-14 w-14 place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-indigo-tint" />
        <span className="relative grid h-14 w-14 place-items-center rounded-[16px] bg-indigo text-white">
          <WizardIcon
            d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z"
            size={26}
          />
        </span>
      </span>

      <div className="mb-1 text-xl font-extrabold text-ink-900">
        La IA está armando el borrador
      </div>
      <div className="mb-[26px] text-center text-[13px] text-ink-400">
        Un momento — esto lo hace el sistema con las evidencias que cargaste.
      </div>

      <div className="flex w-full max-w-[420px] flex-col gap-[13px]">
        {GEN_STEPS.map((label, i) => {
          const done = i < current;
          const active = i === current;
          return (
            <div key={label} className="flex items-center gap-3">
              <span
                className={
                  "grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-full " +
                  (done
                    ? "bg-success"
                    : active
                    ? "bg-indigo-tint"
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
                {active && <Spinner size={15} className="text-indigo" />}
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
    </div>
  );
}
