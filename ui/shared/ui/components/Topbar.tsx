// components/Topbar.tsx
// Chrome: el TOPBAR es del MÓDULO (emblema + nombre) + (opcional) switcher de
// organización/tenant + usuario a la derecha. Fondo claro. El logo Margay NO va acá
// (firma en el pie de la Sidebar).
"use client";
import * as React from "react";
import { LogOut, ChevronDown, Check, Building2, Menu } from "lucide-react";
import { ModuleEmblem, type ModuleKey } from "./ModuleEmblem";
import { cn } from "../cn";

export interface TopbarUser {
  name: string;
  email: string;
  initials: string;
  /** Foto del usuario (p. ej. avatar de Google). Si falta, se muestran las iniciales. */
  avatarUrl?: string | null;
}

/** Organización/tenant que el usuario puede operar (para el switcher del topbar). */
export interface TopbarTenant {
  id: string;
  name: string;
}

export function Topbar({
  module,
  title,
  lockup,
  user,
  onLogout,
  onProfile,
  onMenuClick,
  tenants,
  activeTenantId,
  onTenantChange,
}: {
  module: ModuleKey;
  /** Nombre del módulo. Obligatorio salvo que pases `lockup`. */
  title?: string;
  /**
   * Reemplaza el lockup por defecto (emblema + título). Lo usa `<PlatformShell>` para
   * montar el `<ModuleSwitcher>` en su lugar. Sin esta prop el render es el histórico.
   */
  lockup?: React.ReactNode;
  /** Si falta, el bloque de usuario no se renderiza (lo decide el consumidor). */
  user?: TopbarUser;
  onLogout?: () => void;
  /** Si se pasa, el bloque de usuario (nombre + avatar) es clickeable → perfil. */
  onProfile?: () => void;
  /** Si se pasa, muestra el botón hamburguesa en < md (abre el drawer del AppShell). */
  onMenuClick?: () => void;
  /** Si se pasan, el topbar muestra el switcher de organización (como el hub). */
  tenants?: TopbarTenant[];
  activeTenantId?: string;
  onTenantChange?: (id: string) => void;
}) {
  const avatar = !user ? null : user.avatarUrl ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={user.avatarUrl}
      alt=""
      referrerPolicy="no-referrer"
      className="h-[34px] w-[34px] rounded-full object-cover"
    />
  ) : (
    <span className="grid h-[34px] w-[34px] place-items-center rounded-full bg-accent text-xs font-bold text-white">
      {user.initials}
    </span>
  );

  const userBlock = user && (
    <>
      {/* En mobile se oculta el texto (queda solo el avatar) para no desbordar. */}
      <div className="hidden text-right leading-tight sm:block">
        <div className="text-sm font-bold text-ink-800">{user.name}</div>
        <div className="text-xs text-ink-500">{user.email}</div>
      </div>
      {avatar}
    </>
  );

  return (
    <header className="print:hidden flex h-[60px] items-center justify-between gap-2 border-b border-ink-200 bg-white px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        {onMenuClick && (
          <button
            type="button"
            onClick={onMenuClick}
            aria-label="Abrir menú"
            className="-ml-1.5 grid h-10 w-10 shrink-0 place-items-center rounded-md text-ink-600 transition-colors hover:bg-ink-100 md:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        {lockup ?? (
          <>
            <span className="grid h-[34px] w-[34px] shrink-0 place-items-center rounded-md bg-accent-tint text-accent-ink">
              <ModuleEmblem module={module} />
            </span>
            <span className="truncate text-h3 font-bold text-ink-900">{title}</span>
          </>
        )}
        {tenants && tenants.length > 0 && (
          <>
            <span className="mx-1 hidden h-5 w-px bg-ink-200 sm:block" aria-hidden="true" />
            <div className="hidden sm:block">
              <TenantSwitcher
                tenants={tenants}
                activeTenantId={activeTenantId}
                onTenantChange={onTenantChange}
              />
            </div>
          </>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-4">
        {onProfile && userBlock ? (
          <button
            type="button"
            onClick={onProfile}
            title="Ver mi perfil"
            className="-mx-1.5 flex items-center gap-4 rounded-md px-1.5 py-1 transition-colors hover:bg-ink-100"
          >
            {userBlock}
          </button>
        ) : (
          userBlock
        )}
        {/* Sin usuario, "Salir" solo tiene sentido si el consumidor cableó el handler. */}
        {(user || onLogout) && (
          <button
            onClick={onLogout}
            title="Salir"
            className="flex items-center gap-1.5 text-sm font-semibold text-ink-500 hover:text-ink-800"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Salir</span>
          </button>
        )}
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
