// components/Sidebar.tsx
// Chrome: panel lateral OSCURO. Arriba = la cuenta/tenant que operás (solo si hay
// cliente). Al pie = firma Margay (logo + empresa). El usuario NO va acá (va en Topbar).
// Colores desde tokens de sidebar (--sidebar-*) y acento por data-module.
import * as React from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import { cn } from "../cn";

export interface NavItem {
  label: string;
  icon?: React.ReactNode;
  active?: boolean;
  external?: boolean;
  onClick?: () => void;
}
export interface NavGroup {
  label: string;
  items: NavItem[];
}

function initialsOf(name: string) {
  return name
    .replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ ]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function Sidebar({
  account,
  groups,
  company = "Margay Studio",
  logoSrc = "/brand/margay-icon-48.png",
}: {
  /** Cuenta/cliente que se opera. Omitir en módulos internos (Hub propio, GPU interno). */
  account?: { name: string; sub?: string };
  groups: NavGroup[];
  company?: string;
  logoSrc?: string;
}) {
  return (
    <aside className="flex w-[224px] shrink-0 flex-col bg-sidebar-surface px-3 pb-3 pt-3.5 text-sidebar-fg">
      {account && (
        <div className="flex items-center gap-2.5 px-1.5 pb-3.5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[10px] bg-white/10 text-xs font-bold">
            {initialsOf(account.name)}
          </span>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-bold">{account.name}</div>
            {account.sub && <div className="text-xs text-white/50">{account.sub}</div>}
          </div>
          <ChevronDown className="h-4 w-4 text-white/40" />
        </div>
      )}

      <nav className="flex flex-col gap-0.5">
        {groups.map((g, gi) => (
          <React.Fragment key={gi}>
            <div className="px-2.5 pb-1.5 pt-3.5 text-[10px] font-bold uppercase tracking-[.1em] text-white/30">
              {g.label}
            </div>
            {g.items.map((it, ii) => (
              <button
                key={ii}
                onClick={it.onClick}
                className={cn(
                  "relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm font-semibold text-white/65 transition-colors hover:bg-sidebar-hover hover:text-white",
                  it.active && "bg-white/[0.09] text-white shadow-[inset_3px_0_0_var(--accent)]"
                )}
              >
                <span
                  className={cn(
                    "[&_svg]:h-[18px] [&_svg]:w-[18px]",
                    it.active ? "text-accent" : "text-white/50"
                  )}
                >
                  {it.icon}
                </span>
                <span>{it.label}</span>
                {it.external && <ExternalLink className="ml-auto h-3.5 w-3.5 text-white/40" />}
              </button>
            ))}
          </React.Fragment>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="mt-1.5 flex items-center gap-2.5 border-t border-sidebar-border px-1.5 pb-0.5 pt-3">
        <img src={logoSrc} alt="" className="h-[30px] w-[30px] rounded-md" />
        <div className="leading-tight">
          <div className="text-[13px] font-bold">{company}</div>
          <div className="text-[10.5px] text-white/45">Plataforma Margay</div>
        </div>
      </div>
    </aside>
  );
}
