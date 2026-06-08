// components/Topbar.tsx
// Chrome: el TOPBAR es del MÓDULO (emblema + nombre) + (opcional) switcher de
// organización/tenant + usuario a la derecha. Fondo claro. El logo Margay NO va acá
// (firma en el pie de la Sidebar).
"use client";
import * as React from "react";
import { LogOut, ChevronDown, Check, Building2 } from "lucide-react";
import { ModuleEmblem, type ModuleKey } from "./ModuleEmblem";
import { cn } from "../cn";

export interface TopbarUser {
  name: string;
  email: string;
  initials: string;
}

/** Organización/tenant que el usuario puede operar (para el switcher del topbar). */
export interface TopbarTenant {
  id: string;
  name: string;
}

export function Topbar({
  module,
  title,
  user,
  onLogout,
  tenants,
  activeTenantId,
  onTenantChange,
}: {
  module: ModuleKey;
  title: string;
  user: TopbarUser;
  onLogout?: () => void;
  /** Si se pasan, el topbar muestra el switcher de organización (como el hub). */
  tenants?: TopbarTenant[];
  activeTenantId?: string;
  onTenantChange?: (id: string) => void;
}) {
  return (
    <header className="flex h-[60px] items-center justify-between border-b border-ink-200 bg-white px-6">
      <div className="flex items-center gap-3">
        <span className="grid h-[34px] w-[34px] place-items-center rounded-md bg-accent-tint text-accent-ink">
          <ModuleEmblem module={module} />
        </span>
        <span className="text-h3 font-bold text-ink-900">{title}</span>
        {tenants && tenants.length > 0 && (
          <>
            <span className="mx-1 h-5 w-px bg-ink-200" aria-hidden="true" />
            <TenantSwitcher
              tenants={tenants}
              activeTenantId={activeTenantId}
              onTenantChange={onTenantChange}
            />
          </>
        )}
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right leading-tight">
          <div className="text-sm font-bold text-ink-800">{user.name}</div>
          <div className="text-xs text-ink-500">{user.email}</div>
        </div>
        <span className="grid h-[34px] w-[34px] place-items-center rounded-full bg-accent text-xs font-bold text-white">
          {user.initials}
        </span>
        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 text-sm font-semibold text-ink-500 hover:text-ink-800"
        >
          <LogOut className="h-4 w-4" />
          Salir
        </button>
      </div>
    </header>
  );
}

function TenantSwitcher({
  tenants,
  activeTenantId,
  onTenantChange,
}: {
  tenants: TopbarTenant[];
  activeTenantId?: string;
  onTenantChange?: (id: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const active = tenants.find((t) => t.id === activeTenantId) ?? tenants[0];
  const canSwitch = tenants.length > 1 && !!onTenantChange;

  React.useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => canSwitch && setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-semibold text-ink-700",
          canSwitch ? "hover:bg-ink-100" : "cursor-default"
        )}
        aria-haspopup={canSwitch ? "menu" : undefined}
        aria-expanded={canSwitch ? open : undefined}
        title={active?.name}
      >
        <Building2 className="h-4 w-4 text-ink-500" />
        <span className="max-w-[180px] truncate">{active?.name}</span>
        {canSwitch && (
          <ChevronDown
            className={cn("h-4 w-4 text-ink-400 transition-transform", open && "rotate-180")}
          />
        )}
      </button>
      {open && canSwitch && (
        <div
          role="menu"
          className="absolute left-0 z-50 mt-1 min-w-[200px] rounded-md border border-ink-200 bg-white py-1 shadow-md"
        >
          {tenants.map((t) => (
            <button
              key={t.id}
              type="button"
              role="menuitem"
              onClick={() => {
                onTenantChange?.(t.id);
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-ink-700 hover:bg-ink-100"
            >
              <span className="flex-1 truncate">{t.name}</span>
              {t.id === active?.id && <Check className="h-4 w-4 text-accent" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
