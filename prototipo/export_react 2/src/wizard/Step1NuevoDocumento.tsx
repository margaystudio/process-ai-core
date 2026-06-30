// Step1NuevoDocumento — two columns:
//   left = form (Nombre, Guardar en, contexto for the AI, advanced options)
//   right = Evidencias panel (list with processing/done states, add evidence)
import React from "react";
import { Evidence, CONTEXT_EXAMPLES, DETAIL_LEVELS, Icon } from "./data";
import { FolderSelector } from "./FolderSelector";
import { EvidenceCard } from "./EvidenceCard";

export interface Step1State {
  name: string; folder: string; contexto: string;
  advancedOpen: boolean; detailLevel: string; smartQueries: boolean;
  evidences: Evidence[];
}

export function Step1NuevoDocumento({
  s, set, onAddEvidence, onRemoveEvidence,
}: {
  s: Step1State;
  set: (patch: Partial<Step1State>) => void;
  onAddEvidence: () => void;       // opens AddEvidenceModal
  onRemoveEvidence: (id: string) => void;
}) {
  return (
    <div className="mx-auto max-w-[1200px] px-[30px] py-7">
      <div className="mb-5">
        <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Paso 1 · Nuevo documento</div>
        <div className="text-2xl font-extrabold text-ink-900">Creemos un documento desde sus evidencias</div>
      </div>

      <div className="grid items-start gap-5" style={{ gridTemplateColumns: "1.12fr 1fr" }}>
        {/* ---- form ---- */}
        <div className="rounded-[14px] border border-line bg-surface p-[22px_24px] shadow-card">
          <Label required>Nombre del documento</Label>
          <input value={s.name} onChange={(e) => set({ name: e.target.value })} placeholder="Ej: Recepción de mercadería" className="mb-5 h-[46px] w-full rounded-[10px] border border-line-input px-3.5 text-[15px] font-semibold text-ink-900 outline-none" />

          <Label required>Guardar en</Label>
          <FolderSelector value={s.folder} onChange={(f) => set({ folder: f })} />

          <Divider />

          <Label>Información que la IA debería tener en cuenta <span className="font-medium text-ink-400">(opcional)</span></Label>
          <textarea value={s.contexto} onChange={(e) => set({ contexto: e.target.value })} placeholder="Contale a la IA lo que no se ve en las evidencias…" className="min-h-[88px] w-full resize-y rounded-[10px] border border-line-input p-[11px_13px] text-[13.5px] leading-normal text-ink-700 outline-none" />
          <div className="mt-[9px] flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-ink-400">Ejemplos:</span>
            {CONTEXT_EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => set({ contexto: ex })} className="rounded-pill border border-indigo-border bg-indigo-tint px-[11px] py-1 text-[11.5px] text-indigo">{ex}</button>
            ))}
          </div>
          <div className="mt-[9px] text-[11.5px] leading-snug text-ink-300">Es solo una ayuda para la IA, no es obligatorio. La descripción y el resto la infiere automáticamente al crear el borrador.</div>

          <div className="mt-5 h-px bg-line-soft" />
          {/* advanced options */}
          <button onClick={() => set({ advancedOpen: !s.advancedOpen })} className="flex w-full items-center gap-2.5 pt-3.5 text-left">
            <Icon d="M9 18l6-6-6-6" size={15} className="text-ink-400 transition-transform" strokeWidth={2.2} style={{ transform: `rotate(${s.advancedOpen ? 90 : 0}deg)` } as any} />
            <span className="text-[13px] font-bold text-ink-700">Opciones avanzadas</span>
            <span className="text-[11.5px] text-ink-300">normalmente no hace falta tocarlas</span>
          </button>
          {s.advancedOpen && (
            <div className="mt-3.5 animate-in">
              <Label>Nivel de detalle</Label>
              <div className="relative">
                <select value={s.detailLevel} onChange={(e) => set({ detailLevel: e.target.value })} className="h-11 w-full appearance-none rounded-[10px] border border-line-input bg-surface px-[13px] pr-9 text-[13.5px] font-semibold text-ink-700 outline-none">
                  {DETAIL_LEVELS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                </select>
                <Icon d="M6 9l6 6 6-6" size={15} className="pointer-events-none absolute right-[13px] top-[15px] text-ink-300" />
              </div>
              <div className="mt-[7px] text-[11.5px] text-ink-300">En automático, la IA elige el nivel según las evidencias.</div>

              <div className="mt-[18px] flex items-start gap-3.5 border-t border-line-soft pt-[18px]">
                <div className="min-w-0 flex-1">
                  <div className="mb-[3px] text-[12.5px] font-bold text-ink-900">Disponible para consultas inteligentes</div>
                  <div className="text-[11.5px] leading-snug text-ink-300">Si lo desactivás, Tyto no usará este documento para responder consultas inteligentes.</div>
                </div>
                <Toggle on={s.smartQueries} onClick={() => set({ smartQueries: !s.smartQueries })} />
              </div>
            </div>
          )}
        </div>

        {/* ---- evidences ---- */}
        <div className="rounded-[14px] border border-line bg-surface p-[22px_24px] shadow-card">
          <div className="mb-[5px] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="text-[15px] font-extrabold text-ink-900">Evidencias</span>
              <span className="rounded-pill bg-indigo-tint px-2.5 py-[3px] text-xs font-bold text-indigo">{s.evidences.length}</span>
            </div>
            <button onClick={onAddEvidence} className="inline-flex h-[34px] items-center gap-1.5 rounded-[9px] bg-ink-800 px-[13px] text-[12.5px] font-bold text-white">
              <Icon d="M12 5v14M5 12h14" size={14} strokeWidth={2.2} />Agregar evidencia
            </button>
          </div>
          <div className="mb-4 text-[12px] leading-snug text-ink-400">Sumá evidencias que ya existen (audio, video, PDF, imágenes, documentos) o grabá un audio en el momento. Apenas las cargás, el sistema las procesa; la IA arma el borrador al tocar “Crear borrador”.</div>

          {s.evidences.length === 0 ? (
            <div className="rounded-xl border-[1.5px] border-dashed border-line-input px-5 py-10 text-center">
              <Icon d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" size={30} className="mx-auto mb-2.5 text-ink-200" strokeWidth={1.6} />
              <div className="mb-[3px] text-sm font-bold text-ink-500">No hay evidencias agregadas</div>
              <div className="text-[12.5px] text-ink-300">Hacé clic en “Agregar evidencia” para comenzar</div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {s.evidences.map((e) => <EvidenceCard key={e.id} evidence={e} onRemove={onRemoveEvidence} />)}
              <button onClick={onAddEvidence} className="flex items-center justify-center gap-2 rounded-[11px] border-[1.5px] border-dashed border-line-input bg-surface-hover p-[13px]">
                <Icon d="M12 5v14M5 12h14" size={17} className="text-ink-300" strokeWidth={1.8} />
                <span className="text-[13px] text-ink-400">Agregar <span className="font-semibold text-indigo">otra evidencia</span></span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return <div className="mb-2 text-[12.5px] font-bold text-ink-900">{children}{required && <span className="text-red"> *</span>}</div>;
}
function Divider() { return <div className="my-[20px] h-px bg-line-soft" />; }
function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} role="switch" aria-checked={on} className={"relative h-[26px] w-[46px] flex-shrink-0 rounded-pill transition-colors " + (on ? "bg-indigo" : "bg-ink-200")}>
      <span className="absolute top-[3px] h-5 w-5 rounded-full bg-white shadow transition-all" style={{ left: on ? 23 : 3 }} />
    </button>
  );
}
