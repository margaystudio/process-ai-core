/**
 * Switch / Toggle accesible — Margay Design System.
 *
 * Implementa role="switch" con aria-checked, navegación por teclado (Space/Enter)
 * y estado disabled. Mínimo 38px de target. Tokens Margay sin hex sueltos.
 *
 * @example
 * <Switch
 *   id="notificaciones"
 *   label="Recibir notificaciones"
 *   checked={enabled}
 *   onCheckedChange={setEnabled}
 * />
 */
"use client";

import * as React from "react";
import { cn } from "../cn";

export interface SwitchProps {
  /** Estado actual del toggle. */
  checked: boolean;
  /** Callback al cambiar. Recibe el nuevo valor. */
  onCheckedChange: (checked: boolean) => void;
  /** Deshabilita el control. */
  disabled?: boolean;
  /**
   * Texto visible junto al toggle. Si no se provee, se debe pasar `aria-label`
   * para cumplir accesibilidad AA.
   */
  label?: string;
  /** ID del input (enlaza con el label). */
  id?: string;
  /** aria-label cuando no hay label visible. */
  "aria-label"?: string;
  /** Clases adicionales en el contenedor. */
  className?: string;
}

export function Switch({
  checked,
  onCheckedChange,
  disabled = false,
  label,
  id,
  "aria-label": ariaLabel,
  className,
}: SwitchProps) {
  function handleKeyDown(e: React.KeyboardEvent<HTMLButtonElement>) {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      if (!disabled) onCheckedChange(!checked);
    }
  }

  function handleClick() {
    if (!disabled) onCheckedChange(!checked);
  }

  const button = (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label ? undefined : ariaLabel}
      disabled={disabled}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        // Track
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-pill",
        "transition-colors duration-150 ease-in-out",
        "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring",
        "disabled:cursor-not-allowed",
        checked
          ? "bg-create disabled:bg-ink-300"
          : "bg-ink-300 disabled:bg-ink-200"
      )}
    >
      {/* Thumb */}
      <span
        aria-hidden="true"
        className={cn(
          "pointer-events-none block h-4 w-4 rounded-full bg-white shadow-xs",
          "transition-transform duration-150 ease-in-out",
          checked ? "translate-x-[18px]" : "translate-x-[2px]"
        )}
      />
    </button>
  );

  if (!label) return <span className={className}>{button}</span>;

  return (
    <label
      className={cn(
        "inline-flex min-h-[38px] cursor-pointer items-center gap-2.5",
        disabled && "cursor-not-allowed opacity-60",
        className
      )}
      htmlFor={id}
    >
      {button}
      <span className="select-none text-sm text-ink-700">{label}</span>
    </label>
  );
}
