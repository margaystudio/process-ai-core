/**
 * Tabs accesibles — Margay Design System.
 *
 * Implementa role="tablist" / role="tab" / role="tabpanel" con aria-selected,
 * aria-controls / id encadenados y roving focus (flechas ←/→). Reemplaza los
 * `<button>` sin accesibilidad usados en las pantallas de Settings.
 *
 * API controlada: el padre mantiene `value` y reacciona a `onValueChange`.
 *
 * @example
 * const [tab, setTab] = useState("general");
 * const items = [
 *   { value: "general", label: "General" },
 *   { value: "usuarios", label: "Usuarios" },
 * ];
 *
 * <Tabs value={tab} onValueChange={setTab} items={items}>
 *   {tab === "general" && <GeneralPanel />}
 *   {tab === "usuarios" && <UsuariosPanel />}
 * </Tabs>
 *
 * // Si querés paneles declarativos, usá TabsContent:
 * <Tabs value={tab} onValueChange={setTab} items={items}>
 *   <TabsContent value="general" current={tab}><GeneralPanel /></TabsContent>
 *   <TabsContent value="usuarios" current={tab}><UsuariosPanel /></TabsContent>
 * </Tabs>
 */
"use client";

import * as React from "react";
import { cn } from "../cn";

export interface TabItem {
  value: string;
  label: string;
  /** Deshabilita la pestaña (sigue siendo enfocable con roving focus). */
  disabled?: boolean;
}

export interface TabsProps {
  /** Valor activo (pestaña seleccionada). */
  value: string;
  /** Callback al cambiar pestaña. */
  onValueChange: (value: string) => void;
  /** Lista de pestañas. */
  items: TabItem[];
  /** Contenido debajo del tablist (normalmente el panel activo). */
  children?: React.ReactNode;
  /** ID base para generar aria-controls / id de paneles. */
  id?: string;
  /** Clases adicionales en el contenedor. */
  className?: string;
  /** Clases adicionales en el tablist. */
  tablistClassName?: string;
}

export function Tabs({
  value,
  onValueChange,
  items,
  children,
  id: baseId,
  className,
  tablistClassName,
}: TabsProps) {
  const uid = React.useId();
  const prefix = baseId ?? uid;
  const tabRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  function handleKeyDown(
    e: React.KeyboardEvent<HTMLButtonElement>,
    index: number
  ) {
    const enabledIndexes = items
      .map((item, i) => (item.disabled ? null : i))
      .filter((i): i is number => i !== null);

    const pos = enabledIndexes.indexOf(index);

    let next: number | undefined;
    if (e.key === "ArrowRight") {
      next = enabledIndexes[(pos + 1) % enabledIndexes.length];
    } else if (e.key === "ArrowLeft") {
      next =
        enabledIndexes[
          (pos - 1 + enabledIndexes.length) % enabledIndexes.length
        ];
    } else if (e.key === "Home") {
      next = enabledIndexes[0];
    } else if (e.key === "End") {
      next = enabledIndexes[enabledIndexes.length - 1];
    }

    if (next !== undefined) {
      e.preventDefault();
      tabRefs.current[next]?.focus();
      onValueChange(items[next].value);
    }
  }

  return (
    <div className={className}>
      {/* Tablist */}
      <div
        role="tablist"
        aria-orientation="horizontal"
        className={cn(
          "flex border-b border-ink-200",
          tablistClassName
        )}
      >
        {items.map((item, index) => {
          const isSelected = item.value === value;
          return (
            <button
              key={item.value}
              ref={(el) => { tabRefs.current[index] = el; }}
              role="tab"
              type="button"
              id={`${prefix}-tab-${item.value}`}
              aria-controls={`${prefix}-panel-${item.value}`}
              aria-selected={isSelected}
              disabled={item.disabled}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => {
                if (!item.disabled) onValueChange(item.value);
              }}
              onKeyDown={(e) => handleKeyDown(e, index)}
              className={cn(
                "relative px-4 py-2.5 text-sm font-semibold transition-colors",
                "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring focus-visible:ring-inset",
                "disabled:cursor-not-allowed disabled:opacity-50",
                isSelected
                  ? "text-ink-800 after:absolute after:inset-x-0 after:bottom-[-1px] after:h-[2px] after:rounded-t-sm after:bg-action"
                  : "text-ink-500 hover:text-ink-700"
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      {/* Panel area */}
      {children}
    </div>
  );
}

/**
 * Contenedor de panel para uso declarativo junto con `<Tabs>`.
 * Aplica role="tabpanel" con aria-labelledby encadenado al tab.
 */
export interface TabsContentProps {
  /** Valor de esta pestaña. */
  value: string;
  /** Valor activo (la misma prop `value` del `<Tabs>` padre). */
  current: string;
  children: React.ReactNode;
  /** ID base (debe coincidir con el `id` del `<Tabs>` padre). */
  id?: string;
  className?: string;
}

export function TabsContent({
  value,
  current,
  children,
  id: baseId,
  className,
}: TabsContentProps) {
  const uid = React.useId();
  const prefix = baseId ?? uid;
  const isActive = value === current;

  return (
    <div
      role="tabpanel"
      id={`${prefix}-panel-${value}`}
      aria-labelledby={`${prefix}-tab-${value}`}
      hidden={!isActive}
      tabIndex={0}
      className={cn(
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring",
        className
      )}
    >
      {isActive ? children : null}
    </div>
  );
}
