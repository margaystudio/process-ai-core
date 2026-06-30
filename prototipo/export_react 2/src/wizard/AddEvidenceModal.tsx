// AddEvidenceModal — "Agregar evidencia" modal. Two modes:
//   • "Archivo existente": pick type → select file → processing steps → adds evidence
//   • "Grabar audio": idle → recording (timer) → processing → done → describe → add
// Drives the processing pipelines from EVIDENCE_TYPES[tipo].steps.
import React, { useState, useEffect, useRef } from "react";
import { EVIDENCE_TYPES, EvidenceTipo, Evidence, evidenceIconPath, formatSecs, Icon } from "./data";
import { ProcessingSteps } from "./ProcessingSteps";

type Mode = "import" | "record";
type RecPhase = "idle" | "rec" | "saving" | "done";
const TYPES: EvidenceTipo[] = ["Audio", "Video", "PDF", "Imagen", "Documento"];

export function AddEvidenceModal({ onClose, onAdd }: { onClose: () => void; onAdd: (e: Evidence) => void }) {
  const [mode, setMode] = useState<Mode>("import");
  // import state
  const [tipo, setTipo] = useState<EvidenceTipo>("Audio");
  const [desc, setDesc] = useState("");
  const [fileName, setFileName] = useState("");
  const [saving, setSaving] = useState(false);
  const [fmStep, setFmStep] = useState(0);
  // record state
  const [recPhase, setRecPhase] = useState<RecPhase>("idle");
  const [recSecs, setRecSecs] = useState(0);
  const [recStep, setRecStep] = useState(0);
  const [recDesc, setRecDesc] = useState("");
  const recTimer = useRef<any>(null);
  const stepTimer = useRef<any>(null);

  const def = EVIDENCE_TYPES[tipo];
  useEffect(() => () => { clearInterval(recTimer.current); clearInterval(stepTimer.current); }, []);

  // ---- import: run processing pipeline then add ----
  const submitFile = () => {
    if (!fileName) return;
    setSaving(true); setFmStep(0);
    let s = 0;
    stepTimer.current = setInterval(() => {
      s += 1;
      if (s >= 4) { clearInterval(stepTimer.current); setFmStep(4); setTimeout(() => { onAdd({ id: "a-" + Date.now(), tipo, title: desc.trim() || fileName, processing: false, chips: def.chips }); onClose(); }, 420); }
      else setFmStep(s);
    }, 500);
  };

  // ---- record flow ----
  const startRec = () => { setRecPhase("rec"); setRecSecs(0); recTimer.current = setInterval(() => setRecSecs((n) => n + 1), 1000); };
  const stopRec = () => { clearInterval(recTimer.current); setRecPhase("saving"); setRecStep(0); let s = 0; stepTimer.current = setInterval(() => { s += 1; if (s >= 4) { clearInterval(stepTimer.current); setRecStep(4); setTimeout(() => setRecPhase("done"), 420); } else setRecStep(s); }, 500); };
  const addRecording = () => { onAdd({ id: "a-" + Date.now(), tipo: "Audio", title: recDesc.trim() || "Grabación de audio", processing: false, chips: ["Audio transcripto", "Idioma: ES", formatSecs(recSecs)] }); onClose(); };

  return (
    <div onClick={onClose} className="fixed inset-0 z-[120] flex items-center justify-center bg-[rgba(20,28,33,.45)] p-6">
      <div onClick={(e) => e.stopPropagation()} className="max-h-[92vh] w-[486px] max-w-full overflow-y-auto rounded-[18px] bg-surface p-[26px_28px] shadow-modal animate-in">
        {/* header */}
        <div className="mb-1 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo"><Icon d={evidenceIconPath(tipo)} size={18} /></span>
            <span className="text-xl font-extrabold text-ink-900">Agregar evidencia</span>
          </div>
          <button onClick={onClose} className="grid h-7 w-7 place-items-center rounded-lg bg-line-softer"><Icon d="M18 6L6 18M6 6l12 12" size={14} className="text-ink-400" strokeWidth={2.2} /></button>
        </div>
        <div className="mb-4 text-[12.5px] text-ink-400">Sumá material existente o grabá un audio. El sistema lo procesa automáticamente.</div>

        {/* mode segmented */}
        <div className="mb-5 flex gap-1 rounded-[11px] border border-line-soft bg-line-softer p-1">
          {([["import", "Archivo existente", "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"], ["record", "Grabar audio", "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4"]] as const).map(([m, label, d]) => (
            <button key={m} onClick={() => setMode(m)} className={"flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-[13px] font-bold " + (mode === m ? "bg-surface text-ink-800 shadow-card" : "text-ink-400")}>
              <Icon d={d} size={15} />{label}
            </button>
          ))}
        </div>

        {/* IMPORT MODE */}
        {mode === "import" && (saving ? (
          <ProcessingSteps steps={def.steps} current={fmStep} />
        ) : (
          <>
            <div className="mb-[9px] text-[12.5px] font-bold text-ink-900">Tipo de evidencia</div>
            <div className="mb-3.5 flex flex-wrap items-center gap-[7px]">
              {TYPES.map((t) => {
                const active = t === tipo;
                return (
                  <button key={t} onClick={() => { setTipo(t); setFileName(""); }} className={"inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-[12.5px] font-bold " + (active ? "border-indigo-light bg-indigo-tint text-indigo" : "border-line bg-surface text-ink-500")}>
                    <Icon d={evidenceIconPath(t)} size={14} />{t}
                  </button>
                );
              })}
            </div>
            <div className="mb-4 text-[11.5px] leading-snug text-ink-400">{def.help} · Formatos: {def.formats}</div>

            <div className="mb-[7px] text-[12.5px] font-bold text-ink-900">Descripción <span className="font-medium text-ink-400">(opcional)</span></div>
            <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder={def.placeholder} className="mb-[18px] h-11 w-full rounded-[10px] border border-line-input px-[13px] text-[13.5px] outline-none" />

            <div className="mb-2 text-[12.5px] font-bold text-ink-900">Evidencia</div>
            {!fileName ? (
              <div className="rounded-xl border-[1.5px] border-dashed border-line-input bg-surface-hover px-5 py-[30px] text-center">
                <div className="mb-3 text-sm font-bold text-ink-500">Arrastrá tu evidencia aquí</div>
                <button onClick={() => setFileName(def.sample)} className="h-10 rounded-[9px] border border-line-input bg-surface px-[18px] text-[13.5px] font-semibold text-ink-800">Seleccionar archivo</button>
              </div>
            ) : (
              <div className="flex items-center gap-[11px] rounded-xl border-[1.5px] border-green-border bg-[#F1F9F4] p-[13px_15px] animate-in">
                <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] bg-green"><Icon d="M20 6L9 17l-5-5" size={17} className="text-white" strokeWidth={2.4} /></span>
                <div className="min-w-0 flex-1"><div className="truncate text-[13.5px] font-bold text-ink-900">{fileName}</div><div className="text-[11.5px] text-[#3E7D5A]">Lista para subir</div></div>
                <button onClick={() => setFileName("")} className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-[7px] border border-[#C7E3D2] bg-surface"><Icon d="M18 6L6 18M6 6l12 12" size={13} className="text-ink-500" strokeWidth={2.2} /></button>
              </div>
            )}
            <div className="mt-2 text-[11.5px] text-ink-400">Máximo: 25.00 MB</div>

            <div className="mt-[22px] flex gap-[11px]">
              <button onClick={submitFile} disabled={!fileName} className={"h-11 flex-1 rounded-[10px] text-sm font-bold text-white " + (fileName ? "bg-ink-800" : "cursor-not-allowed bg-ink-300")}>Subir evidencia</button>
              <button onClick={onClose} className="h-11 flex-1 rounded-[10px] border border-line-input bg-surface text-sm font-semibold text-ink-700">Cancelar</button>
            </div>
            <div className="mt-3.5 text-center text-[11.5px] leading-relaxed text-ink-300">Esta evidencia se utilizará como contexto para generar o actualizar el documento.</div>
          </>
        ))}

        {/* RECORD MODE */}
        {mode === "record" && (
          <>
            {recPhase === "idle" && (
              <div className="flex flex-col items-center gap-3.5 py-[14px]">
                <button onClick={startRec} className="grid h-[84px] w-[84px] place-items-center rounded-full bg-red shadow-[0_10px_26px_rgba(203,66,66,.32)]"><Icon d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4" size={34} className="text-white" /></button>
                <div className="text-[13.5px] font-semibold text-ink-700">Tocá para empezar a grabar</div>
                <RecordHint />
              </div>
            )}
            {recPhase === "rec" && (
              <div className="flex flex-col items-center gap-4 py-2">
                <span className="relative grid h-[84px] w-[84px] place-items-center">
                  <span className="absolute inset-0 animate-ping rounded-full bg-[rgba(203,66,66,.4)]" />
                  <span className="relative grid h-16 w-16 place-items-center rounded-full bg-red"><Icon d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4" size={26} className="text-white" /></span>
                </span>
                <div className="font-mono text-[26px] font-extrabold text-ink-900">{formatSecs(recSecs)}</div>
                <button onClick={stopRec} className="inline-flex h-11 items-center gap-2 rounded-pill bg-ink-800 px-[22px] text-sm font-bold text-white"><span className="h-3 w-3 rounded-[3px] bg-white" />Detener</button>
                <RecordHint />
              </div>
            )}
            {recPhase === "saving" && <ProcessingSteps steps={["Audio guardado", "Transcribiendo…", "Detectando idioma…", "Listo"]} current={recStep} />}
            {recPhase === "done" && (
              <>
                <div className="mb-4 flex items-center gap-[11px] rounded-xl border-[1.5px] border-green-border bg-[#F1F9F4] p-[13px_15px] animate-in">
                  <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-[9px] bg-green"><Icon d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4" size={18} className="text-white" /></span>
                  <div className="min-w-0 flex-1"><div className="text-[13.5px] font-bold text-ink-900">Grabación lista</div><div className="font-mono text-[11.5px] text-[#3E7D5A]">audio · {formatSecs(recSecs)}</div></div>
                  <button onClick={() => { setRecPhase("idle"); setRecSecs(0); setRecDesc(""); }} title="Regrabar" className="grid h-[30px] w-[30px] flex-shrink-0 place-items-center rounded-[7px] border border-[#C7E3D2] bg-surface"><Icon d="M3 2v6h6M3.51 15a9 9 0 1 0 2.13-9.36L3 8" size={14} className="text-ink-500" /></button>
                </div>
                <div className="mb-[7px] text-[12.5px] font-bold text-ink-900">Descripción <span className="font-medium text-ink-400">(opcional)</span></div>
                <input value={recDesc} onChange={(e) => setRecDesc(e.target.value)} placeholder="Ej: Entrevista al cajero" className="mb-[18px] h-11 w-full rounded-[10px] border border-line-input px-[13px] text-[13.5px] outline-none" />
                <div className="flex gap-[11px]">
                  <button onClick={addRecording} className="h-11 flex-1 rounded-[10px] bg-green text-sm font-bold text-white">Agregar evidencia</button>
                  <button onClick={() => setMode("import")} className="h-11 flex-1 rounded-[10px] border border-line-input bg-surface text-sm font-semibold text-ink-700">Volver</button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function RecordHint() {
  return (
    <div className="flex w-full items-start gap-2 rounded-[10px] border border-line-soft bg-surface-app p-[11px_13px]">
      <Icon d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z" size={15} className="mt-px flex-shrink-0 text-indigo" />
      <span className="text-[11.5px] leading-relaxed text-ink-500">El audio se transcribirá automáticamente y se incorporará como evidencia del documento.</span>
    </div>
  );
}
