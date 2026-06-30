// Nuevo documento — AI-assisted authoring from evidence.
// Step 1 (evidence + options) → generation → Step 2 (draft review) → send to approval.
// In the prototype the generated content is the hardcoded "Cierre de caja" case.
import React, { useState } from "react";
import { Icon, ICONS } from "../lib/data";
import { PrimaryButton } from "../components/ui";

type Phase = "input" | "generating" | "review";

const EVIDENCE_KINDS = [
  { k: "audio", label: "Audio", d: "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4" },
  { k: "video", label: "Video", d: "M23 7l-7 5 7 5V7zM1 5h15v14H1z" },
  { k: "pdf", label: "PDF / Word", d: ICONS.doc },
  { k: "img", label: "Imagen", d: "M3 3h18v18H3zM8.5 11l2.5 3 3.5-4.5L21 17" },
  { k: "rec", label: "Grabar ahora", d: "M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" },
];

export default function NuevoDocumentoScreen() {
  const [phase, setPhase] = useState<Phase>("input");

  return (
    <div className="mx-auto max-w-[760px] px-8 pb-[60px] pt-8">
      {phase === "input" && (
        <div className="animate-in">
          <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Paso 1 · Nuevo documento</div>
          <h1 className="text-[25px] font-extrabold text-ink-900">Creá conocimiento desde evidencias</h1>
          <p className="mt-1.5 text-[13px] text-ink-400">Sumá evidencias y la IA redacta un borrador estructurado. Vos revisás y decidís antes de enviarlo a aprobación.</p>

          <div className="mt-6 rounded-[14px] border border-line bg-surface p-5 shadow-card">
            <label className="mb-1.5 block text-[13px] font-bold text-ink-900">Título del documento</label>
            <input defaultValue="Cierre de caja" className="h-[46px] w-full rounded-[10px] border border-line-input px-3.5 text-sm font-semibold outline-none" />
          </div>

          <div className="mb-2 mt-[18px] text-[13px] font-bold text-ink-900">Evidencias</div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {EVIDENCE_KINDS.map((e) => (
              <button key={e.k} className="flex flex-col items-center gap-2 rounded-[12px] border border-line bg-surface px-2 py-4 hover:border-indigo-light">
                <span className="grid h-9 w-9 place-items-center rounded-[10px] bg-indigo-tint text-indigo"><Icon d={e.d} size={18} /></span>
                <span className="text-[11.5px] font-bold text-ink-700">{e.label}</span>
              </button>
            ))}
          </div>

          {/* advanced options */}
          <details className="mt-[18px] rounded-[14px] border border-line bg-surface p-5 shadow-card">
            <summary className="cursor-pointer text-[13px] font-bold text-ink-900">Opciones avanzadas</summary>
            <div className="mt-4 flex flex-col gap-4">
              <div>
                <div className="mb-2 text-[12.5px] font-bold text-ink-700">Nivel de detalle</div>
                <div className="inline-flex items-center gap-0.5 rounded-lg bg-surface-track p-0.5">
                  {["Conciso", "Equilibrado", "Detallado"].map((l, i) => <span key={l} className={"rounded-md px-3.5 py-1.5 text-[12.5px] font-bold " + (i === 1 ? "bg-surface text-ink-800 shadow-card" : "text-ink-400")}>{l}</span>)}
                </div>
              </div>
              <div className="flex items-center justify-between rounded-[12px] border border-line bg-surface px-4 py-3">
                <div><div className="text-[13px] font-bold text-ink-900">Disponible para consultas inteligentes</div><div className="text-[12px] text-ink-400">Tyto podrá usar este documento al responder.</div></div>
                <span className="relative h-[26px] w-[46px] flex-shrink-0 rounded-pill bg-indigo"><span className="absolute left-[23px] top-[3px] h-5 w-5 rounded-full bg-white shadow" /></span>
              </div>
            </div>
          </details>

          <div className="mt-6 flex justify-end">
            <PrimaryButton onClick={() => { setPhase("generating"); setTimeout(() => setPhase("review"), 2200); }} className="!bg-indigo">
              <Icon d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 12l1 2.6L21 16l-2.6 1L17 20l-1-2.6L13 16l2.6-1z" size={17} />Generar borrador con IA
            </PrimaryButton>
          </div>
        </div>
      )}

      {phase === "generating" && (
        <div className="flex flex-col items-center justify-center py-32 text-center animate-in">
          <span className="mb-5 grid h-16 w-16 place-items-center rounded-[18px] bg-indigo text-white">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} className="animate-spin" style={{ animationDuration: ".8s" }}><path d="M21 12a9 9 0 1 1-6.2-8.5" /></svg>
          </span>
          <div className="text-lg font-extrabold text-ink-900">Redactando el borrador…</div>
          <div className="mt-1.5 text-[13px] text-ink-400">La IA estructura las evidencias en un documento. Vos lo revisás antes de continuar.</div>
        </div>
      )}

      {phase === "review" && (
        <div className="animate-in">
          <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Paso 2 · Revisión del borrador</div>
          <h1 className="text-[25px] font-extrabold text-ink-900">Revisá lo que generó la IA</h1>
          <p className="mt-1.5 text-[13px] text-ink-400">Editá lo que necesites. Nada se publica: al confirmar entra al circuito de aprobación como borrador.</p>

          <div className="mt-6 rounded-[14px] border border-line bg-surface p-7 shadow-card">
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-indigo-border bg-indigo-tint px-3 py-1 text-[11px] font-bold text-indigo">Borrador generado por IA</span>
            <h2 className="mt-3 text-lg font-extrabold text-ink-900">Cierre de caja</h2>
            <p className="mt-2 text-sm leading-7 text-ink-700">Procedimiento para el cierre de caja diario en la estación. Aplica al turno que cierra la jornada.</p>
            <h3 className="mt-4 text-[13px] font-extrabold text-indigo">1 · Arqueo de efectivo</h3>
            <p className="mt-1.5 text-sm leading-7 text-ink-700">Contá el efectivo en presencia del supervisor y registralo en la planilla de cierre. Separá el fondo fijo antes de declarar el total del turno.</p>
            <h3 className="mt-4 text-[13px] font-extrabold text-indigo">2 · Cierre de lote POS</h3>
            <p className="mt-1.5 text-sm leading-7 text-ink-700">Ejecutá el cierre de lote en el POS (F4 → Cierre) y verificá el total contra el sistema.</p>
          </div>

          <div className="mt-6 flex items-center justify-between gap-3">
            <button onClick={() => setPhase("input")} className="inline-flex h-[46px] items-center gap-1.5 rounded-[11px] border border-line bg-surface px-[18px] text-[13.5px] font-bold text-ink-500"><Icon d="M19 12H5M11 18l-6-6 6-6" size={16} />Volver a editar</button>
            <PrimaryButton><Icon d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" size={16} />Enviar a aprobación</PrimaryButton>
          </div>
        </div>
      )}
    </div>
  );
}
