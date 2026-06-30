// App shell: dark Sidebar (230px) + fixed Topbar (58px) + content area.
import React from "react";
import { Icon, ICONS } from "../lib/data";

export type ViewKey =
  | "biblioteca" | "porAprobar"          // Biblioteca
  | "nuevo" | "importar"                 // Crear
  | "panel"                              // Análisis
  | "carpetas" | "tipos" | "usuarios"    // Administración
  | "tyto";                              // Asistente

interface NavItem { key: ViewKey; label: string; icon: string; badge?: number; }
interface NavSection { title: string; items: NavItem[]; }

const SECTIONS: NavSection[] = [
  { title: "Biblioteca", items: [
    { key: "biblioteca", label: "Biblioteca", icon: ICONS.doc },
    { key: "porAprobar", label: "Por aprobar", icon: ICONS.check, badge: 3 },
  ]},
  { title: "Crear", items: [
    { key: "nuevo", label: "Nuevo documento", icon: ICONS.plus },
    { key: "importar", label: "Importar documentación", icon: ICONS.upload },
  ]},
  { title: "Análisis", items: [
    { key: "panel", label: "Panel de control", icon: ICONS.chart },
  ]},
  { title: "Administración", items: [
    { key: "carpetas", label: "Carpetas", icon: ICONS.folder },
    { key: "tipos", label: "Tipo de documentos", icon: ICONS.list },
    { key: "usuarios", label: "Usuarios y roles", icon: ICONS.users },
  ]},
  { title: "Asistente", items: [
    { key: "tyto", label: "Tyto", icon: ICONS.tyto },
  ]},
];

function Sidebar({ view, onNavigate }: { view: ViewKey; onNavigate: (v: ViewKey) => void }) {
  return (
    <aside className="flex w-[230px] flex-shrink-0 flex-col bg-ink-800 p-3">
      {SECTIONS.map((sec) => (
        <div key={sec.title}>
          <div className="px-2.5 pb-1.5 pt-4 text-[10px] font-bold uppercase tracking-[.1em] text-white/30">{sec.title}</div>
          <div className="flex flex-col gap-0.5">
            {sec.items.map((it) => {
              const active = view === it.key;
              return (
                <button
                  key={it.key}
                  onClick={() => onNavigate(it.key)}
                  className={
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-semibold transition-colors " +
                    (active
                      ? "bg-white/[.09] text-white shadow-[inset_3px_0_0_#ADB9DF]"
                      : "text-white/[.62] hover:bg-white/[.05]")
                  }
                >
                  <Icon d={it.icon} size={17} className="opacity-80" />
                  <span className="flex-1 text-left">{it.label}</span>
                  {it.badge != null && (
                    <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[9px] bg-red px-1.5 text-[10.5px] font-extrabold text-white">{it.badge}</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      <div className="mt-auto px-2.5 pt-4 text-[10.5px] font-semibold text-white/25">Margay Studio</div>
    </aside>
  );
}

function Topbar({ onHome }: { onHome: () => void }) {
  return (
    <div className="z-10 flex h-[58px] flex-shrink-0 items-center justify-between border-b border-line bg-surface px-[22px]">
      <button onClick={onHome} className="flex items-center gap-3">
        <span className="grid h-[34px] w-[34px] place-items-center rounded-lg bg-indigo-tint text-indigo">
          <svg width="22" height="22" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="13" r="3.2" /><circle cx="11" cy="35" r="3.2" /><circle cx="37" cy="24" r="3.2" />
            <path d="M14 14l20 9M14 34l20 -9" />
          </svg>
        </span>
        <span className="text-base font-bold text-ink-900">Process AI</span>
      </button>
      <div className="flex items-center gap-4">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink-500">
          <Icon d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4" size={14} className="text-ink-400" />
          Estación El Cruce
        </span>
        <span className="grid h-8 w-8 place-items-center rounded-full bg-indigo text-xs font-bold text-white">MD</span>
      </div>
    </div>
  );
}

export function AppShell({ view, onNavigate, children }: { view: ViewKey; onNavigate: (v: ViewKey) => void; children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden font-sans">
      <div className="flex min-h-0 flex-1">
        <Sidebar view={view} onNavigate={onNavigate} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onHome={() => onNavigate("biblioteca")} />
          <main className="min-h-0 flex-1 overflow-y-auto bg-surface-app">{children}</main>
        </div>
      </div>
    </div>
  );
}
