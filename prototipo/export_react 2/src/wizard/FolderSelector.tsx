// FolderSelector — "Guardar en" field with a "Cambiar" button that opens a
// modal to pick the destination folder. Controlled component.
import React, { useState } from "react";
import { FOLDERS, Icon } from "./data";

export function FolderSelector({ value, onChange }: { value: string; onChange: (folder: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="flex items-center gap-3 rounded-[10px] border border-line-input p-[11px_14px]">
        <Icon d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" size={18} className="flex-shrink-0 text-indigo" />
        <span className="min-w-0 flex-1 truncate text-sm font-bold text-ink-900">{value}</span>
        <button
          onClick={() => setOpen(true)}
          className="h-[34px] flex-shrink-0 rounded-lg border border-indigo-light bg-indigo-tint px-4 text-[13px] font-bold text-indigo"
        >
          Cambiar
        </button>
      </div>

      {open && (
        <div onClick={() => setOpen(false)} className="fixed inset-0 z-[120] flex items-center justify-center bg-[rgba(20,28,33,.45)] p-6">
          <div onClick={(e) => e.stopPropagation()} className="flex max-h-[84vh] w-[440px] max-w-full flex-col rounded-2xl bg-surface p-[20px_22px] shadow-modal">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[17px] font-extrabold text-ink-900">Elegí la ubicación</span>
              <button onClick={() => setOpen(false)} className="grid h-7 w-7 place-items-center rounded-lg bg-line-softer">
                <Icon d="M18 6L6 18M6 6l12 12" size={14} className="text-ink-400" strokeWidth={2.2} />
              </button>
            </div>
            <div className="flex flex-col gap-1.5 overflow-y-auto">
              {FOLDERS.map((f) => {
                const sel = f === value;
                return (
                  <button
                    key={f}
                    onClick={() => { onChange(f); setOpen(false); }}
                    className={"flex items-center gap-3 rounded-[10px] border px-3.5 py-3 text-left " + (sel ? "border-indigo-light bg-indigo-tint" : "border-line bg-surface hover:bg-surface-hover")}
                  >
                    <Icon d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" size={17} className={sel ? "text-indigo" : "text-ink-400"} />
                    <span className={"flex-1 text-[13.5px] font-bold " + (sel ? "text-indigo" : "text-ink-800")}>{f}</span>
                    {sel && <Icon d="M20 6L9 17l-5-5" size={15} className="text-indigo" strokeWidth={2.6} />}
                  </button>
                );
              })}
            </div>
            <button className="mt-3 flex items-center justify-center gap-2 rounded-[10px] border border-dashed border-line-input py-2.5 text-[12.5px] font-bold text-ink-500">
              <Icon d="M12 5v14M5 12h14" size={15} />Nueva carpeta
            </button>
          </div>
        </div>
      )}
    </>
  );
}
