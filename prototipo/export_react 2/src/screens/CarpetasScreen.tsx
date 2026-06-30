// Carpetas — folder administration / document governance.
// Tree (left) + detail with tabs (right). Inheritance is the key concept.
import React, { useState } from "react";
import { FOLDERS, Folder, folderPath, FOLDER_ICON_PATHS, Icon, ICONS } from "../lib/data";
import { TintPill } from "../components/ui";

type Tab = "resumen" | "general" | "gobierno" | "tyto" | "permisos" | "ia" | "actividad";
const TABS: [Tab, string][] = [["resumen", "Resumen"], ["general", "General"], ["gobierno", "Gobierno"], ["tyto", "Tyto"], ["permisos", "Permisos"], ["ia", "IA"], ["actividad", "Actividad"]];

const STATS = [["Documentos", "32"], ["Aprobados", "26"], ["Borradores", "4"], ["Pendientes", "2"], ["Relaciones nuevas", "8"], ["Confianza prom.", "92%"]];

// inheritance state per config block: "base" | "heredado" | "personalizado"
function Inheritance({ kind, from }: { kind: "base" | "heredado" | "personalizado"; from?: string }) {
  if (kind === "personalizado") return <TintPill color="#9A6A00">Personalizado</TintPill>;
  if (kind === "heredado") return <TintPill color="#48569C">Heredado de {from}</TintPill>;
  return <TintPill color="#8A8F91">Configuración base</TintPill>;
}

export default function CarpetasScreen() {
  const [selId, setSelId] = useState("caja");
  const [tab, setTab] = useState<Tab>("resumen");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ procesos: true, contratos: true });
  const [modal, setModal] = useState(false);
  const sel = FOLDERS.find((f) => f.id === selId)!;
  const children = (pid: string | null) => FOLDERS.filter((f) => f.parent === pid);

  const renderRow = (f: Folder, depth: number): React.ReactNode => {
    const kids = children(f.id);
    const open = !!expanded[f.id];
    return (
      <React.Fragment key={f.id}>
        <div className="flex w-full items-center gap-px" style={{ paddingLeft: depth * 14 }}>
          <span onClick={() => kids.length && setExpanded((e) => ({ ...e, [f.id]: !e[f.id] }))} className={"grid h-7 w-[18px] flex-shrink-0 place-items-center transition-transform " + (kids.length ? "cursor-pointer" : "pointer-events-none opacity-0")} style={{ transform: `rotate(${open ? 90 : 0}deg)` }}>
            <Icon d={ICONS.chevronR} size={11} className="text-ink-400" strokeWidth={2.6} />
          </span>
          <button onClick={() => setSelId(f.id)} className={"flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-[7px] text-[12.5px] " + (selId === f.id ? "bg-indigo-tint font-bold text-ink-800" : "font-semibold text-ink-700 hover:bg-surface-hover")}>
            <span style={{ color: f.color }}><Icon d={FOLDER_ICON_PATHS[f.icon]} size={14} /></span>
            <span className="min-w-0 flex-1 truncate text-left">{f.name}</span>
            <span className="text-[10.5px] font-bold text-ink-300">{f.docs}</span>
          </button>
        </div>
        {open && kids.map((k) => renderRow(k, depth + 1))}
      </React.Fragment>
    );
  };

  return (
    <div className="flex min-h-full items-stretch">
      {/* tree */}
      <div className="sticky top-0 max-h-screen w-[248px] flex-shrink-0 self-start overflow-y-auto border-r border-line bg-surface p-3 pt-[22px]">
        <div className="mb-3 flex items-center justify-between px-2">
          <span className="text-[11px] font-bold uppercase tracking-[.08em] text-ink-400">Estructura</span>
          <button onClick={() => setModal(true)} className="grid h-6 w-6 place-items-center rounded-md text-ink-400 hover:bg-surface-hover"><Icon d="M12 5v14M5 12h14" size={15} /></button>
        </div>
        {children(null).map((f) => renderRow(f, 0))}
        <p className="mt-3 px-2 text-[10.5px] leading-relaxed text-ink-300">Arrastrá una carpeta sobre otra para reparentar.</p>
      </div>

      {/* detail */}
      <div className="min-w-0 flex-1 px-8 pb-[50px] pt-7">
        {/* header */}
        <div className="flex items-start gap-3.5">
          <span className="grid h-12 w-12 flex-shrink-0 place-items-center rounded-[13px]" style={{ color: sel.color, background: `${sel.color}1f` }}><Icon d={FOLDER_ICON_PATHS[sel.icon]} size={24} /></span>
          <div className="min-w-0 flex-1">
            <div className="text-xs text-ink-400">{folderPath(sel).split(" / ").join(" › ")}</div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-[23px] font-extrabold text-ink-900">{sel.name}</h1>
              <span className="inline-flex items-center gap-1.5 rounded-pill border border-green-border bg-green-bg px-2.5 py-[3px] text-[11px] font-bold text-green-text"><span className="h-1.5 w-1.5 rounded-full bg-green-bright" />Activa</span>
            </div>
            <div className="mt-1 text-[13px] text-ink-400">Dominio de conocimiento de operación de caja. Actualizada hace 2 horas.</div>
          </div>
        </div>

        {/* stats strip */}
        <div className="mt-5 flex flex-wrap gap-x-8 gap-y-3 rounded-[13px] border border-line bg-surface px-5 py-4 shadow-card">
          {STATS.map(([l, v]) => (
            <div key={l}><div className="text-lg font-extrabold text-ink-900">{v}</div><div className="text-[11px] text-ink-400">{l}</div></div>
          ))}
        </div>

        {/* tabs */}
        <div className="mt-6 flex gap-1 border-b border-line">
          {TABS.map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={"-mb-px border-b-2 px-3.5 py-2.5 text-[13px] font-bold transition-colors " + (tab === k ? "border-ink-800 text-ink-900" : "border-transparent text-ink-400")}>{l}</button>
          ))}
        </div>

        <div className="mt-6">
          {tab === "gobierno" && <GobiernoTab />}
          {tab === "permisos" && <PermisosTab />}
          {tab === "ia" && <IaTab />}
          {tab === "tyto" && <TytoTab />}
          {(tab === "resumen" || tab === "general" || tab === "actividad") && <PlaceholderTab tab={tab} />}
        </div>
      </div>

      {modal && <CreateModal onClose={() => setModal(false)} />}
    </div>
  );
}

function GovBlock({ title, inh, children }: { title: string; inh: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-[13px] border border-line bg-surface p-5 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[13px] font-extrabold text-ink-900">{title}</span>
        <div className="flex items-center gap-2">{inh}<button className="text-[11.5px] font-bold text-indigo">Personalizar</button></div>
      </div>
      {children}
    </div>
  );
}

function GobiernoTab() {
  return (
    <div className="flex flex-col gap-3.5">
      <GovBlock title="Tipo documental por defecto" inh={<Inheritance kind="heredado" from="Procesos" />}>
        <div className="inline-flex items-center rounded-lg bg-indigo-tint px-3 py-1.5 text-[13px] font-bold text-indigo">Procedimiento</div>
      </GovBlock>
      <GovBlock title="Circuito de aprobación" inh={<Inheritance kind="personalizado" />}>
        <div className="inline-flex items-center rounded-lg bg-amber-bg px-3 py-1.5 text-[13px] font-bold text-amber">Doble aprobación</div>
      </GovBlock>
      <GovBlock title="Aprobadores por defecto" inh={<Inheritance kind="personalizado" />}>
        <div className="flex flex-wrap gap-2">
          {["Lucía Gómez", "Juan Pérez", "Encargado de turno (rol)"].map((a) => (
            <span key={a} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-[12.5px] font-semibold text-ink-700"><span className="h-1.5 w-1.5 rounded-full bg-indigo" />{a}</span>
          ))}
        </div>
      </GovBlock>
      <GovBlock title="Permitir sobrescribir por documento" inh={<Inheritance kind="heredado" from="Procesos" />}>
        <Toggle on label="Los autores pueden ajustar la configuración en cada documento" />
      </GovBlock>
    </div>
  );
}

const PERMS = ["Ver documentos", "Crear documentos", "Editar", "Importar", "Aprobar", "Eliminar", "Administrar carpeta", "Administrar permisos"];
const ROLES = ["Admin", "Gerente", "Encargado", "Editor", "Lector"];
const MATRIX: Record<string, boolean[]> = {
  "Ver documentos": [true, true, true, true, true], "Crear documentos": [true, true, true, true, false], Editar: [true, true, true, true, false],
  Importar: [true, true, false, false, false], Aprobar: [true, true, true, false, false], Eliminar: [true, true, false, false, false],
  "Administrar carpeta": [true, true, false, false, false], "Administrar permisos": [true, false, false, false, false],
};
function PermisosTab() {
  return (
    <div className="overflow-hidden rounded-[13px] border border-line bg-surface shadow-card">
      <div className="grid items-center border-b border-line-soft bg-surface-hover px-5 py-3 text-[11px] font-extrabold uppercase tracking-[.04em] text-ink-400" style={{ gridTemplateColumns: "1.6fr repeat(5, 1fr)" }}>
        <span>Permiso</span>{ROLES.map((r) => <span key={r} className="text-center">{r}</span>)}
      </div>
      {PERMS.map((p) => (
        <div key={p} className="grid items-center border-b border-line-softer px-5 py-3 last:border-0" style={{ gridTemplateColumns: "1.6fr repeat(5, 1fr)" }}>
          <span className="text-[12.5px] font-semibold text-ink-700">{p}</span>
          {MATRIX[p].map((v, i) => (
            <span key={i} className="flex justify-center">
              {v ? <span className="grid h-5 w-5 place-items-center rounded-md bg-green-bg text-green-text"><Icon d={ICONS.check} size={13} strokeWidth={3} /></span> : <span className="h-1 w-3 rounded bg-line" />}
            </span>
          ))}
        </div>
      ))}
      <div className="border-t border-line-soft px-5 py-3 text-[11.5px] text-ink-400">Origen: <TintPill color="#48569C">Heredado de Biblioteca</TintPill> · <TintPill color="#9A6A00">Personalizado</TintPill></div>
    </div>
  );
}

const IA_OPTS = ["Detectar duplicados", "Detectar nuevas versiones", "Detectar relaciones", "Detectar entidades", "Detectar información sensible", "Detectar documentos obsoletos", "Agrupar documentos similares", "Extraer metadatos"];
function IaTab() {
  return (
    <div>
      <div className="text-[13px] font-extrabold text-ink-900">La IA puede sugerir automáticamente</div>
      <p className="mb-4 text-[12px] text-ink-400">Configuración avanzada. No protagoniza el flujo.</p>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {IA_OPTS.map((o, i) => <div key={o} className="flex items-center justify-between rounded-[12px] border border-line bg-surface px-4 py-3"><span className="text-[13px] font-bold text-ink-700">{o}</span><Toggle on={i < 5} /></div>)}
      </div>
      <div className="mt-4 flex items-start gap-2.5 rounded-[12px] border border-indigo-border bg-indigo-tint px-4 py-3 text-[12.5px] leading-relaxed text-indigo">
        <Icon d="M12 9v4M12 17h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" size={17} className="flex-shrink-0" />
        <span><b>La IA nunca modifica documentos ni toma decisiones automáticamente.</b> Todas las sugerencias requieren validación humana.</span>
      </div>
    </div>
  );
}

function TytoTab() {
  return (
    <div className="flex flex-col gap-3.5">
      <GovBlock title="Disponible para consultas inteligentes" inh={<Inheritance kind="heredado" from="Biblioteca" />}><Toggle on label="Tyto puede usar esta carpeta para responder consultas" /></GovBlock>
      <GovBlock title="Prioridad del conocimiento" inh={<Inheritance kind="personalizado" />}>
        <div className="inline-flex items-center gap-0.5 rounded-lg bg-surface-track p-0.5">
          {["Normal", "Alta", "Crítica"].map((p, i) => <span key={p} className={"rounded-md px-3.5 py-1.5 text-[12.5px] font-bold " + (i === 1 ? "bg-surface text-indigo shadow-card" : "text-ink-400")}>{p}</span>)}
        </div>
      </GovBlock>
      <div className="flex items-start gap-2.5 rounded-[12px] border border-indigo-border bg-indigo-tint px-4 py-3 text-[12.5px] leading-relaxed text-indigo">
        <Icon d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6zM9 12l2 2 4-4" size={17} className="flex-shrink-0" />
        Tyto consulta la <b>representación derivada</b> de estos documentos. El documento original nunca cambia.
      </div>
    </div>
  );
}

function PlaceholderTab({ tab }: { tab: string }) {
  return <div className="rounded-[13px] border border-dashed border-line-input bg-surface-hover px-6 py-10 text-center text-[13px] text-ink-400">Contenido de la pestaña <b className="capitalize text-ink-700">{tab}</b> (ver prototipo para el detalle completo).</div>;
}

function Toggle({ on, label }: { on?: boolean; label?: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className={"relative h-[26px] w-[46px] flex-shrink-0 rounded-pill transition-colors " + (on ? "bg-indigo" : "bg-ink-200")}>
        <span className="absolute top-[3px] h-5 w-5 rounded-full bg-white shadow transition-all" style={{ left: on ? 23 : 3 }} />
      </span>
      {label && <span className="text-[12.5px] text-ink-500">{label}</span>}
    </div>
  );
}

function CreateModal({ onClose }: { onClose: () => void }) {
  return (
    <div onClick={onClose} className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(20,28,33,.38)] p-6">
      <div onClick={(e) => e.stopPropagation()} className="w-[460px] max-w-full rounded-[16px] bg-surface p-6 shadow-modal">
        <h3 className="text-[18px] font-extrabold text-ink-900">Nueva carpeta</h3>
        <p className="mt-1 text-[12.5px] text-ink-400">Cada carpeta es un dominio de conocimiento con su propio gobierno.</p>
        <div className="mt-5 flex flex-col gap-4">
          {["Nombre", "Descripción"].map((l) => (
            <label key={l} className="block"><span className="mb-1.5 block text-[13px] font-bold text-ink-900">{l}</span><input className="h-[44px] w-full rounded-[10px] border border-line-input px-3.5 text-sm outline-none" /></label>
          ))}
          <label className="block"><span className="mb-1.5 block text-[13px] font-bold text-ink-900">Carpeta padre</span>
            <select className="h-[44px] w-full rounded-[10px] border border-line-input px-3 text-sm">{FOLDERS.filter((f) => !f.parent).map((f) => <option key={f.id}>{f.name}</option>)}</select>
          </label>
          <div className="flex items-center justify-between rounded-[12px] border border-line bg-surface px-4 py-3">
            <span className="text-[13px] font-bold text-ink-700">Heredar configuración del padre</span><Toggle on />
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2.5">
          <button onClick={onClose} className="h-[44px] rounded-[10px] border border-line px-5 text-[13.5px] font-bold text-ink-500">Cancelar</button>
          <button onClick={onClose} className="h-[44px] rounded-[10px] bg-ink-800 px-5 text-[13.5px] font-bold text-white">Crear carpeta</button>
        </div>
      </div>
    </div>
  );
}
