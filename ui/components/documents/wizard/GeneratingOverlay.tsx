"use client";

import { useEffect, useRef, useState } from "react";
import { GEN_STEPS } from "./data";
import { WizardIcon } from "./WizardIcon";
import { Spinner } from "./Spinner";

// ── Tiempos estimados por etapa (milisegundos) ──────────────────────────────
//
// El backend es síncrono: no hay progreso real. Estos valores son estimaciones
// basadas en el tiempo típico de cada etapa del pipeline. Con video, las
// primeras etapas (transcripción) tardan significativamente más.
//
// Estrategia: cada etapa tiene una duración estimada. Un setInterval avanza
// el progreso dentro de cada etapa suavemente. La última etapa nunca se marca
// "terminada" de forma autónoma — sólo lo hace cuando el backend responde
// (prop `done=true`). Así nunca mentimos sobre el estado real.
//
// Si el backend responde ANTES de que el timer llegue al final, completamos
// de golpe. Si el backend tarda MÁS que la estimación, el último paso
// queda en "activo" mostrando que sigue trabajando — sin congelarse.

const STEP_DURATIONS_BASE_MS = [
  6_000,  // Procesando evidencias
  8_000,  // Transcribiendo audio
  7_000,  // Analizando documentos
  5_000,  // Organizando secciones
  10_000, // Generando borrador  ← nunca se auto-completa
];

// Con video la transcripción tarda mucho más
const STEP_DURATIONS_VIDEO_MS = [
  10_000, // Procesando evidencias
  40_000, // Transcribiendo audio  ← el cuello de botella real
  8_000,  // Analizando documentos
  5_000,  // Organizando secciones
  15_000, // Generando borrador
];

// Tick del progreso interno por etapa (ms)
const TICK_MS = 200;

// Progreso máximo que alcanza la ÚLTIMA etapa de forma autónoma.
// El 100% solo lo pone el prop `done`.
const LAST_STEP_AUTO_CAP = 0.80;

interface GeneratingOverlayProps {
  /**
   * true cuando hay evidencia de video (calibra los tiempos del stepper:
   * la transcripción de video es el cuello de botella real del pipeline).
   */
  hasVideo?: boolean;
  /**
   * true cuando createProcessRun() resolvió (o falló).
   * Al recibirlo, el overlay completa visualmente el stepper al instante.
   * El caller sigue siendo responsable de mostrar el error o navegar.
   */
  done?: boolean;
}

/**
 * Overlay a pantalla completa mostrado mientras createProcessRun() está en vuelo.
 *
 * El avance es ESTIMADO POR TIEMPO — no refleja el estado real del pipeline
 * porque el backend no expone progreso (síncrono, sin SSE/WS).
 * La última etapa nunca se auto-completa: sólo avanza al 100% cuando el
 * prop `done` es true, evitando marcar como "listo" algo que no terminó.
 *
 * TODO(arquitectura): si el backend agrega progreso en tiempo real (SSE/WS),
 *   reemplazá el timer por el estado real y eliminá los STEP_DURATIONS_*_MS.
 */
export function GeneratingOverlay({
  hasVideo = false,
  done = false,
}: GeneratingOverlayProps) {
  const durations = hasVideo ? STEP_DURATIONS_VIDEO_MS : STEP_DURATIONS_BASE_MS;
  const totalSteps = GEN_STEPS.length;

  // stepProgress: número en [0, totalSteps). La parte entera es el índice de
  // paso actual; la parte decimal es el progreso dentro del paso (0..1).
  const [stepProgress, setStepProgress] = useState(0);

  // Cronómetro de tiempo transcurrido (segundos)
  const [elapsed, setElapsed] = useState(0);

  const startRef = useRef<number>(Date.now());
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Timer principal ────────────────────────────────────────────────────────
  useEffect(() => {
    if (done) return; // cuando done=true el efecto de abajo se encarga

    startRef.current = Date.now();

    tickRef.current = setInterval(() => {
      const now = Date.now();
      const totalElapsedMs = now - startRef.current;

      // Actualizamos el cronómetro
      setElapsed(Math.floor(totalElapsedMs / 1000));

      // Calculamos en qué step estamos según el tiempo acumulado
      let remaining = totalElapsedMs;
      let targetStep = 0;
      let progressInStep = 0;

      for (let i = 0; i < totalSteps; i++) {
        const dur = durations[i];
        if (remaining <= dur) {
          targetStep = i;
          progressInStep = remaining / dur;
          // La última etapa nunca supera el cap autónomo
          if (i === totalSteps - 1) {
            progressInStep = Math.min(progressInStep, LAST_STEP_AUTO_CAP);
          }
          break;
        }
        remaining -= dur;
        // Si consumimos todas las etapas previas y seguimos, quedamos en la última
        if (i === totalSteps - 2) {
          targetStep = totalSteps - 1;
          progressInStep = Math.min(
            remaining / durations[totalSteps - 1],
            LAST_STEP_AUTO_CAP,
          );
          break;
        }
      }

      setStepProgress(targetStep + progressInStep);
    }, TICK_MS);

    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [done, durations, totalSteps]);

  // ── Cuando el backend responde: completar al instante ─────────────────────
  useEffect(() => {
    if (!done) return;
    if (tickRef.current) clearInterval(tickRef.current);
    // Marcamos todos los pasos completos: stepProgress = totalSteps
    setStepProgress(totalSteps);
  }, [done, totalSteps]);

  // ── Derivamos el paso actual y si cada paso está done/active/pending ──────
  const currentStep = Math.min(Math.floor(stepProgress), totalSteps - 1);
  // stepProgress === totalSteps significa que todo está completo
  const allDone = stepProgress >= totalSteps;

  // ── Copy contextual ───────────────────────────────────────────────────────
  const subtitle = hasVideo
    ? "La transcripción de video puede tomar varios minutos. Ya está trabajando."
    : "Un momento — esto lo hace el sistema con las evidencias que cargaste.";

  return (
    <div
      className="flex h-full flex-col items-center justify-center bg-surface-app px-6"
      role="status"
      aria-live="polite"
      aria-label="Generando borrador"
    >
      {/* Ícono IA animado */}
      <span className="relative mb-[18px] grid h-14 w-14 place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-indigo-tint" />
        <span className="relative grid h-14 w-14 place-items-center rounded-[16px] bg-indigo text-white">
          <WizardIcon
            d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z"
            size={26}
          />
        </span>
      </span>

      {/* Título y subtítulo */}
      <div className="mb-1 text-xl font-extrabold text-ink-900">
        La IA está armando el borrador
      </div>
      <div className="mb-[26px] max-w-[380px] text-center text-[13px] text-ink-400">
        {subtitle}
      </div>

      {/* Stepper de etapas con avance estimado */}
      <div className="flex w-full max-w-[420px] flex-col gap-[13px]">
        {GEN_STEPS.map((label, i) => {
          const isDone = allDone ? true : i < currentStep;
          const isActive = !allDone && i === currentStep;
          return (
            <div key={label} className="flex items-center gap-3">
              <span
                className={
                  "grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-full " +
                  (isDone
                    ? "bg-success"
                    : isActive
                    ? "bg-indigo-tint"
                    : "bg-surface-track")
                }
              >
                {isDone && (
                  <WizardIcon
                    d="M20 6L9 17l-5-5"
                    size={14}
                    className="text-white"
                    strokeWidth={2.8}
                  />
                )}
                {isActive && <Spinner size={15} className="text-indigo" />}
              </span>
              <span
                className={
                  "text-sm " +
                  (isDone
                    ? "font-semibold text-success-fg"
                    : isActive
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

      {/* Cronómetro + aclaración de estimación */}
      <div className="mt-[28px] flex flex-col items-center gap-1">
        <span className="font-mono text-[22px] font-extrabold tabular-nums text-ink-700">
          {formatElapsed(elapsed)}
        </span>
        <span className="text-[11.5px] text-ink-400">
          El avance es estimado — la IA sigue trabajando
        </span>
      </div>
    </div>
  );
}

/** Formatea segundos a "0:00" */
function formatElapsed(totalSecs: number): string {
  const m = Math.floor(totalSecs / 60);
  const s = totalSecs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
