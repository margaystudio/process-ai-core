/**
 * Dialog / Modal accesible — Margay Design System.
 *
 * Implementa:
 *   - role="dialog" + aria-modal="true" + aria-labelledby
 *   - Focus trap: Tab / Shift+Tab ciclan dentro del dialog.
 *   - Cierre con Esc.
 *   - Restaura el foco al elemento que lo tenía antes de abrir.
 *   - Backdrop semitransparente (click cierra si `closeOnBackdrop` = true).
 *   - Scroll del body bloqueado mientras está abierto.
 *
 * Renderiza en un portal sobre #document.body para salir del stacking context.
 *
 * @example
 * <Dialog
 *   open={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   title="Confirmar eliminación"
 * >
 *   <p>¿Querés eliminar esta carpeta?</p>
 *   <div className="flex justify-end gap-3 pt-4">
 *     <Button variant="secondary" onClick={() => setIsOpen(false)}>Cancelar</Button>
 *     <Button variant="danger" onClick={handleDelete}>Eliminar</Button>
 *   </div>
 * </Dialog>
 */
"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "../cn";

export interface DialogProps {
  /** Controla la visibilidad del dialog. */
  open: boolean;
  /** Callback al cerrar (Esc, backdrop o botón X). */
  onClose: () => void;
  /** Título visible del dialog (también aria-labelledby). */
  title?: string;
  /** Si `title` no se usa, proveé `aria-labelledby` apuntando a tu propio heading. */
  "aria-labelledby"?: string;
  children: React.ReactNode;
  /**
   * Ancho máximo del panel.
   * @default "max-w-lg"
   */
  maxWidth?: string;
  /** Si `true`, hacer click en el backdrop llama a `onClose`. @default true */
  closeOnBackdrop?: boolean;
  /** Clases adicionales en el panel. */
  className?: string;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function Dialog({
  open,
  onClose,
  title,
  "aria-labelledby": ariaLabelledBy,
  children,
  maxWidth = "max-w-lg",
  closeOnBackdrop = true,
  className,
}: DialogProps) {
  const panelRef = React.useRef<HTMLDivElement>(null);
  const previousFocusRef = React.useRef<HTMLElement | null>(null);
  const titleId = React.useId();
  const labelledBy = ariaLabelledBy ?? (title ? titleId : undefined);

  // Guardar foco previo al abrir
  React.useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      // Mover el foco al panel en el próximo frame (tras render)
      requestAnimationFrame(() => {
        const first = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE);
        first ? first.focus() : panelRef.current?.focus();
      });
      // Bloquear scroll
      document.body.style.overflow = "hidden";
    } else {
      // Restaurar foco y scroll al cerrar
      document.body.style.overflow = "";
      previousFocusRef.current?.focus();
    }
  }, [open]);

  // Limpiar overflow si el componente se desmonta mientras está abierto
  React.useEffect(() => {
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  // Cerrar con Esc
  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  // Focus trap
  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  if (!open) return null;

  const content = (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-hidden="false"
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-ink-900/40 backdrop-blur-[2px]"
        aria-hidden="true"
        onClick={closeOnBackdrop ? onClose : undefined}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className={cn(
          "relative z-10 w-full rounded-lg bg-white shadow-modal",
          "focus-visible:outline-none",
          "animate-in",
          maxWidth,
          className
        )}
      >
        {/* Header */}
        {title && (
          <div className="flex items-start justify-between border-b border-ink-200 px-5 py-4">
            <h2 id={titleId} className="text-h3 text-ink-800">
              {title}
            </h2>
            <button
              type="button"
              aria-label="Cerrar"
              onClick={onClose}
              className={cn(
                "ml-4 flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
                "text-ink-500 hover:bg-ink-100 hover:text-ink-700",
                "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring",
                "transition-colors"
              )}
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        )}

        {/* Body */}
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );

  // Portal: renderiza fuera del árbol DOM del componente
  return typeof window !== "undefined"
    ? createPortal(content, document.body)
    : null;
}
