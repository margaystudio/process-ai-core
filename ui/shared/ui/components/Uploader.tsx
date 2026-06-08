// components/Uploader.tsx
// Dropzone de carga de archivos. Resalta con el acento del módulo al arrastrar/hover.
import * as React from "react";
import { Upload } from "lucide-react";
import { cn } from "../cn";

export function Uploader({
  accept = ".xlsx",
  hint = "Formato: Excel (.xlsx) · máx. 10 MB",
  label = (
    <>
      Subí el archivo o <span className="font-bold text-create">elegí un archivo</span>
    </>
  ),
  onFile,
}: {
  accept?: string;
  hint?: string;
  label?: React.ReactNode;
  onFile?: (file: File) => void;
}) {
  const [drag, setDrag] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  return (
    <label
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f && onFile) onFile(f);
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center gap-1.5 rounded-md border-[1.5px] border-dashed border-ink-300 bg-ink-50 px-5 py-8 text-center transition-colors hover:border-accent hover:bg-accent-tint",
        drag && "border-accent bg-accent-tint"
      )}
    >
      <Upload className="h-[30px] w-[30px] text-ink-400" />
      <span className="text-body font-semibold text-ink-700">{label}</span>
      <span className="text-xs text-ink-500">{hint}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f && onFile) onFile(f);
        }}
      />
    </label>
  );
}
