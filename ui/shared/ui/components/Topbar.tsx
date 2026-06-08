// components/Topbar.tsx
// Chrome: el TOPBAR es del MÓDULO (emblema + nombre) + usuario a la derecha.
// Fondo claro. El logo Margay NO va acá (firma en el pie de la Sidebar).
import * as React from "react";
import { LogOut } from "lucide-react";
import { ModuleEmblem, type ModuleKey } from "./ModuleEmblem";

export interface TopbarUser {
  name: string;
  email: string;
  initials: string;
}

export function Topbar({
  module,
  title,
  user,
  onLogout,
}: {
  module: ModuleKey;
  title: string;
  user: TopbarUser;
  onLogout?: () => void;
}) {
  return (
    <header className="flex h-[60px] items-center justify-between border-b border-ink-200 bg-white px-6">
      <div className="flex items-center gap-3">
        <span className="grid h-[34px] w-[34px] place-items-center rounded-md bg-accent-tint text-accent-ink">
          <ModuleEmblem module={module} />
        </span>
        <span className="text-h3 font-bold text-ink-900">{title}</span>
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
