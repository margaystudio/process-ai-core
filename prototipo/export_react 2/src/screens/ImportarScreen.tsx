// Importar documentación — 5-step batch import wizard.
// Steps: Configurar lote · Incorporar · Procesamiento · Revisión · Borradores creados.
import React, { useState, useEffect, useRef } from "react";
import { Icon, ICONS } from "../lib/data";
import { PrimaryButton } from "../components/ui";

const STEPS = ["Configurar lote", "Incorporar", "Procesamiento", "Revisión", "Borradores creados"];
const PIPELINE = ["Extrayendo contenido", "Identificando estructura", "Detectando entidades", "Construyendo relaciones", "Preparando consultas inteligentes"];

interface ImpDoc { id: string; file: string; ext: string; size: string; estado: "listo" | "revisar" | "bloqueado" | "excluido"; flags: { sev: "info" | "warn" | "error"; msg: string }[]; }
const DOCS: ImpDoc[] = [
  { id: "i1", file: "Cierre de caja nocturno.pdf", ext: "PDF", size: "1,2 MB", estado: "revisar", flags: [{ sev: "info", msg: "Parece una nueva versión de un documento existente." }] },
  { id: "i2", file: "Política de arqueo.docx", ext: "DOCX", size: "320 KB", estado: "revisar", flags: [{ sev: "warn", msg: "El contenido parece una Política, no un Procedimiento." }] },
  { id: "i3", file: "Manual de apertura.pdf", ext: "PDF", size: "3,4 MB", estado: "listo", flags: [] },
  { id: "i4", file: "Contrato proveedor Aguas SA.pdf", ext: "PDF", size: "880 KB", estado: "revisar", flags: [{ sev: "warn", msg: "Parece un contrato, no un procedimiento." }] },
  { id: "i5", file: "recibo_scan_0042.jpg", ext: "JPG", size: "2,1 MB", estado: "revisar", flags: [{ sev: "warn", msg: "Calidad de OCR baja." }] },
  { id: "i6", file: "backup_caja_old.pdf", ext: "PDF", size: "640 KB", estado: "bloqueado", flags: [{ sev: "error", msg: "Documento protegido por contraseña." }] },
];

function PersistentBanner() {
  return (
    <div className="mb-[22px] flex items-start gap-3 rounded-[13px] border border-indigo-border bg-indigo-tint px-[18px] py-3.5">
      <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] border border-indigo-border bg-surface text-indigo">
        <Icon d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4" size={18} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13px] font-extrabold text-ink-800">El documento original siempre se conserva</div>
        <div className="text-xs leading-relaxed text-ink-500">Process AI no modifica tus archivos. La IA genera una <b className="text-indigo">representación derivada</b> para búsqueda, relaciones y consultas inteligentes. La fuente oficial nunca cambia.</div>
      </div>
    </div>
  );
}

function StepRail({ step }: { step: number }) {
  return (
    <div className="mb-6 flex items-center border-b border-line bg-surface px-1 py-3">
      {STEPS.map((l, i) => {
        const n = i + 1, state = n < step ? "done" : n === step ? "current" : "todo";
        return (
          <React.Fragment key={l}>
            {i > 0 && <div className="mx-1.5 h-0.5 flex-1 rounded" style={{ background: n <= step ? "#9ECBB0" : "#E5E8EA" }} />}
            <div className="flex items-center gap-2">
              <span className={"grid h-7 w-7 flex-shrink-0 place-items-center rounded-full text-[12.5px] font-extrabold " + (state === "done" ? "bg-green text-white" : state === "current" ? "bg-ink-800 text-white" : "border-[1.5px] border-line-input bg-surface text-ink-300")}>
                {state === "done" ? <Icon d={ICONS.check} size={14} strokeWidth={3} /> : n}
              </span>
              <span className={"whitespace-nowrap text-[12.5px] font-bold " + (state === "current" ? "text-ink-900" : state === "done" ? "text-green-text" : "text-ink-300")}>{l}</span>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

export default function ImportarScreen() {
  const [step, setStep] = useState(1);
  const [progress, setProgress] = useState(0);
  const timer = useRef<any>(null);

  useEffect(() => {
    if (step !== 3) return;
    setProgress(0);
    timer.current = setInterval(() => setProgress((p) => (p >= 100 ? (clearInterval(timer.current), 100) : p + 5)), 300);
    return () => clearInterval(timer.current);
  }, [step]);

  const activeStage = progress >= 100 ? 5 : Math.min(4, Math.floor(progress / 20));

  return (
    <div className="flex h-full flex-col">
      <StepRail step={step} />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[880px] px-8 pb-[60px]">
          <PersistentBanner />

          {step === 1 && (
            <div className="animate-in">
              <Eyebrow n={1} title="Definí el contexto antes de incorporar archivos" sub="Estas configuraciones se aplican por defecto a todos los documentos del lote. Vas a poder ajustar cada documento en la revisión." />
              <Field label="Nombre de la importación" defaultValue="Manuales Operativos 2024" hint="Queda registrada como un lote para auditoría. Ej: Importación #24." />
              <div className="mb-[18px] grid gap-[18px] sm:grid-cols-2">
                <SelectField label="Carpeta destino" options={["Procesos / Caja", "RRHH / Liquidación", "Contratos / Proveedores"]} />
                <SelectField label="Tipo documental" options={["Procedimiento", "Política", "Contrato", "Manual"]} />
              </div>
              <CardRow title="Disponible para consultas inteligentes" desc="Si lo desactivás, Tyto y los asistentes no usarán estos documentos." on />
              <div className="mt-6 flex items-center justify-end gap-3">
                <span className="mr-auto text-[12.5px] text-ink-400">La IA nunca decide estos aspectos. La decisión siempre es tuya.</span>
                <PrimaryButton onClick={() => setStep(2)}>Incorporar documentación<Icon d="M5 12h14M13 6l6 6-6 6" size={17} strokeWidth={2.2} /></PrimaryButton>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-in">
              <Eyebrow n={2} title="Sumá la documentación existente" />
              <div className="mb-[18px] rounded-[16px] border-2 border-dashed border-line-input bg-surface-hover px-6 py-[46px] text-center">
                <span className="mx-auto mb-3.5 grid h-14 w-14 place-items-center rounded-[14px] bg-indigo-tint text-indigo"><Icon d={ICONS.upload} size={28} strokeWidth={1.8} /></span>
                <div className="text-base font-extrabold text-ink-900">Arrastrá tus archivos acá</div>
                <div className="mb-[18px] text-[13px] text-ink-400">o seleccioná archivos o una carpeta completa</div>
                <div className="flex items-center justify-center gap-2.5">
                  <button className="inline-flex h-[42px] items-center gap-2 rounded-[10px] bg-ink-800 px-[18px] text-[13.5px] font-bold text-white">Seleccionar archivos</button>
                  <button className="inline-flex h-[42px] items-center gap-2 rounded-[10px] border border-line-input bg-surface px-[18px] text-[13.5px] font-bold text-ink-700">Seleccionar carpeta</button>
                </div>
                <div className="mt-5 flex items-center justify-center gap-2 text-[11px] text-ink-300">
                  Formatos soportados: {["PDF", "DOCX", "IMÁGENES"].map((f) => <span key={f} className="rounded-md bg-line-soft px-2 py-0.5 text-[10.5px] font-extrabold text-ink-500">{f}</span>)}
                </div>
              </div>
              <div className="flex justify-end"><PrimaryButton onClick={() => setStep(3)} className="!bg-green">Procesar {DOCS.length} documentos<Icon d="M5 12h14M13 6l6 6-6 6" size={17} strokeWidth={2.2} /></PrimaryButton></div>
            </div>
          )}

          {step === 3 && (
            <div className="animate-in">
              <Eyebrow n={3} title="Process AI está preparando tus documentos" />
              <div className="mb-3.5 rounded-[14px] border border-line bg-surface p-5 shadow-card">
                <div className="mb-3 flex items-center justify-between"><span className="text-sm font-extrabold text-ink-900">{progress >= 100 ? "Lote procesado" : "Procesando documentos…"}</span><span className="font-mono text-[13px] font-extrabold text-indigo">{progress}%</span></div>
                <div className="h-2.5 overflow-hidden rounded-md bg-line-soft"><div className="h-full rounded-md bg-indigo transition-all" style={{ width: `${progress}%` }} /></div>
              </div>
              <div className="mb-3.5 rounded-[14px] border border-line bg-surface px-5 py-3.5 shadow-card">
                <div className="mb-3 text-[10.5px] font-bold uppercase tracking-[.06em] text-ink-300">Generando la representación para IA</div>
                <div className="flex flex-wrap items-center gap-1">
                  {PIPELINE.map((label, i) => {
                    const done = progress >= 100 || i < activeStage, active = i === activeStage && progress < 100;
                    return (
                      <React.Fragment key={label}>
                        {i > 0 && <Icon d={ICONS.chevronR} size={13} className="text-line-input" />}
                        <span className={"inline-flex items-center gap-1.5 rounded-pill px-2.5 py-[5px] text-[11.5px] font-bold " + (done ? "bg-green-bg text-green-text" : active ? "bg-indigo-tint text-indigo" : "bg-surface-track text-ink-300")}>
                          <span className="h-1.5 w-1.5 rounded-full" style={{ background: done ? "#2F9E62" : active ? "#48569C" : "#CDD2D4" }} />{label}
                        </span>
                      </React.Fragment>
                    );
                  })}
                </div>
              </div>
              <div className="flex justify-end"><PrimaryButton onClick={() => setStep(4)} className={progress < 100 ? "opacity-50" : ""}>Revisar lote completo<Icon d="M5 12h14M13 6l6 6-6 6" size={17} strokeWidth={2.2} /></PrimaryButton></div>
            </div>
          )}

          {step === 4 && <RevisionStep onBack={() => setStep(3)} onImport={() => setStep(5)} />}
          {step === 5 && <ResultStep />}
        </div>
      </div>
    </div>
  );
}

function RevisionStep({ onBack, onImport }: { onBack: () => void; onImport: () => void }) {
  const flagTone = (s: string) => (s === "error" ? { c: "#9B3A37", bg: "#FDF4F3", bd: "#E7B6B2" } : s === "warn" ? { c: "#7A5600", bg: "#FBF7EC", bd: "#F0DCA0" } : { c: "#48569C", bg: "rgba(173,185,223,.1)", bd: "#D2CFE6" });
  const estTone = (e: string) => (e === "listo" ? { c: "#1E7A47", bg: "#E7F4ED", bd: "#B9E0C9", l: "Listo" } : e === "revisar" ? { c: "#9A6A00", bg: "#FBF3DD", bd: "#F0DCA0", l: "Tiene observaciones" } : e === "bloqueado" ? { c: "#B0413E", bg: "#FDECEC", bd: "#E7B6B2", l: "Bloqueado" } : { c: "#8A8F91", bg: "#F2F4F5", bd: "#E5E8EA", l: "Excluido" });
  const created = DOCS.filter((d) => d.estado !== "bloqueado" && d.estado !== "excluido").length;
  return (
    <div className="animate-in">
      <Eyebrow n={4} title="Revisá el resultado y decidí" sub={`${DOCS.length} documentos · ${DOCS.filter((d) => d.flags.length).length} con sugerencias de la IA`} />
      <div className="mb-4 flex items-start gap-2.5 rounded-[12px] border border-amber-border bg-amber-bg px-4 py-3 text-[12.5px] leading-relaxed text-[#7A5600]">
        <Icon d="M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" size={18} className="flex-shrink-0" />
        <span>La IA <b>solo sugiere</b> — no toma decisiones de gobierno documental. Aceptá, ignorá o ajustá lo que corresponda. <b>Vos decidís.</b></span>
      </div>
      <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
        {DOCS.map((d) => {
          const et = estTone(d.estado);
          return (
            <div key={d.id} className="border-b border-line-softer last:border-0">
              <div className="grid items-center gap-3 px-5 py-3.5" style={{ gridTemplateColumns: "2.4fr 1.4fr 1fr" }}>
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-[30px] w-[30px] flex-shrink-0 place-items-center rounded-lg bg-indigo-tint text-[8.5px] font-extrabold text-indigo">{d.ext}</span>
                  <div className="min-w-0"><div className="truncate text-[13px] font-semibold text-ink-800">{d.file}</div><div className="text-[11px] text-ink-300">{d.size}</div></div>
                </div>
                <select className="h-[34px] rounded-lg border border-line bg-surface px-2 text-[12px] font-semibold"><option>Procedimiento</option><option>Política</option><option>Contrato</option></select>
                <span className="inline-flex items-center justify-self-center rounded-pill border px-2.5 py-1 text-[10.5px] font-extrabold" style={{ color: et.c, background: et.bg, borderColor: et.bd }}>{et.l}</span>
              </div>
              {d.flags.map((f, i) => {
                const t = flagTone(f.sev);
                return (
                  <div key={i} className="mx-5 mb-3 flex items-center gap-2.5 rounded-[9px] border px-3 py-2 text-[12px]" style={{ color: t.c, background: t.bg, borderColor: t.bd }}>
                    <Icon d="M12 9v4M12 17h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" size={14} className="flex-shrink-0" />
                    <span className="flex-1">{f.msg}</span>
                    <button className="rounded-md px-2 py-1 text-[11.5px] font-bold text-ink-400">Ignorar sugerencia</button>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
      {/* confirm summary */}
      <div className="mt-[18px] rounded-[14px] border border-line bg-surface p-5 shadow-card">
        <div className="mb-3.5 text-[13px] font-extrabold text-ink-900">Resultado del análisis</div>
        <div className="flex">
          {[[String(DOCS.length), "documentos analizados", "#232627"], [String(created), "borradores se crearán", "#1E7A47"], [String(DOCS.length - created), "excluidos", "#8A8F91"]].map(([v, l, c], i) => (
            <div key={i} className="flex-1 border-r border-line-soft px-4 last:border-0"><div className="text-2xl font-extrabold" style={{ color: c }}>{v}</div><div className="mt-0.5 text-xs text-ink-400">{l}</div></div>
          ))}
        </div>
      </div>
      <div className="mt-6 flex items-center justify-between gap-3">
        <button onClick={onBack} className="inline-flex h-[46px] items-center gap-1.5 rounded-[11px] border border-line bg-surface px-[18px] text-[13.5px] font-bold text-ink-500"><Icon d="M19 12H5M11 18l-6-6 6-6" size={16} />Atrás</button>
        <div className="flex items-center gap-3.5">
          <span className="text-[12.5px] text-ink-400">Se crearán como <b className="text-ink-500">borradores</b>. Nada se publica automáticamente.</span>
          <PrimaryButton onClick={onImport} className="!bg-green"><Icon d={ICONS.check} size={17} strokeWidth={2.4} />Importar {created} documentos</PrimaryButton>
        </div>
      </div>
    </div>
  );
}

function ResultStep() {
  const created = DOCS.filter((d) => d.estado !== "bloqueado").length;
  return (
    <div className="animate-in">
      <div className="mb-[26px] text-center">
        <span className="mx-auto mb-3.5 grid h-[60px] w-[60px] place-items-center rounded-full border border-green-border bg-green-bg text-green"><Icon d={ICONS.check} size={30} strokeWidth={2.6} /></span>
        <div className="text-[25px] font-extrabold text-ink-900">Borradores creados</div>
        <div className="text-[13.5px] text-ink-400">Tu documentación ya está en Process AI como borradores — todavía no son documentos oficiales.</div>
      </div>
      <div className="mb-[18px] flex items-start gap-3 rounded-[12px] border border-indigo-border bg-indigo-tint px-4 py-3.5 text-[12.5px] leading-relaxed text-indigo">
        <Icon d="M12 9v4M12 17h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" size={18} className="flex-shrink-0" />
        <span><b>Ningún documento fue publicado automáticamente.</b> Todos los borradores deberán seguir el circuito normal de revisión y aprobación antes de convertirse en documentos oficiales.</span>
      </div>
      <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
        <div className="flex items-center justify-between border-b border-line-soft px-[22px] py-4">
          <div className="flex items-center gap-2.5"><span className="rounded-md bg-indigo-tint px-2.5 py-[3px] font-mono text-[11px] font-extrabold text-indigo">Importación #24</span><span className="text-base font-extrabold text-ink-900">Manuales Operativos 2024</span></div>
          <span className="inline-flex items-center gap-1.5 rounded-pill border border-green-border bg-green-bg px-3 py-1 text-xs font-bold text-green-text"><span className="h-1.5 w-1.5 rounded-full bg-green-bright" />Finalizada</span>
        </div>
        <div className="grid grid-cols-3">
          {[["Fecha", "29/06/2026"], ["Usuario", "Martín Díaz"], ["Documentos", `${DOCS.length} en el lote`]].map(([l, v], i) => (
            <div key={i} className="border-r border-line-soft px-[22px] py-[18px] last:border-0"><div className="text-[11px] font-bold uppercase tracking-[.04em] text-ink-300">{l}</div><div className="mt-1 text-sm font-bold text-ink-800">{v}</div></div>
          ))}
        </div>
        <div className="grid grid-cols-2 border-t border-line-soft">
          <div className="flex items-center gap-3 border-r border-line-soft px-[22px] py-4"><span className="grid h-[38px] w-[38px] place-items-center rounded-[9px] bg-green-bg text-green"><Icon d={ICONS.check} size={20} strokeWidth={2.4} /></span><div><div className="text-xl font-extrabold text-ink-900">{created}</div><div className="text-xs text-ink-400">borradores creados</div></div></div>
          <div className="flex items-center gap-3 px-[22px] py-4"><span className="grid h-[38px] w-[38px] place-items-center rounded-[9px] bg-line-softer text-ink-400"><Icon d="M18 6L6 18M6 6l12 12" size={20} strokeWidth={2.2} /></span><div><div className="text-xl font-extrabold text-ink-900">{DOCS.length - created}</div><div className="text-xs text-ink-400">excluidos del lote</div></div></div>
        </div>
      </div>
      <div className="mt-6 flex items-center justify-center gap-3">
        <button className="inline-flex h-[46px] items-center gap-2 rounded-[11px] border border-line bg-surface px-5 text-sm font-bold text-ink-700"><Icon d={ICONS.plus} size={16} />Nueva importación</button>
        <PrimaryButton>Revisar borradores<Icon d="M5 12h14M13 6l6 6-6 6" size={17} strokeWidth={2.2} /></PrimaryButton>
      </div>
    </div>
  );
}

// ---- small form helpers ----
function Eyebrow({ n, title, sub }: { n: number; title: string; sub?: string }) {
  return (
    <div className="mb-5">
      <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Paso {n} · {STEPS[n - 1]}</div>
      <div className="text-2xl font-extrabold text-ink-900">{title}</div>
      {sub && <div className="mt-1.5 text-[13px] text-ink-400">{sub}</div>}
    </div>
  );
}
function Field({ label, defaultValue, hint }: { label: string; defaultValue?: string; hint?: string }) {
  return (
    <div className="mb-[18px] rounded-[14px] border border-line bg-surface p-5 shadow-card">
      <label className="mb-[7px] block text-[13px] font-bold text-ink-900">{label}</label>
      <input defaultValue={defaultValue} className="h-[46px] w-full rounded-[10px] border border-line-input px-3.5 text-sm font-semibold outline-none" />
      {hint && <div className="mt-[7px] text-[11.5px] text-ink-300">{hint}</div>}
    </div>
  );
}
function SelectField({ label, options }: { label: string; options: string[] }) {
  return (
    <div className="rounded-[14px] border border-line bg-surface p-5 shadow-card">
      <div className="mb-2 text-[13px] font-bold text-ink-900">{label}</div>
      <select className="h-[44px] w-full rounded-[10px] border border-line-input bg-surface px-3 text-[13.5px] font-semibold">{options.map((o) => <option key={o}>{o}</option>)}</select>
    </div>
  );
}
function CardRow({ title, desc, on }: { title: string; desc: string; on?: boolean }) {
  return (
    <div className="rounded-[14px] border border-line bg-surface p-5 shadow-card">
      <div className="flex items-start gap-3">
        <div className="flex-1"><div className="text-[13px] font-bold text-ink-900">{title}</div><div className="text-[12px] leading-snug text-ink-400">{desc}</div></div>
        <span className={"relative h-[26px] w-[46px] flex-shrink-0 rounded-pill " + (on ? "bg-indigo" : "bg-ink-200")}><span className="absolute top-[3px] h-5 w-5 rounded-full bg-white shadow transition-all" style={{ left: on ? 23 : 3 }} /></span>
      </div>
    </div>
  );
}
