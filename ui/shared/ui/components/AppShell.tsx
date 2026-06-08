// components/AppShell.tsx
// Compone el chrome de un módulo: fija data-module (acento), apila Topbar arriba y
// Sidebar + contenido abajo. El contenido scrollea; topbar y sidebar quedan fijos.
import * as React from "react";
import type { ModuleKey } from "./ModuleEmblem";

export function AppShell({
  module,
  topbar,
  sidebar,
  children,
}: {
  module: ModuleKey;
  topbar: React.ReactNode;
  sidebar: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div data-module={module} className="flex h-screen flex-col bg-ink-50">
      {topbar}
      <div className="flex min-h-0 flex-1">
        {sidebar}
        <main className="min-w-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
