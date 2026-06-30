"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  EVIDENCE_TYPES,
  EVIDENCE_TIPO_TO_FILE_TYPE,
  type EvidenceTipo,
  type Evidence,
  evidenceIconPath,
  formatSecs,
  formatFileSize,
  getPreferredAudioMime,
} from "./data";
import { WizardIcon } from "./WizardIcon";

type Mode = "import" | "record";
type RecPhase = "idle" | "rec" | "done" | "error";

const TYPES: EvidenceTipo[] = ["Audio", "Video", "PDF", "Imagen", "Documento"];

/**
 * Modal "Agregar evidencia".
 *
 * Modo "Archivo existente": selector de tipo → <input type="file"> real → agrega evidencia.
 * Modo "Grabar audio": idle → grabando (MediaRecorder real + timer) → listo → agrega evidencia.
 */
export function AddEvidenceModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (e: Evidence) => void;
}) {
  const [mode, setMode] = useState<Mode>("import");

  // ---- Estado modo import ----
  const [tipo, setTipo] = useState<EvidenceTipo>("Audio");
  const [desc, setDesc] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // ---- Estado modo record ----
  const [recPhase, setRecPhase] = useState<RecPhase>("idle");
  const [recSecs, setRecSecs] = useState(0);
  const [recBlob, setRecBlob] = useState<Blob | null>(null);
  const [recDesc, setRecDesc] = useState("");
  const [recError, setRecError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const def = EVIDENCE_TYPES[tipo];

  // Limpiar recursos al desmontar
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // Cerrar con Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Resetear archivo al cambiar tipo
  const handleTipoChange = (t: EvidenceTipo) => {
    setTipo(t);
    setSelectedFile(null);
    setDesc("");
  };

  // ---- Import: agregar archivo seleccionado ----
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    // Resetear input para permitir elegir el mismo archivo de nuevo
    e.target.value = "";
  };

  const submitFile = () => {
    if (!selectedFile) return;
    onAdd({
      id: `e-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      tipo,
      fileType: EVIDENCE_TIPO_TO_FILE_TYPE[tipo],
      title: desc.trim() || selectedFile.name,
      file: selectedFile,
    });
    onClose();
  };

  // ---- Record: MediaRecorder real ----
  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startRec = useCallback(async () => {
    setRecError(null);
    setRecBlob(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const { mime } = getPreferredAudioMime();
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mime });
        setRecBlob(blob);
        stopStream();
        setRecPhase("done");
      };

      recorder.start();
      setRecSecs(0);
      setRecPhase("rec");
      timerRef.current = setInterval(
        () => setRecSecs((n) => n + 1),
        1000,
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error desconocido";
      if (msg.includes("Permission denied") || msg.includes("NotAllowed")) {
        setRecError(
          "Permiso de micrófono denegado. Habilitá el acceso en la configuración del navegador.",
        );
      } else if (msg.includes("NotFound") || msg.includes("Requested device not found")) {
        setRecError(
          "No se encontró un micrófono. Conectá uno e intentá de nuevo.",
        );
      } else {
        setRecError(msg);
      }
      setRecPhase("error");
    }
  }, [stopStream]);

  const stopRec = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  const addRecording = () => {
    if (!recBlob) return;
    const { ext } = getPreferredAudioMime();
    const fileName = `grabacion-${Date.now()}${ext}`;
    const file = new File([recBlob], fileName, { type: recBlob.type });
    onAdd({
      id: `e-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      tipo: "Audio",
      fileType: "audio",
      title: recDesc.trim() || "Grabación de audio",
      file,
    });
    onClose();
  };

  const resetRec = () => {
    setRecPhase("idle");
    setRecSecs(0);
    setRecBlob(null);
    setRecDesc("");
    setRecError(null);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Agregar evidencia"
      onClick={onClose}
      className="fixed inset-0 z-[120] flex items-center justify-center bg-[rgba(20,28,33,.45)] p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-h-[92vh] w-[486px] max-w-full overflow-y-auto rounded-[18px] bg-surface p-[26px_28px] shadow-modal animate-in"
      >
        {/* Header */}
        <div className="mb-1 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo">
              <WizardIcon d={evidenceIconPath(tipo)} size={18} />
            </span>
            <span className="text-xl font-extrabold text-ink-900">
              Agregar evidencia
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
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
        <div className="mb-4 text-[12.5px] text-ink-400">
          Sumá material existente o grabá un audio. El sistema lo procesa al generar el borrador.
        </div>

        {/* Segmented control de modo */}
        <div className="mb-5 flex gap-1 rounded-[11px] border border-line-soft bg-line-softer p-1">
          {(
            [
              [
                "import" as const,
                "Archivo existente",
                "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
              ],
              [
                "record" as const,
                "Grabar audio",
                "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4",
              ],
            ] as const
          ).map(([m, label, d]) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-[13px] font-bold transition-colors " +
                (mode === m
                  ? "bg-surface text-ink-800 shadow-card"
                  : "text-ink-400 hover:text-ink-700")
              }
            >
              <WizardIcon d={d} size={15} />
              {label}
            </button>
          ))}
        </div>

        {/* ============================================================
            MODO IMPORT
        ============================================================ */}
        {mode === "import" && (
          <>
            <div className="mb-[9px] text-[12.5px] font-bold text-ink-900">
              Tipo de evidencia
            </div>
            <div className="mb-3.5 flex flex-wrap items-center gap-[7px]">
              {TYPES.map((t) => {
                const active = t === tipo;
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => handleTipoChange(t)}
                    className={
                      "inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-[12.5px] font-bold transition-colors " +
                      (active
                        ? "border-indigo-light bg-indigo-tint text-indigo"
                        : "border-line bg-surface text-ink-500 hover:border-indigo-light")
                    }
                  >
                    <WizardIcon d={evidenceIconPath(t)} size={14} />
                    {t}
                  </button>
                );
              })}
            </div>
            <div className="mb-4 text-[11.5px] leading-snug text-ink-400">
              {def.help} · Formatos aceptados: {def.accept}
            </div>

            <label className="mb-[7px] block text-[12.5px] font-bold text-ink-900">
              Descripción{" "}
              <span className="font-medium text-ink-400">(opcional)</span>
            </label>
            <input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder={def.placeholder}
              className="mb-[18px] h-11 w-full rounded-[10px] border border-line-input px-[13px] text-[13.5px] text-ink-900 outline-none placeholder:text-ink-400 focus:border-indigo focus:ring-[3px] focus:ring-indigo-tint"
            />

            <div className="mb-2 text-[12.5px] font-bold text-ink-900">
              Archivo
            </div>

            {/* Input de archivo oculto */}
            <input
              ref={fileInputRef}
              type="file"
              accept={def.accept}
              className="sr-only"
              aria-hidden="true"
              tabIndex={-1}
              onChange={handleFileChange}
            />

            {!selectedFile ? (
              <div className="rounded-xl border-[1.5px] border-dashed border-line-input bg-surface-hover px-5 py-[30px] text-center">
                <div className="mb-3 text-sm font-bold text-ink-500">
                  Arrastrá tu evidencia aquí
                </div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="h-10 rounded-[9px] border border-line-input bg-surface px-[18px] text-[13.5px] font-semibold text-ink-800 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                >
                  Seleccionar archivo
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-[11px] rounded-xl border-[1.5px] border-success-bd bg-success-bg p-[13px_15px] animate-in">
                <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] bg-success">
                  <WizardIcon
                    d="M20 6L9 17l-5-5"
                    size={17}
                    className="text-white"
                    strokeWidth={2.4}
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13.5px] font-bold text-ink-900">
                    {selectedFile.name}
                  </div>
                  <div className="text-[11.5px] text-success-fg">
                    {formatFileSize(selectedFile.size)} · Lista para agregar
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  aria-label="Quitar archivo"
                  className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-[7px] border border-success-bd bg-surface transition-colors hover:bg-success-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                >
                  <WizardIcon
                    d="M18 6L6 18M6 6l12 12"
                    size={13}
                    className="text-ink-500"
                    strokeWidth={2.2}
                  />
                </button>
              </div>
            )}
            <div className="mt-2 text-[11.5px] text-ink-400">Máximo: 25 MB</div>

            <div className="mt-[22px] flex gap-[11px]">
              <button
                type="button"
                onClick={submitFile}
                disabled={!selectedFile}
                className={
                  "h-11 flex-1 rounded-[10px] text-sm font-bold text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action " +
                  (selectedFile
                    ? "bg-ink-800 hover:bg-ink-900"
                    : "cursor-not-allowed bg-ink-300")
                }
              >
                Agregar evidencia
              </button>
              <button
                type="button"
                onClick={onClose}
                className="h-11 flex-1 rounded-[10px] border border-line-input bg-surface text-sm font-semibold text-ink-700 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
              >
                Cancelar
              </button>
            </div>
            <div className="mt-3.5 text-center text-[11.5px] leading-relaxed text-ink-300">
              Las evidencias se procesan cuando generás el borrador.
            </div>
          </>
        )}

        {/* ============================================================
            MODO RECORD
        ============================================================ */}
        {mode === "record" && (
          <>
            {/* Error de acceso al micrófono */}
            {recError && (
              <div
                role="alert"
                className="mb-4 rounded-[10px] border border-danger-bd bg-danger-bg p-[11px_13px] text-[12.5px] text-danger"
              >
                {recError}
              </div>
            )}

            {recPhase === "idle" || recPhase === "error" ? (
              <div className="flex flex-col items-center gap-3.5 py-[14px]">
                <button
                  type="button"
                  onClick={startRec}
                  aria-label="Iniciar grabación"
                  className="grid h-[84px] w-[84px] place-items-center rounded-full bg-danger shadow-[0_10px_26px_rgba(203,66,66,.32)] transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-danger/30"
                >
                  <WizardIcon
                    d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4"
                    size={34}
                    className="text-white"
                  />
                </button>
                <div className="text-[13.5px] font-semibold text-ink-700">
                  Tocá para empezar a grabar
                </div>
                <RecordHint />
              </div>
            ) : null}

            {recPhase === "rec" && (
              <div className="flex flex-col items-center gap-4 py-2">
                <span className="relative grid h-[84px] w-[84px] place-items-center">
                  <span className="absolute inset-0 animate-ping rounded-full bg-danger/40" />
                  <span className="relative grid h-16 w-16 place-items-center rounded-full bg-danger">
                    <WizardIcon
                      d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4"
                      size={26}
                      className="text-white"
                    />
                  </span>
                </span>
                <div
                  className="font-mono text-[26px] font-extrabold text-ink-900"
                  aria-live="polite"
                  aria-label={`Tiempo de grabación: ${formatSecs(recSecs)}`}
                >
                  {formatSecs(recSecs)}
                </div>
                <button
                  type="button"
                  onClick={stopRec}
                  className="inline-flex h-11 items-center gap-2 rounded-pill bg-ink-800 px-[22px] text-sm font-bold text-white transition-colors hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                >
                  <span className="h-3 w-3 rounded-[3px] bg-white" aria-hidden="true" />
                  Detener
                </button>
                <RecordHint />
              </div>
            )}

            {recPhase === "done" && recBlob && (
              <>
                <div className="mb-4 flex items-center gap-[11px] rounded-xl border-[1.5px] border-success-bd bg-success-bg p-[13px_15px] animate-in">
                  <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-[9px] bg-success">
                    <WizardIcon
                      d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v4"
                      size={18}
                      className="text-white"
                    />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13.5px] font-bold text-ink-900">
                      Grabación lista
                    </div>
                    <div className="font-mono text-[11.5px] text-success-fg">
                      audio · {formatSecs(recSecs)} · {formatFileSize(recBlob.size)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={resetRec}
                    title="Regrabar"
                    aria-label="Regrabar"
                    className="grid h-[30px] w-[30px] flex-shrink-0 place-items-center rounded-[7px] border border-success-bd bg-surface transition-colors hover:bg-success-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                  >
                    <WizardIcon
                      d="M3 2v6h6M3.51 15a9 9 0 1 0 2.13-9.36L3 8"
                      size={14}
                      className="text-ink-500"
                    />
                  </button>
                </div>

                <label className="mb-[7px] block text-[12.5px] font-bold text-ink-900">
                  Descripción{" "}
                  <span className="font-medium text-ink-400">(opcional)</span>
                </label>
                <input
                  value={recDesc}
                  onChange={(e) => setRecDesc(e.target.value)}
                  placeholder="Ej: Entrevista al cajero"
                  className="mb-[18px] h-11 w-full rounded-[10px] border border-line-input px-[13px] text-[13.5px] text-ink-900 outline-none placeholder:text-ink-400 focus:border-indigo focus:ring-[3px] focus:ring-indigo-tint"
                />

                <div className="flex gap-[11px]">
                  <button
                    type="button"
                    onClick={addRecording}
                    className="h-11 flex-1 rounded-[10px] bg-success text-sm font-bold text-white transition-colors hover:bg-success-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                  >
                    Agregar grabación
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("import")}
                    className="h-11 flex-1 rounded-[10px] border border-line-input bg-surface text-sm font-semibold text-ink-700 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                  >
                    Volver
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function RecordHint() {
  return (
    <div className="flex w-full items-start gap-2 rounded-[10px] border border-line-soft bg-surface-app p-[11px_13px]">
      <WizardIcon
        d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z"
        size={15}
        className="mt-px flex-shrink-0 text-indigo"
      />
      <span className="text-[11.5px] leading-relaxed text-ink-500">
        El audio se transcribirá automáticamente al generar el borrador.
      </span>
    </div>
  );
}
