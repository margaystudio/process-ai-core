"use client";

import { useState } from "react";
import { useFolders } from "@/hooks/useFolders";
import { WizardIcon } from "./WizardIcon";

const FOLDER_ICON =
  "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z";

/**
 * Campo controlado "Guardar en" + modal de selección de carpeta.
 * Carga las carpetas reales del workspace activo vía listFolders().
 *
 * value / onChange trabajan con `folder_id` (string) del backend.
 */
export function FolderSelector({
  value,
  onChange,
}: {
  /** ID de la carpeta seleccionada (vacío si no se eligió ninguna) */
  value: string;
  onChange: (folderId: string, folderName: string) => void;
}) {
  const [open, setOpen] = useState(false);
  // Carpetas cacheadas: se cargan una vez con la pantalla (no en cada apertura del selector).
  const { folders, loading, error } = useFolders();

  // Nombre de la carpeta seleccionada (para mostrar). Disponible sin abrir el modal.
  const selectedFolder = folders.find((f) => f.id === value) ?? null;

  return (
    <>
      <div className="flex items-center gap-3 rounded-[10px] border border-line-input p-[11px_14px]">
        <WizardIcon
          d={FOLDER_ICON}
          size={18}
          className="flex-shrink-0 text-indigo"
        />
        <span className="min-w-0 flex-1 truncate text-sm font-bold text-ink-900">
          {selectedFolder ? (
            selectedFolder.path || selectedFolder.name
          ) : (
            <span className="font-normal text-ink-400">
              Seleccioná una carpeta…
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="h-[34px] flex-shrink-0 rounded-lg border border-indigo-light bg-indigo-tint px-4 text-[13px] font-bold text-indigo transition-colors hover:bg-indigo hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo"
        >
          {value ? "Cambiar" : "Elegir"}
        </button>
      </div>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Elegir ubicación"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-[120] flex items-center justify-center bg-[rgba(20,28,33,.45)] p-6"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[84vh] w-[440px] max-w-full flex-col rounded-2xl bg-surface p-[20px_22px] shadow-modal"
          >
            {/* Header */}
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[17px] font-extrabold text-ink-900">
                Elegí la ubicación
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Cerrar"
                className="grid h-7 w-7 place-items-center rounded-lg bg-line-softer transition-colors hover:bg-line focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
              >
                <WizardIcon
                  d="M18 6L6 18M6 6l12 12"
                  size={14}
                  className="text-ink-400"
                  strokeWidth={2.2}
                />
              </button>
            </div>

            {/* Lista de carpetas */}
            <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto">
              {loading && (
                <div className="py-8 text-center text-[13px] text-ink-400">
                  Cargando carpetas…
                </div>
              )}

              {error && (
                <div className="rounded-[10px] border border-danger-bd bg-danger-bg px-4 py-3 text-[12.5px] text-danger">
                  {error}
                </div>
              )}

              {!loading && !error && folders.length === 0 && (
                <div className="py-8 text-center text-[13px] text-ink-400">
                  No hay carpetas creadas todavía.
                </div>
              )}

              {!loading &&
                folders.map((f) => {
                  const sel = f.id === value;
                  return (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => {
                        onChange(f.id, f.path || f.name);
                        setOpen(false);
                      }}
                      className={
                        "flex items-center gap-3 rounded-[10px] border px-3.5 py-3 text-left transition-colors " +
                        (sel
                          ? "border-indigo-light bg-indigo-tint"
                          : "border-line bg-surface hover:bg-surface-hover")
                      }
                    >
                      <WizardIcon
                        d={FOLDER_ICON}
                        size={17}
                        className={sel ? "text-indigo" : "text-ink-400"}
                      />
                      <span
                        className={
                          "flex-1 text-[13.5px] font-bold " +
                          (sel ? "text-indigo" : "text-ink-800")
                        }
                      >
                        {f.path || f.name}
                      </span>
                      {sel && (
                        <WizardIcon
                          d="M20 6L9 17l-5-5"
                          size={15}
                          className="text-indigo"
                          strokeWidth={2.6}
                        />
                      )}
                    </button>
                  );
                })}
            </div>

            {/* TODO(wire): conectar con creación real de carpetas (createFolder) */}
            <button
              type="button"
              className="mt-3 flex items-center justify-center gap-2 rounded-[10px] border border-dashed border-line-input py-2.5 text-[12.5px] font-bold text-ink-500 transition-colors hover:border-indigo-light hover:text-indigo focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
            >
              <WizardIcon d="M12 5v14M5 12h14" size={15} />
              Nueva carpeta
            </button>
          </div>
        </div>
      )}
    </>
  );
}
