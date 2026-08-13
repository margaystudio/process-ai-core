// components/AppShell.tsx
// Compone el chrome de un módulo: fija data-module (acento), apila Topbar arriba y
// Sidebar + contenido abajo. El contenido scrollea; topbar y sidebar quedan fijos.
// Mobile (< md): si el consumidor pasa mobileNavOpen/onMobileNavClose, la sidebar
// inline se oculta y la navegación vive en un drawer lateral con overlay.
"use client";
import * as React from "react";
import type { ModuleKey } from "./ModuleEmblem";
import { cn } from "../cn";

export function AppShell({
  module,
  topbar,
  sidebar,
  mobileNav,
  mobileNavOpen,
  onMobileNavClose,
  children,
}: {
  module: ModuleKey;
  topbar: React.ReactNode;
  sidebar: React.ReactNode;
  /** Contenido del drawer mobile. Si falta, se reutiliza `sidebar`. */
  mobileNav?: React.ReactNode;
  /** Si se define (junto a onMobileNavClose), habilita el modo drawer en < md. */
  mobileNavOpen?: boolean;
  onMobileNavClose?: () => void;
  children: React.ReactNode;
}) {
  // El modo drawer solo se activa si el consumidor lo cablea; sin estas props el
  // render es idéntico al histórico (sidebar inline siempre visible).
  const conDrawer = mobileNavOpen !== undefined && onMobileNavClose !== undefined;

  // Cierre con Escape y scroll-lock del body mientras el drawer está abierto.
  React.useEffect(() => {
    if (!conDrawer || !mobileNavOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onMobileNavClose?.();
    }
    document.addEventListener("keydown", onKey);
    const overflowPrevio = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflowPrevio;
    };
  }, [conDrawer, mobileNavOpen, onMobileNavClose]);

  return (
    // `data-shell-root` / `data-shell-main` son los ganchos de impresión: en
    // pantalla el shell es `h-dvh` + scroll interno, que al imprimir recortaría todo
    // a una hoja. tokens.css los suelta en `@media print`. Van como data-attr y no
    // como clase para que un módulo pueda apuntarles sin depender de Tailwind.
    <div data-module={module} data-shell-root className="flex h-dvh flex-col bg-ink-50">
      {topbar}
      <div className="flex min-h-0 flex-1">
        {conDrawer ? (
          <>
            <div className="hidden min-h-0 md:flex">{sidebar}</div>
            {/* Overlay + drawer mobile. Se montan siempre para animar la transición. */}
            <div
              className={cn(
                "fixed inset-0 z-40 bg-ink-900/40 transition-opacity md:hidden",
                mobileNavOpen ? "opacity-100" : "pointer-events-none opacity-0"
              )}
              onClick={onMobileNavClose}
              aria-hidden="true"
            />
            <div
              className={cn(
                "fixed inset-y-0 left-0 z-50 flex pb-[env(safe-area-inset-bottom)] transition-transform duration-200 ease-in-out md:hidden",
                mobileNavOpen ? "translate-x-0" : "-translate-x-full"
              )}
              role="dialog"
              aria-modal="true"
              aria-label="Menú de navegación"
            >
              {mobileNav ?? sidebar}
            </div>
          </>
        ) : (
          sidebar
        )}
        <main data-shell-main className="min-w-0 flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
