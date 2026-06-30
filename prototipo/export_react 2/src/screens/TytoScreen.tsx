// Tyto — knowledge assistant. Initial screen + conversation + context panel + states.
// NOT a generic chatbot: it's a corporate knowledge browser. Always cites official docs.
import React, { useState } from "react";
import { Icon, ICONS } from "../lib/data";

type Conf = "alta" | "media" | "baja";
type SpecialState = "ok" | "multiple" | "contradictory" | "outdated" | "archived" | "none";

interface Scenario {
  q: string; tag: string; topic: string; state: SpecialState; conf: Conf | null;
  answer: string[]; docs: { name: string; carpeta: string; estado: string; version: string }[];
  procesos: string[]; sistemas: string[]; personas: string[]; conceptos: string[];
}

const SCENARIOS: Record<string, Scenario> = {
  cierre: { q: "¿Cómo se hace el cierre de caja?", tag: "Procesos › Caja", topic: "Cierre de caja", state: "ok", conf: "alta",
    answer: ["El cierre de caja se realiza al finalizar el turno en tres pasos: arqueo de efectivo, cierre de lote del POS y registro de diferencias.¹", "Se cuenta el efectivo frente al supervisor y se separa el fondo fijo. Luego se ejecuta el cierre de lote (F4 → Cierre) y se verifica el total contra el sistema.²"],
    docs: [{ name: "Cierre de caja", carpeta: "Procesos › Caja", estado: "Aprobado", version: "v3" }, { name: "Arqueo de turno", carpeta: "Procesos › Caja", estado: "Aprobado", version: "v2" }],
    procesos: ["Apertura de caja", "Relevo de turno"], sistemas: ["POS", "Sistema de caja"], personas: ["Encargado de turno", "Supervisor"], conceptos: ["Arqueo", "Fondo fijo", "Cierre de lote"] },
  devoluciones: { q: "¿Cuál es la política de devoluciones?", tag: "Comercial", topic: "Devoluciones", state: "contradictory", conf: "baja",
    answer: ["Encontré dos versiones con criterios distintos sobre el plazo de devolución.", "La versión oficial vigente (v2) indica 30 días corridos.¹ Una versión anterior, ya archivada, menciona 15 días.² Te recomiendo confirmar con el responsable comercial antes de aplicar."],
    docs: [{ name: "Política de devoluciones", carpeta: "Comercial", estado: "Aprobado", version: "v2" }, { name: "Política de devoluciones (anterior)", carpeta: "Comercial", estado: "Archivado", version: "v1" }],
    procesos: ["Atención al cliente"], sistemas: ["Sistema de ventas"], personas: ["Responsable comercial"], conceptos: ["Plazo de devolución", "Versión vigente"] },
};

const CONF_META: Record<Conf, { l: string; c: string; bg: string; bd: string }> = {
  alta: { l: "Confianza alta", c: "#1E7A47", bg: "#E7F4ED", bd: "#B9E0C9" },
  media: { l: "Confianza media", c: "#9A6A00", bg: "#FBF3DD", bd: "#F0DCA0" },
  baja: { l: "Confianza baja", c: "#B0413E", bg: "#FDECEC", bd: "#E7B6B2" },
};

const FREQUENT = ["cierre", "devoluciones"];
const FOLDERS = ["Todas", "Procesos", "RRHH", "Comercial", "Seguridad", "Contratos"];

export default function TytoScreen({ embedded = false }: { embedded?: boolean }) {
  const [mode, setMode] = useState<"home" | "chat">("home");
  const [thread, setThread] = useState<{ role: "user" | "tyto"; text?: string; key?: string }[]>([]);
  const [folder, setFolder] = useState("Todas");

  const ask = (key: string) => { setThread((t) => [...t, { role: "user", text: SCENARIOS[key].q }, { role: "tyto", key }]); setMode("chat"); };
  const lastTyto = [...thread].reverse().find((m) => m.role === "tyto");
  const lastSc = lastTyto ? SCENARIOS[lastTyto.key!] : null;
  const showCtx = mode === "chat" && lastSc && lastSc.state !== "none";

  return (
    <div className="flex h-full flex-col bg-surface">
      {!embedded && (
        <div className="z-10 flex h-[58px] flex-shrink-0 items-center gap-3 border-b border-line bg-surface px-[22px]">
          <span className="inline-flex items-center gap-1.5 text-[13.5px] font-bold text-indigo"><Icon d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0" size={17} />Tyto</span>
          <span className="text-[11.5px] text-ink-300">Asistente de conocimiento</span>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col bg-surface-app">
          {mode === "home" ? (
            <div className="flex-1 overflow-y-auto">
              <div className="mx-auto max-w-[780px] px-[30px] pb-[70px] pt-[60px]">
                <div className="mb-[30px] text-center">
                  <span className="mb-[18px] inline-grid h-[60px] w-[60px] place-items-center rounded-[16px] bg-indigo text-white"><Icon d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0" size={30} /></span>
                  <div className="text-[28px] font-extrabold text-ink-900">Preguntá al conocimiento de tu organización</div>
                  <div className="mx-auto mt-2.5 max-w-md text-sm leading-relaxed text-ink-400">Tyto responde solo con <b className="text-ink-500">documentos oficiales aprobados</b>. Cita siempre la fuente y nunca inventa información.</div>
                </div>

                <div className="mb-3.5 flex items-center gap-2 rounded-[14px] border-[1.5px] border-line-input bg-surface p-[7px_7px_7px_16px] shadow-raised">
                  <Icon d={ICONS.search} size={20} className="flex-shrink-0 text-ink-300" />
                  <input placeholder="Escribí tu pregunta sobre procesos, políticas, contratos…" className="min-w-0 flex-1 bg-transparent text-[15px] outline-none" />
                  <button onClick={() => ask("cierre")} className="inline-flex h-[42px] items-center gap-1.5 rounded-[10px] bg-ink-800 px-[18px] text-sm font-bold text-white">Preguntar</button>
                </div>

                <div className="mb-9 flex flex-wrap items-center gap-2">
                  <span className="text-[11.5px] text-ink-300">Buscar en:</span>
                  {FOLDERS.map((f) => <button key={f} onClick={() => setFolder(f)} className={"h-[30px] rounded-pill px-3 text-xs font-bold " + (folder === f ? "border-[1.5px] border-indigo-light bg-indigo-tint text-indigo" : "border border-line bg-surface text-ink-500")}>{f}</button>)}
                </div>

                <div className="mb-3 text-xs font-bold uppercase tracking-[.06em] text-ink-400">Preguntas frecuentes</div>
                <div className="grid grid-cols-2 gap-3">
                  {FREQUENT.map((k) => (
                    <button key={k} onClick={() => ask(k)} className="flex items-start gap-3 rounded-[13px] border border-line bg-surface px-4 py-[15px] text-left shadow-card hover:border-indigo-light">
                      <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-[9px] bg-indigo-tint text-indigo"><Icon d={ICONS.search} size={16} /></span>
                      <span className="min-w-0"><span className="block text-[13.5px] font-bold leading-snug text-ink-800">{SCENARIOS[k].q}</span><span className="mt-0.5 block text-[11.5px] text-ink-300">{SCENARIOS[k].tag}</span></span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto">
              <div className="mx-auto max-w-[780px] px-[30px] pb-10 pt-7">
                {embedded && <div className="mb-1.5 flex justify-end"><button onClick={() => { setThread([]); setMode("home"); }} className="inline-flex h-8 items-center gap-1.5 rounded-[9px] border border-line bg-surface px-3 text-xs font-bold text-ink-700"><Icon d={ICONS.plus} size={14} />Nueva consulta</button></div>}
                {thread.map((m, i) => m.role === "user"
                  ? <div key={i} className="mb-[18px] flex justify-end"><div className="max-w-[75%] rounded-[14px_14px_4px_14px] bg-ink-800 px-4 py-[11px] text-sm font-semibold leading-normal text-white">{m.text}</div></div>
                  : <TytoMessage key={i} sc={SCENARIOS[m.key!]} />
                )}
              </div>
            </div>
          )}

          {mode === "chat" && (
            <div className="flex-shrink-0 border-t border-line bg-surface px-[30px] py-3.5">
              <div className="mx-auto flex max-w-[780px] items-center gap-2 rounded-[13px] border-[1.5px] border-line bg-surface-app p-[6px_6px_6px_15px]">
                <input placeholder="Seguí preguntando sobre esta respuesta…" className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
                <button className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-[10px] bg-ink-800 text-white"><Icon d="M5 12h14M13 6l6 6-6 6" size={17} strokeWidth={2.2} /></button>
              </div>
              <div className="mt-2 text-center text-[10.5px] text-ink-200">Tyto consulta la representación derivada. El documento oficial siempre es la fuente de verdad.</div>
            </div>
          )}
        </div>

        {showCtx && <ContextPanel sc={lastSc!} />}
      </div>
    </div>
  );
}

function TytoMessage({ sc }: { sc: Scenario }) {
  const cm = sc.conf ? CONF_META[sc.conf] : null;
  const banner = bannerFor(sc.state);
  return (
    <div className="mb-[26px] animate-in">
      <div className="mb-[11px] flex items-center gap-2.5">
        <span className="grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-[7px] bg-indigo text-white"><Icon d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0" size={15} /></span>
        <span className="text-[13px] font-extrabold text-ink-900">Tyto</span>
        {cm && <span className="ml-auto inline-flex items-center gap-1.5 rounded-pill border px-3 py-[3px] text-[11px] font-bold" style={{ color: cm.c, background: cm.bg, borderColor: cm.bd }}><span className="h-1.5 w-1.5 rounded-full" style={{ background: cm.c }} />{cm.l}</span>}
      </div>
      {banner && (
        <div className="mb-3.5 flex items-start gap-2.5 rounded-[11px] border px-3.5 py-[11px]" style={{ color: banner.c, background: banner.bg, borderColor: banner.bd }}>
          <Icon d={banner.icon} size={16} className="mt-px flex-shrink-0" />
          <div><div className="text-[12.5px] font-extrabold">{banner.title}</div><div className="text-xs leading-relaxed opacity-90">{banner.text}</div></div>
        </div>
      )}
      <div className="text-[14.5px] leading-relaxed text-ink-900">{sc.answer.map((p, i) => <div key={i} className="mb-2.5">{p}</div>)}</div>

      {/* sources */}
      <div className="mt-4">
        <div className="mb-2.5 text-[11px] font-bold uppercase tracking-[.05em] text-ink-400">Fuentes oficiales · {sc.docs.length}</div>
        <div className="flex flex-col gap-2">
          {sc.docs.map((d, i) => {
            const tone = d.estado === "Aprobado" ? { c: "#1E7A47", bg: "#E7F4ED", bd: "#B9E0C9" } : { c: "#8A8F91", bg: "#F2F4F5", bd: "#E5E8EA" };
            return (
              <button key={i} className="flex items-center gap-3 rounded-[11px] border border-line bg-surface px-3.5 py-3 text-left hover:border-indigo-light">
                <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-[7px] bg-indigo-tint text-[10px] font-extrabold text-indigo">{i + 1}</span>
                <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-bold text-ink-800">{d.name}</div><div className="text-[11px] text-ink-300">{d.carpeta}</div></div>
                <span className="rounded-pill border px-2 py-0.5 text-[10px] font-extrabold" style={{ color: tone.c, background: tone.bg, borderColor: tone.bd }}>{d.estado}</span>
                <span className="font-mono text-[10.5px] font-bold text-ink-400">{d.version}</span>
                <Icon d={ICONS.chevronR} size={15} className="text-ink-200" />
              </button>
            );
          })}
        </div>
      </div>

      {/* actions */}
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {[["Abrir documento", true], ["Copiar respuesta", false], ["Ver procedimiento", false]].map(([l, primary]) => (
          <button key={l as string} className={"inline-flex h-[34px] items-center gap-1.5 rounded-[9px] px-3 text-xs font-bold " + (primary ? "bg-ink-800 text-white" : "border border-line bg-surface text-ink-700")}>{l}</button>
        ))}
      </div>
    </div>
  );
}

function ContextPanel({ sc }: { sc: Scenario }) {
  const sections: { title: string; color: string; items: string[] }[] = [
    { title: "Documentos utilizados", color: "#48569C", items: sc.docs.map((d) => d.name) },
    { title: "Procesos relacionados", color: "#2F9E62", items: sc.procesos },
    { title: "Sistemas", color: "#2E8B8B", items: sc.sistemas },
    { title: "Personas y roles", color: "#8B5CC2", items: sc.personas },
    { title: "Conceptos detectados", color: "#6A6E70", items: sc.conceptos },
  ].filter((s) => s.items.length);

  return (
    <aside className="w-[340px] flex-shrink-0 overflow-y-auto border-l border-line bg-surface">
      <div className="px-5 pb-10 pt-5">
        <div className="mb-1.5 text-xs font-extrabold uppercase tracking-[.05em] text-ink-400">Contexto de la respuesta</div>
        <div className="mb-[18px] text-[11.5px] leading-relaxed text-ink-300">Conocimiento relacionado detectado a partir de las fuentes citadas.</div>
        {/* mini knowledge graph */}
        <div className="mb-[18px] rounded-[13px] border border-line-soft bg-surface-hover p-2"><KnowledgeGraph sc={sc} /></div>
        {sections.map((sec) => (
          <div key={sec.title} className="mb-[18px]">
            <div className="mb-2.5 flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: sec.color }} /><span className="text-[12.5px] font-extrabold text-ink-900">{sec.title}</span><span className="text-[10.5px] font-bold text-ink-300">{sec.items.length}</span></div>
            <div className="flex flex-wrap gap-1.5">
              {sec.items.map((it, i) => <button key={i} className="rounded-lg border border-line-soft bg-surface-softer px-2.5 py-[5px] text-[11.5px] font-semibold text-ink-700" style={{ background: "#F4F5F6" }}>{it}</button>)}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

function KnowledgeGraph({ sc }: { sc: Scenario }) {
  const cx = 160, cy = 100, ring = 72;
  const sats = [
    ...sc.docs.slice(0, 2).map((d) => ({ label: d.name, color: "#2F9E62" })),
    ...sc.procesos.slice(0, 1).map((p) => ({ label: p, color: "#48569C" })),
    ...sc.personas.slice(0, 1).map((p) => ({ label: p, color: "#8B5CC2" })),
  ];
  const n = Math.max(sats.length, 1);
  const nodes = sats.map((s, i) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / n; return { ...s, x: cx + ring * Math.cos(a), y: cy + ring * Math.sin(a) }; });
  return (
    <svg width="100%" height={200} viewBox="0 0 320 200">
      {nodes.map((nd, i) => <line key={"l" + i} x1={cx} y1={cy} x2={nd.x} y2={nd.y} stroke="#DCE0E2" strokeWidth={1.5} />)}
      {nodes.map((nd, i) => (
        <g key={"n" + i}>
          <circle cx={nd.x} cy={nd.y} r={6} fill={nd.color} />
          <text x={nd.x} y={nd.y < cy ? nd.y - 11 : nd.y + 18} fontSize={8.5} fill="#6A6E70" textAnchor="middle" fontWeight={600} fontFamily="Plus Jakarta Sans">{nd.label.length > 17 ? nd.label.slice(0, 16) + "…" : nd.label}</text>
        </g>
      ))}
      <circle cx={cx} cy={cy} r={13} fill="rgba(72,86,156,.14)" />
      <circle cx={cx} cy={cy} r={8} fill="#48569C" />
      <text x={cx} y={cy + 30} fontSize={9.5} fill="#232627" textAnchor="middle" fontWeight={800} fontFamily="Plus Jakarta Sans">{sc.topic}</text>
    </svg>
  );
}

function bannerFor(state: SpecialState) {
  switch (state) {
    case "multiple": return { c: "#48569C", bg: "rgba(173,185,223,.12)", bd: "#D2CFE6", icon: "M3 3h13v13H3zM8 8h13v13H8z", title: "Respuesta combinada", text: "Esta respuesta integra varios documentos oficiales. Revisá cada fuente citada." };
    case "contradictory": return { c: "#B0413E", bg: "#FDECEC", bd: "#E7B6B2", icon: "M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z", title: "Información contradictoria", text: "Hay diferencias entre versiones. Tyto prioriza la versión oficial vigente sobre la archivada." };
    case "outdated": return { c: "#9A6A00", bg: "#FBF3DD", bd: "#F0DCA0", icon: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7v5l3 2", title: "Documento desactualizado", text: "El documento principal no se actualiza desde 2021. Verificá su vigencia antes de aplicarlo." };
    case "archived": return { c: "#6A6E70", bg: "#F2F4F5", bd: "#E5E8EA", icon: "M3 4h18v4H3zM5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4", title: "Documento archivado", text: "La fuente citada está archivada y puede no reflejar la situación vigente." };
    default: return null;
  }
}
