// Tipo de documentos — configurable document types with per-type behaviour.
import React, { useState } from "react";
import { Icon, FOLDER_ICON_PATHS, FolderIconKind } from "../lib/data";

interface DocType { id: string; name: string; icon: FolderIconKind; color: string; count: number; desc: string; on: string[]; }

const BEHAVIORS: Record<string, string> = {
  versionado: "Versionado", aprobacion: "Aprobación", tyto: "Disponible para Tyto", relaciones: "Relaciones",
  metadatos: "Extraer metadatos", vencimiento: "Fecha de vencimiento", responsable: "Responsable",
  confidencial: "Confidencial", renovacion: "Renovación", comunicacion: "Requiere comunicación",
  aceptacion: "Puede pedir aceptación", capitulos: "Puede tener capítulos", plantillas: "Puede generar plantillas",
};

const TYPES: DocType[] = [
  { id: "procedimiento", name: "Procedimiento", icon: "flow", color: "#48569C", count: 142, desc: "Cómo se ejecuta una tarea paso a paso.", on: ["versionado", "aprobacion", "tyto", "relaciones", "metadatos"] },
  { id: "politica", name: "Política", icon: "shield", color: "#2F9E62", count: 38, desc: "Reglas y lineamientos de la organización.", on: ["versionado", "aprobacion", "tyto", "comunicacion", "aceptacion"] },
  { id: "manual", name: "Manual", icon: "box", color: "#C99A2E", count: 21, desc: "Documento extenso con capítulos.", on: ["versionado", "aprobacion", "tyto", "capitulos", "metadatos"] },
  { id: "contrato", name: "Contrato", icon: "contract", color: "#2E8B8B", count: 54, desc: "Acuerdo legal con un tercero.", on: ["aprobacion", "vencimiento", "responsable", "confidencial", "renovacion"] },
  { id: "formulario", name: "Formulario", icon: "folder", color: "#8B5CC2", count: 33, desc: "Plantilla para capturar datos.", on: ["versionado", "plantillas", "metadatos"] },
  { id: "nda", name: "NDA", icon: "shield", color: "#CB4242", count: 8, desc: "Acuerdo de confidencialidad.", on: ["aprobacion", "vencimiento", "confidencial", "renovacion"] },
];

export default function TipoDocumentosScreen() {
  const [selId, setSelId] = useState("procedimiento");
  const [types, setTypes] = useState(TYPES);
  const sel = types.find((t) => t.id === selId)!;
  const toggle = (k: string) => setTypes((ts) => ts.map((t) => (t.id !== selId ? t : { ...t, on: t.on.includes(k) ? t.on.filter((x) => x !== k) : [...t.on, k] })));

  return (
    <div className="flex min-h-full items-stretch">
      {/* list pane */}
      <div className="w-[320px] flex-shrink-0 border-r border-line bg-surface p-5">
        <div className="mb-1 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Administración</div>
        <h1 className="mb-4 text-[19px] font-extrabold text-ink-900">Tipo de documentos</h1>
        <button className="mb-3 flex w-full items-center justify-center gap-2 rounded-[10px] border border-dashed border-line-input bg-surface py-2.5 text-[12.5px] font-bold text-ink-500">
          <Icon d="M12 5v14M5 12h14" size={15} />Nuevo tipo
        </button>
        <div className="flex flex-col gap-1">
          {types.map((t) => (
            <button key={t.id} onClick={() => setSelId(t.id)} className={"flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-left " + (t.id === selId ? "bg-indigo-tint" : "hover:bg-surface-hover")}>
              <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg" style={{ color: t.color, background: `${t.color}1f` }}><Icon d={FOLDER_ICON_PATHS[t.icon]} size={16} /></span>
              <span className="min-w-0 flex-1"><span className="block text-[13px] font-bold text-ink-800">{t.name}</span><span className="block text-[11px] text-ink-300">{t.count} documentos</span></span>
            </button>
          ))}
        </div>
      </div>

      {/* detail pane */}
      <div className="min-w-0 max-w-[720px] flex-1 px-8 pb-[50px] pt-7">
        <div className="flex items-center gap-3.5">
          <span className="grid h-12 w-12 flex-shrink-0 place-items-center rounded-[13px]" style={{ color: sel.color, background: `${sel.color}1f` }}><Icon d={FOLDER_ICON_PATHS[sel.icon]} size={24} /></span>
          <div>
            <h2 className="text-[22px] font-extrabold text-ink-900">{sel.name}</h2>
            <div className="text-[12.5px] text-ink-400">{sel.desc} · {sel.count} documentos</div>
          </div>
        </div>

        <div className="mt-7 text-[13px] font-extrabold text-ink-900">Comportamiento</div>
        <p className="mb-4 text-[12px] text-ink-400">Cada tipo activa funciones específicas del modelo documental.</p>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {Object.entries(BEHAVIORS).map(([k, label]) => {
            const active = sel.on.includes(k);
            return (
              <button key={k} onClick={() => toggle(k)} className={"flex items-center justify-between rounded-[12px] border px-4 py-3 text-left transition-colors " + (active ? "border-indigo-light bg-indigo-tint" : "border-line bg-surface")}>
                <span className={"text-[13px] font-bold " + (active ? "text-indigo" : "text-ink-500")}>{label}</span>
                <span className={"relative h-[22px] w-[38px] flex-shrink-0 rounded-pill transition-colors " + (active ? "bg-indigo" : "bg-ink-200")}>
                  <span className="absolute top-[3px] h-4 w-4 rounded-full bg-white shadow transition-all" style={{ left: active ? 19 : 3 }} />
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
