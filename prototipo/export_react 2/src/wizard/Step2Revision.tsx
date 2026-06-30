// Step2Revision — review the AI-generated draft before sending to approval.
// Generation summary (evidence used + what the AI organized) + the draft editor
// with read/edit toggle. Draft body is the hardcoded "Cierre de caja" demo.
import React, { useState } from "react";
import { Evidence, Icon } from "./data";
import { EvidenceCardCompact } from "./EvidenceCard";

const DRAFT_TITLE = "Cierre de caja";
const DRAFT_BODY = `Procedimiento para el cierre de caja diario en la estación. Aplica al turno que cierra la jornada.

1 · Arqueo de efectivo
Contá el efectivo en presencia del supervisor y registralo en la planilla de cierre. Separá el fondo fijo antes de declarar el total del turno.

2 · Cierre de lote POS
Ejecutá el cierre de lote en el POS (F4 → Cierre) y verificá el total contra el sistema.

3 · Registro de diferencias
Si hay diferencia, registrala en la planilla y avisá al supervisor antes de cerrar el turno.`;

export function Step2Revision({ evidences }: { evidences: Evidence[] }) {
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(DRAFT_BODY);
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <div className="mx-auto max-w-[900px] px-[30px] py-7">
      <div className="mb-[18px]">
        <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Paso 2 · Revisión</div>
        <div className="text-2xl font-extrabold text-ink-900">Revisá el documento antes de enviarlo a aprobación</div>
      </div>

      {/* generation summary */}
      <div className="mb-4 rounded-[14px] border border-line bg-surface p-[16px_20px] shadow-card">
        <div className="mb-3 flex items-center gap-2.5">
          <Icon d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z" size={16} className="text-indigo" />
          <span className="text-[13.5px] font-extrabold text-ink-900">Resumen de generación</span>
          <span className="ml-auto text-[11.5px] text-ink-400">Generado hace 18 segundos</span>
        </div>
        <div className="grid gap-[18px] sm:grid-cols-2">
          {/* evidence used */}
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-[.04em] text-ink-400">Se usaron · {evidences.length} evidencias</span>
              <button onClick={() => setShowEvidence((v) => !v)} className="text-[11px] font-bold text-indigo">{showEvidence ? "Ocultar" : "Ver evidencias"}</button>
            </div>
            {!showEvidence ? (
              <div className="flex flex-col gap-1.5">
                {["1 audio transcripto", "1 PDF", "3 imágenes"].map((t) => (
                  <div key={t} className="flex items-center gap-2 text-[13px] text-ink-700"><Icon d="M20 6L9 17l-5-5" size={14} className="flex-shrink-0 text-green-bright" strokeWidth={2.6} />{t}</div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-1.5 animate-in">
                {evidences.map((e) => <EvidenceCardCompact key={e.id} evidence={e} />)}
              </div>
            )}
          </div>
          {/* what the AI organized */}
          <div>
            <div className="mb-2 text-[11px] font-bold uppercase tracking-[.04em] text-ink-400">La IA organizó</div>
            <div className="flex gap-2">
              {[["3", "secciones"], ["12", "pasos"], [String(evidences.length), "evidencias"]].map(([v, l]) => (
                <div key={l} className="flex-1 rounded-[10px] border border-line-soft p-[8px_4px] text-center">
                  <div className="text-lg font-extrabold text-indigo">{v}</div>
                  <div className="text-[10.5px] text-ink-400">{l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* editor */}
      <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
        <div className="flex items-center gap-2.5 border-b border-line-soft p-[16px_22px]">
          <span className="text-lg font-extrabold text-ink-900">{DRAFT_TITLE}</span>
          <span className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-line-softer px-2.5 py-[3px] text-[11.5px] font-bold text-ink-500"><span className="h-1.5 w-1.5 rounded-full bg-ink-300" />Borrador</span>
          <span className="flex-1" />
          {!editing ? (
            <button onClick={() => setEditing(true)} className="inline-flex h-[34px] items-center gap-1.5 rounded-[9px] border border-line-input bg-surface px-3.5 text-[13px] font-bold text-ink-800"><Icon d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z" size={14} className="text-indigo" />Editar</button>
          ) : (
            <>
              <button onClick={() => { setBody(DRAFT_BODY); setEditing(false); }} className="h-[34px] rounded-[9px] border border-line-input bg-surface px-[13px] text-[13px] font-semibold text-ink-500">Cancelar</button>
              <button onClick={() => setEditing(false)} className="h-[34px] rounded-[9px] bg-ink-800 px-3.5 text-[13px] font-bold text-white">Listo</button>
            </>
          )}
        </div>
        <div className="p-[22px_26px]">
          {!editing ? (
            <article className="text-sm leading-7 text-ink-700">
              {body.split("\n\n").map((para, i) => {
                const isHeading = /^\d+ · /.test(para.split("\n")[0]);
                if (isHeading) {
                  const [head, ...rest] = para.split("\n");
                  return <div key={i}><h3 className="mt-4 text-[13px] font-extrabold text-indigo">{head}</h3><p className="mt-1.5">{rest.join(" ")}</p></div>;
                }
                return <p key={i} className="mb-3">{para}</p>;
              })}
            </article>
          ) : (
            <textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[320px] w-full resize-y rounded-[10px] border border-line-input p-3.5 text-sm leading-7 text-ink-700 outline-none" />
          )}
        </div>
      </div>
    </div>
  );
}
