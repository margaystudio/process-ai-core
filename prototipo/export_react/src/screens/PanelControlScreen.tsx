// Panel de control — global governance control center. KPIs + alerts + lists.
// NOT a BI dashboard: every item leads to an action.
import React from "react";
import { Icon, ICONS } from "../lib/data";

const KPIS = [
  { label: "Total documentos", value: "486", tone: "#48569C" },
  { label: "Aprobados", value: "312", tone: "#1F8A55" },
  { label: "Pendientes", value: "47", tone: "#9A6A00" },
  { label: "Obsoletos", value: "23", tone: "#CB4242" },
  { label: "Sin responsable", value: "18", tone: "#8A8F91" },
  { label: "Sin aprobador", value: "9", tone: "#8A8F91" },
];

const ALERTS = [
  { sev: "warn", title: "23 documentos marcados como obsoletos", meta: "No se modifican desde hace más de 2 años", cta: "Revisar" },
  { sev: "error", title: "9 documentos sin aprobador asignado", meta: "No pueden avanzar en el circuito", cta: "Asignar" },
  { sev: "info", title: "2 carpetas sin configuración de gobierno", meta: "Comercial › Promociones · Seguridad › Simulacros", cta: "Configurar" },
];

const TOP_TYTO = [
  ["Cierre de caja", "142 consultas"],
  ["Política de devoluciones", "98 consultas"],
  ["Manual de apertura", "76 consultas"],
  ["Liquidación de sueldos", "54 consultas"],
];

const ACTIVE_FOLDERS = [
  ["Procesos › Caja", "32 cambios esta semana"],
  ["RRHH › Liquidación", "21 cambios"],
  ["Comercial", "14 cambios"],
];

function alertTone(sev: string) {
  if (sev === "error") return { c: "#B0413E", bg: "#FDECEC", bd: "#E7B6B2" };
  if (sev === "warn") return { c: "#9A6A00", bg: "#FBF3DD", bd: "#F0DCA0" };
  return { c: "#48569C", bg: "rgba(173,185,223,.12)", bd: "#D2CFE6" };
}

export default function PanelControlScreen() {
  return (
    <div className="mx-auto max-w-[1180px] px-8 pb-[60px] pt-7">
      <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Análisis</div>
      <h1 className="text-[25px] font-extrabold text-ink-900">Panel de control</h1>
      <p className="mt-1.5 text-[13px] text-ink-400">¿Cómo está la documentación de la organización? Todo lo que ves conduce a una acción.</p>

      {/* KPIs */}
      <div className="mt-6 grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))" }}>
        {KPIS.map((k) => (
          <div key={k.label} className="rounded-[13px] border border-line bg-surface p-[18px] shadow-card">
            <div className="text-[26px] font-extrabold" style={{ color: k.tone }}>{k.value}</div>
            <div className="mt-1 text-xs text-ink-400">{k.label}</div>
          </div>
        ))}
      </div>

      {/* alerts */}
      <div className="mb-3 mt-9 text-[15px] font-extrabold text-ink-900">Alertas</div>
      <div className="flex flex-col gap-2.5">
        {ALERTS.map((a, i) => {
          const t = alertTone(a.sev);
          return (
            <div key={i} className="flex items-center gap-3 rounded-[13px] border bg-surface px-[18px] py-3.5 shadow-card">
              <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-[9px]" style={{ color: t.c, background: t.bg }}>
                <Icon d="M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" size={18} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-bold text-ink-900">{a.title}</div>
                <div className="text-[11.5px] text-ink-400">{a.meta}</div>
              </div>
              <button className="flex-shrink-0 rounded-lg border px-3.5 py-2 text-[12px] font-bold" style={{ color: t.c, borderColor: t.bd, background: t.bg }}>{a.cta}</button>
            </div>
          );
        })}
      </div>

      {/* two lists */}
      <div className="mt-9 grid gap-4 md:grid-cols-2">
        <ListCard title="Más consultados por Tyto" rows={TOP_TYTO} icon={ICONS.tyto} />
        <ListCard title="Carpetas con más actividad" rows={ACTIVE_FOLDERS} icon={ICONS.folder} />
      </div>
    </div>
  );
}

function ListCard({ title, rows, icon }: { title: string; rows: string[][]; icon: string }) {
  return (
    <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
      <div className="flex items-center gap-2 border-b border-line-soft px-[18px] py-[15px]">
        <Icon d={icon} size={16} className="text-indigo" />
        <span className="text-[13px] font-extrabold text-ink-900">{title}</span>
      </div>
      {rows.map((r, i) => (
        <div key={i} className="flex items-center justify-between border-b border-line-softer px-[18px] py-3 last:border-0">
          <span className="text-[13px] font-semibold text-ink-700">{r[0]}</span>
          <span className="text-[11.5px] font-bold text-ink-400">{r[1]}</span>
        </div>
      ))}
    </div>
  );
}
