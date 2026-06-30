// Step3EnviarAprobacion — pick approvers + comment, then send.
// Two states: notSent (selection form) and sent (confirmation card).
import React from "react";
import { Approver, Icon } from "./data";

export interface Step3State {
  folder: string;
  approvers: Approver[];
  comment: string;
  sent: boolean;
}

export function Step3EnviarAprobacion({
  s, set,
}: {
  s: Step3State;
  set: (patch: Partial<Step3State>) => void;
}) {
  const toggle = (id: string) => set({ approvers: s.approvers.map((a) => (a.id === id ? { ...a, sel: !a.sel } : a)) });
  const selected = s.approvers.filter((a) => a.sel);

  return (
    <div className="mx-auto max-w-[720px] px-[30px] py-7">
      <div className="mb-[18px]">
        <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Paso 3 · Enviar a aprobación</div>
        <div className="text-2xl font-extrabold text-ink-900">Enviá el documento al circuito de aprobación</div>
      </div>

      {!s.sent ? (
        <>
          {/* doc header */}
          <div className="mb-4 flex items-center gap-3 rounded-[14px] border border-line bg-surface p-[16px_20px] shadow-card">
            <span className="grid h-[38px] w-[38px] flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo"><Icon d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6" size={19} /></span>
            <div className="flex-1"><div className="text-base font-extrabold text-ink-900">Cierre de caja</div><div className="text-xs text-ink-400">Borrador · en {s.folder}</div></div>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-line-softer px-2.5 py-1 text-[11.5px] font-bold text-ink-500"><span className="h-1.5 w-1.5 rounded-full bg-ink-300" />Borrador</span>
          </div>

          {/* approvers */}
          <div className="mb-4 rounded-[14px] border border-line bg-surface p-[20px_22px] shadow-card">
            <div className="text-sm font-extrabold text-ink-900">Aprobadores disponibles</div>
            <div className="mb-3.5 text-xs text-ink-400">Según la carpeta <strong className="text-ink-500">{s.folder}</strong> y los permisos. Elegí uno o varios.</div>
            <div className="flex flex-col gap-2">
              {s.approvers.map((a) => (
                <button key={a.id} onClick={() => toggle(a.id)} className={"flex items-center gap-3 rounded-[11px] border p-[10px_12px] text-left " + (a.sel ? "border-indigo-light bg-indigo-tint" : "border-line bg-surface")}>
                  <span className={"grid h-[22px] w-[22px] flex-shrink-0 place-items-center rounded-[7px] " + (a.sel ? "bg-indigo" : "border-[1.5px] border-line-input bg-surface")}>
                    {a.sel && <Icon d="M20 6L9 17l-5-5" size={13} className="text-white" strokeWidth={3} />}
                  </span>
                  <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full bg-indigo text-[11px] font-bold text-white">{a.initials}</span>
                  <span className="flex-1"><span className="block text-[13.5px] font-bold text-ink-900">{a.name}</span><span className="block text-[11.5px] text-ink-400">{a.role}</span></span>
                </button>
              ))}
            </div>
          </div>

          {/* comment */}
          <div className="mb-4 rounded-[14px] border border-line bg-surface p-[20px_22px] shadow-card">
            <div className="mb-2 text-[13px] font-bold text-ink-900">Comentario para los aprobadores <span className="font-medium text-ink-400">(opcional)</span></div>
            <textarea value={s.comment} onChange={(e) => set({ comment: e.target.value })} placeholder="Ej: Revisar especialmente el procedimiento de arqueo." className="min-h-[70px] w-full resize-y rounded-[10px] border border-line-input p-[11px_13px] text-[13.5px] leading-normal text-ink-700 outline-none" />
          </div>

          <div className="flex items-start gap-2.5 rounded-xl border border-line-soft bg-[#FAFBFC] p-[13px_16px]">
            <Icon d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 16v-4M12 8h.01" size={17} className="mt-px flex-shrink-0 text-amber" />
            <div className="text-[12.5px] leading-relaxed text-ink-500">El documento queda <strong className="text-ink-800">en revisión</strong> hasta que un aprobador lo apruebe. El versionado oficial empieza recién ahí.</div>
          </div>
        </>
      ) : (
        /* sent confirmation */
        <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card animate-in">
          <div className="flex items-center gap-3 border-b border-line-soft p-[24px_26px]">
            <span className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-full bg-green"><Icon d="M20 6L9 17l-5-5" size={22} className="text-white" strokeWidth={2.6} /></span>
            <div><div className="text-lg font-extrabold text-ink-900">El documento quedó enviado a aprobación</div><div className="text-[12.5px] text-ink-400">Cierre de caja · en revisión</div></div>
          </div>
          <div className="p-[22px_26px]">
            <div className="mb-2.5 text-[11px] font-bold uppercase tracking-[.06em] text-ink-400">Aprobadores seleccionados</div>
            <div className="mb-[22px] flex flex-wrap gap-2">
              {selected.map((a) => (
                <span key={a.id} className="inline-flex items-center gap-2 rounded-pill border border-line py-[5px] pl-[5px] pr-3"><span className="grid h-6 w-6 place-items-center rounded-full bg-indigo text-[10px] font-bold text-white">{a.initials}</span><span className="text-[13px] font-semibold text-ink-700">{a.name}</span></span>
              ))}
            </div>
            <div className="mb-[11px] text-[13px] font-bold text-ink-900">Cuando alguno lo apruebe:</div>
            <div className="flex flex-col gap-2.5">
              {[
                { d: "M9 12l2 2 4-4M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z", bg: "rgba(124,195,156,.22)", c: "#2E6E4D", t: <>Se convierte en la <strong>versión oficial</strong> (arranca el versionado).</> },
                { d: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0", bg: "#37393A", c: "#fff", t: <>Queda <strong>disponible para Tyto</strong> como fuente oficial.</> },
                { d: "M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3z", bg: "rgba(173,185,223,.26)", c: "#48569C", t: <>La IA genera las <strong>relaciones sugeridas</strong> para la red documental.</> },
              ].map((r, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-[7px]" style={{ background: r.bg, color: r.c }}><Icon d={r.d} size={15} /></span>
                  <div className="pt-[3px] text-[13.5px] leading-snug text-ink-700">{r.t}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-line-soft bg-[#FAFBFC] p-[16px_26px]">
            <span className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-pill border border-amber-border bg-amber-bg px-[11px] py-[5px] text-xs font-bold text-amber"><span className="h-1.5 w-1.5 rounded-full bg-amber" />Pendiente de aprobación</span>
            <span className="text-[11.5px] leading-snug text-ink-400">Mientras esté pendiente no podrá editarse.</span>
            <button onClick={() => set({ sent: false })} className="ml-auto inline-flex h-10 flex-shrink-0 items-center gap-1.5 rounded-[10px] border border-line-input bg-surface px-[15px] text-[13px] font-bold text-ink-700"><Icon d="M3 2v6h6M3.51 15a9 9 0 1 0 2.13-9.36L3 8" size={14} className="text-ink-500" />Retirar solicitud</button>
          </div>
        </div>
      )}
    </div>
  );
}
